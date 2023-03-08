"""This module provides helper functions for retrieving, parsing, and merging
ASA metadata from indexer data.
"""
import os
import json
import requests
import datetime

from algosdk import error

from core.factory import AssetParserFactory
from core.asset_utils_base import AssetParserBase
from algorand.algoconn import IndexerBase
from algorand.schemas import ACfgTxn, AssetBaseSchema
from decorators import retry
from utils.ipfs import IPFSCacher, InvalidCIDError
from algorand.arc19 import cid_from_asset, address2cid

from structlog import get_logger
from core.settings import settings

IPFS_GATEWAY = settings.IPFS_GATEWAY
LOGGER = get_logger()

# def reserve_from_cid(cid):

# decodedMultiHash, err := multihash.Decode(cidToEncode.Hash())
# if err != nil {
#    return "", fmt.Errorf("failed to decode ipfs cid: %w", err))
#
# return types.EncodeAddress(decodedMultiHash.Digest)


def make_asset_url(asa_url, ipfs_gateway=None):
    if ipfs_gateway is None:
        ipfs_gateway = IPFS_GATEWAY
    if "ipfs://" in asa_url:
        cid = asa_url.replace("ipfs://", "").split("#")[0].strip("/")
    elif "https://" in asa_url and "ipfs/" in asa_url:
        cid = asa_url.split("ipfs/")[-1]
    elif "https://" in asa_url:
        return asa_url
    else:  # might be ipfs://abc123/abc.png structure
        cid = asa_url.split("ipfs://")[-1]

    if "tinyurl" in asa_url or "ipfs.dahai" in asa_url:
        url = asa_url
        if "http" not in url:
            url = "http://" + url
    else:
        url = ipfs_gateway + cid

    return url


@AssetParserFactory.register("algo")
class AssetParser(AssetParserBase, IndexerBase):
    _acfg_txns = None
    _url = None
    _arc3 = None
    _arc69 = None
    ## _arc19 = None
    _other_metadata = None
    _data = None
    _is_destroyed = None
    _media_url = None

    def __init__(self, asset_id=None, testnet=False):
        self.asset_id = asset_id
        self.network = "algo"
        IndexerBase.__init__(self, testnet=testnet)

    @property
    def acfg_txns(self):
        if self._acfg_txns is None:
            self._acfg_txns = self._get_acfg_txns()
        return self._acfg_txns

    @retry(error.IndexerHTTPError, tries=10, delay=0.5, logger=LOGGER)
    def _get_acfg_txns(self):
        # FIXME: This search asset txns could be wrong if theres over 1k of them
        try:
            responses = self.indexer.search_asset_transactions(
                asset_id=self.asset_id, txn_type="acfg"
            )
            self.use_fallback = False

        except error.IndexerHTTPError as e:
            self.use_fallback = True
            raise e

        txns = []
        for txn in responses["transactions"]:
            if txn.get("asset-config-transaction", None):
                txns.append(ACfgTxn(txn))
            elif txn.get("application-transaction", None):
                for inner in txn.get("inner-txns", []):
                    if "asset-config-transaction" not in inner:
                        if (
                            "inner-txns" in inner
                        ):  # sometimes there are inner txns within inner txns (innerception)
                            for inner2 in inner.get("inner-txns", []):
                                if "asset-config-transaction" in inner2:
                                    inner2["id"] = txn["id"]
                                    txns.append(ACfgTxn(inner2))
                        continue
                    inner["id"] = txn["id"]
                    if inner.get("created-asset-index", None) == self.asset_id:
                        txns.append(ACfgTxn(inner))
                        continue
                    txaid = inner["asset-config-transaction"].get("asset-id", None)
                    if (
                        txaid == int(self.asset_id) or txaid == 0
                    ):  # sometimes asset_id is a str not an int, maybe fix elsewhere?
                        txns.append(ACfgTxn(inner))
                        continue

        txns.reverse()  # puts the most recent txn first
        return txns

    @property
    def url(self):
        if self._url is None:
            self._url = self.get_asset_url(self.asset_data.url)

        return self._url

    @property
    def arc3(self):
        if self._arc3 is None:
            self._arc3 = self._get_arc3()
        return self._arc3 or {}

    @property
    def arc69(self):
        if self._arc69 is None:
            self._arc69 = self._get_arc69()
        return self._arc69 or {}

    # @property
    # def arc19(self):
    #    if self._arc19 is None:
    #        self._arc19 = self._get_arc19()
    #    return self._arc19 or {}

    @property
    def other_md(self):
        if self._other_metadata is None:
            self._other_metadata = self._get_other_md()
        return self._other_metadata or {}

    def _get_other_metadata(self):
        """Fixme: Asset 421840153 is non-standard"""
        return None

    def _get_arc3(self):
        """Parses the metadata request of ipfs metadata"""
        if not self.url:
            return False
        elif self.asset_data.name[-5:] == "@arc3" or self.url[-5:] == "#arc3":
            try:
                ipfs = IPFSCacher(self.url)
                content = ipfs.fetch_content()

                ## rq = self.fetch_url_content()
                return json.loads(content.decode())
            except InvalidCIDError:
                return False
        else:
            ipfs = IPFSCacher(self.url)
            # prefetch
            req = requests.head(ipfs.url)
            if "Content-Type" in req.headers:
                content_type = req.headers["Content-Type"]
            elif "Location" in req.headers:
                req = requests.head(req.headers["Location"])
                content_type = req.headers["Content-Type"]
            else:  # can't parse headers, TODO: might be more cases
                raise NotImplementedError()

            if "json" in content_type:
                content = ipfs.fetch_content()
                return json.loads(content.decode())
            else:
                return False

    def _get_arc69(self):
        for txn in self.acfg_txns:
            if txn.note:
                try:
                    notedata = json.loads(txn.note.decode("utf-8", "ignore"))
                    if not isinstance(notedata, dict):
                        return False
                    if notedata.get("standard", None) == "arc69":
                        return notedata
                except json.JSONDecodeError:
                    pass
        else:
            return False

    def get_asset_url(self, url):
        """Helper function that attempts to check and parse arc19 from the
        asset url, otherwise the original url value is passed back.

        :param url: Asset URL
        """
        if url:
            if "template-ipfs://" in url:
                arc19cid = cid_from_asset(self.asset_data.params.__dict__)
                return "ipfs://" + arc19cid
        return url

    @property
    def all_metadata(self):
        return {
            "arc3": self.arc3,
            "arc69": self.arc69,
        }

    @property
    def has_media(self):
        if not any(list(self.all_metadata.values())) and not self.url:
            return False
        elif self.url:
            if (
                "bit.ly" not in self.url
                and "tinyurl" not in self.url
                and "ipfs" not in self.url
            ):
                req = requests.head(self.url)
                mime = req.headers.get("Content-Type")
                if "image" in mime or "animation" in mime:
                    return True

                return False
        return True

    @property
    def media_url(self):
        if self._media_url is None:
            image_aliases = [
                "image",
                "image_url",
                "animation",
                "animation_url",
            ]  # "external_url",  ## Should we go this far?
            if not self.has_media:
                self._media_url = False
            elif self.arc3:
                for image_alias in image_aliases:
                    if self.arc3.get(image_alias, None):
                        self._media_url = self.arc3[image_alias]
                        break

            elif self.arc69:
                self._media_url = self.arc69.get("media_url") or self.url

            else:
                # FIXME: Anything else for this case? What about ARC19?
                self._media_url = self.url
        return self._media_url

    @property
    def external_link(self):
        for spec in ["arc3", "arc69"]:
            md = self.all_metadata.get(spec, {})
            if md.get("external_url") is not None:
                return md["external_url"]
        return None

    @property
    def media_cid(self):
        cid = None
        if "template-ipfs://" in self.media_url:
            raise NotImplementedError()
        elif "ipfs://" in self.media_url:
            cid = self.media_url.replace("ipfs://", "").split("#")[0].strip("/")
        elif "https://" in self.media_url and "ipfs" in self.media_url:
            cid = self.media_url.split("ipfs/")[-1]
        # else:  # might be ipfs://abc123/abc.png structure
        #    cid = self.media_url.split('ipfs://')[-1]

        return cid

    @property
    def asset_data(self):
        if self._data is None:
            data = self.acfg_txns[-1]  # Start with the OG data from creation
            if len(self.acfg_txns) > 1:
                data.params.manager = self.acfg_txns[0].params.manager
                data.params.reserve = self.acfg_txns[0].params.reserve
                data.params.freeze = self.acfg_txns[0].params.freeze
                data.params.clawback = self.acfg_txns[0].params.clawback
            if len(self.acfg_txns) > 3:
                # TODO: We need examples of assets in this case to make sure
                ## Final data is recorded correctly
                pass
            self._data = data

        return self._data

    @property
    def is_destroyed(self):
        if self._is_destroyed is None:
            if (
                self.acfg_txns[0].params.manager
                == self.acfg_txns[0].params.clawback
                == self.acfg_txns[0].params.freeze
                == self.acfg_txns[0].params.clawback
                is None
            ):
                self._is_destroyed = True
            else:
                self._is_destroyed = False
        return self._is_destroyed

    def normalize_traits(self, metadata):
        if metadata.get("arc69"):
            if (
                "properties" in metadata["arc69"]
                and type(metadata["arc69"]["properties"]) is dict
            ):
                return metadata["arc69"]["properties"]
            if (
                "attributes" in metadata["arc69"]
                and type(metadata["arc69"]["attributes"]) is list
            ):
                traits = {}
                for attribute in metadata["arc69"]["attributes"]:
                    if not "trait_type" in attribute or not "value" in attribute:
                        continue
                    traits[attribute["trait_type"]] = attribute["value"]
                return traits
            if (
                "traits" in metadata["arc69"]
                and type(metadata["arc69"]["traits"]) is dict
            ):
                return metadata["arc69"]["traits"]
        elif metadata.get("arc3"):
            if (
                "properties" in metadata["arc3"]
                and type(metadata["arc3"]["properties"]) is dict
            ):
                properties = metadata["arc3"]["properties"]
                for key in ["properties", "attributes", "traits"]:
                    if key in properties and type(properties[key]) is dict:
                        return properties[key]
                if type(properties) is dict:
                    return properties
        return {}

    def parse_description(self, metadata):
        if metadata.get("arc69"):
            return metadata["arc69"].get("description")
        elif metadata.get("arc3"):
            return metadata["arc3"].get("description")

    @retry(error.IndexerHTTPError, tries=10, delay=0.5, logger=LOGGER)
    def get_asset_balances(
        self,
        limit=None,
        next_page=None,
        min_balance=None,
        max_balance=None,
        include_all=False,
    ):
        try:
            holders = self.indexer.asset_balances(
                self.asset_id, limit, next_page, min_balance, max_balance, include_all
            )
        except error.IndexerHTTPError as e:
            raise e
        return holders

    @retry(error.IndexerHTTPError, tries=10, delay=0.5, logger=LOGGER)
    def get_all_asset_balances(self):
        holders = []
        asset_balances_next_page = None
        while True:
            asset_balances = self.indexer.asset_balances(
                asset_id=self.asset_id, limit=1000, next_page=asset_balances_next_page
            )
            holders.extend(asset_balances.get("balances"))
            asset_balances_next_page = asset_balances.get("next-token", None)

            if asset_balances_next_page is None:
                break
        return holders

    @retry(error.IndexerHTTPError, tries=10, delay=0.5, logger=LOGGER)
    def get_asset_transactions(
        self, limit=None, next_page=None, address=None, start_time=None, end_time=None
    ):
        try:
            transactions = self.indexer.search_asset_transactions(
                asset_id=self.asset_id,
                limit=limit,
                next_page=next_page,
                address=address,
                start_time=start_time,
                end_time=end_time,
            )
        except error.IndexerHTTPError as e:
            raise e
        return transactions["transactions"]

    def to_pydantic(self, media_info=None, collections=[]):
        # only including arc3 description, even though it's already in metadata
        descr = None
        for md in ["arc3", "arc69"]:
            if self.all_metadata[md].get("description", None):
                descr = self.all_metadata[md]["description"]
                break
        asset_info = self.asset_data.params.__dict__
        asset_pydantic = AssetBaseSchema(
            asset_id=self.asset_id,
            name=self.asset_data.name,
            description=descr,
            asset_info=asset_info,  # creator, reserve, clawback, freeze, manager
            asset_metadata=self.all_metadata,
            is_destroyed=self.is_destroyed,
            collection_asset=collections,
            network=self.network,
            blockchain_updated_at=datetime.datetime.utcnow(),
        )

        if media_info is not None:
            asset_pydantic.media = media_info

        return asset_pydantic

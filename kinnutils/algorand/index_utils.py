import structlog
from operator import mod

from algosdk.v2client.indexer import error

from core.factory import IndexParserFactory
from core.index_utils_base import IndexParserBase

from algorand.algoconn import IndexerBase
from decorators import retry

LOGGER = structlog.get_logger()


@IndexParserFactory.register("algo")
class IndexParser(IndexerBase, IndexParserBase):
    """
    For blockchain queries related to assets.
    """

    def __init__(self, testnet=False):
        IndexerBase.__init__(self, testnet=testnet)

    @retry(error.IndexerHTTPError, tries=20, delay=0.25, logger=LOGGER)
    def parse_block(self, round_num: int) -> dict:
        """
        Parses through asset transactions in a block for asset creations,
        deletions, or updates.

        :param round_num: the round number of the block to check
        :type round_num: int
        :returns: dictionary of asset id and direct ipfs address (cid) --> {asset_id: cid}
        """
        try:
            block = self.indexer.block_info(round_num=round_num)
            assets = []

            # TODO: move this to asset parser, indexparser should just be a manager that directs
            for i in block["transactions"]:
                if i["tx-type"] == "acfg":
                    if "created-asset-index" in i:  # asset creation
                        if "url" in i["asset-config-transaction"]["params"]:
                            url = i["asset-config-transaction"]["params"]["url"]
                            if "ipfs" in url or "ardrive" in url or "tinyurl" in url:
                                asa_id = i["created-asset-index"]
                                assets.append(
                                    {"id": asa_id, "event": "creation"}
                                )  # TODO: include note field
                    else:  # check if asset deletion or modification
                        asset_id = i["asset-config-transaction"]["asset-id"]
                        asset = self.indexer.search_assets(
                            asset_id=asset_id, include_all=True
                        )["assets"][0]
                        if asset["deleted"]:  # deleted
                            assets.append({"id": asset_id, "event": "deletion"})
                        else:  # modified
                            assets.append({"id": asset_id, "event": "modification"})
                # elif i["tx-type"] == "axfer":
                ## TODO

            self.use_fallback = False
            # FIXME: This function may be generalized a bit to allow for finding other
            #  On chain events ie certain txns or aaplication calls. Asset specific activities
            #  shoul be handled in the asset utils Asset Parser Class.
            return assets

        except error.IndexerHTTPError as e:
            self.use_fallback = True
            raise e

    @retry(error.IndexerHTTPError, tries=20, delay=0.25, logger=LOGGER)
    def get_created_assets(self, round_num: int) -> list:
        """
        Parses through asset transactions in a block for created assets.

        :param round_num: the round number of the block to check
        :type round_num: int
        :returns: dict --> {asset_id: cid}
        """
        try:
            block = self.indexer.block_info(round_num=round_num)
            self.use_fallback = False
        except error.IndexerHTTPError as e:
            self.use_fallback = True
            raise e

        assets = []
        for i in block["transactions"]:
            if i["tx-type"] == "acfg":
                if "created-asset-index" in i:
                    if "url" in i["asset-config-transaction"]["params"]:
                        url = i["asset-config-transaction"]["params"]["url"]
                        if "ipfs" in url or "ardrive" in url or "tinyurl" in url:
                            asa_id = i["created-asset-index"]
                            assets.append({asa_id: url})
        return assets

    @retry(error.IndexerHTTPError, tries=20, delay=0.25, logger=LOGGER)
    def check_asset(self, asa_id):
        """
        Checks if an asset id contains a url using immutable file storage
        """
        try:
            response = self.indexer.search_assets(asset_id=asa_id)
            self.use_fallback = False
        except error.IndexerHTTPError as e:
            self.use_fallback = True
            raise e

        try:
            if len(response["assets"]):
                if not response["assets"][0][
                    "deleted"
                ]:  # only record assets that haven't been deleted
                    if (
                        "url" in response["assets"][0]["params"]
                    ):  # I checked, all assets either have len(0) or len(1) except asset 0
                        url = response["assets"][0]["params"]["url"]
                        if (
                            "ipfs" in url or "ardrive" in url or "tinyurl" in url
                        ):  # too many random urls otherwise
                            return {asa_id: url}
        except Exception as e:
            # TODO: Put better error message here
            return {asa_id: e}

    @retry(error.IndexerHTTPError, tries=20, delay=0.25, logger=LOGGER)
    def current_round(self):
        try:
            round = self.indexer.health()["round"]
            self.use_fallback = False
            return round
        except error.IndexerHTTPError as e:
            self.use_fallback = True
            raise e

        # algosdk.error.IndexerHTTPError: Limit Exceeded

    @retry(error.IndexerHTTPError, tries=20, delay=0.25, logger=LOGGER)
    def get_block_info(self, round_num):
        try:
            block = self.indexer.block_info(round_num=round_num)
        except error.IndexerHTTPError as e:
            raise e
        return block

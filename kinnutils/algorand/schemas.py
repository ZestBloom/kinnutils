import base64
import datetime

from dataclasses import dataclass
from pydantic import BaseModel


@dataclass
class AcfgParams:
    creator: str
    decimals: int
    total: int
    round: int
    url: str = None
    url_b64: str = None
    name: str = None
    name_b64: str = None
    unit_name: str = None
    unit_name_b64: str = None
    default_frozen: bool = None
    metadata_hash: str = None
    manager: str = None
    freeze: str = None
    reserve: str = None
    clawback: str = None


class Txn:
    def __init__(self, txninfo):
        self.data = txninfo

    @property
    def round_time(self):
        return self.data["round-time"]

    @property
    def note(self):
        if "note" in self.data:
            return base64.b64decode(self.data["note"])
        return None

    @property
    def type(self):
        return self.data["tx-type"]


class ACfgTxn(Txn):
    def __init__(self, txninfo):
        Txn.__init__(self, txninfo)
        params = self.data["asset-config-transaction"]["params"]
        for key in list(params.keys()):
            if "-" in key:
                params[key.replace("-", "_")] = params.pop(key)
        params["round"] = self.data["confirmed-round"]
        self.params = AcfgParams(**params)
        self.txn_id = self.data["id"]

    @property
    def created_asset_id(self):
        self.data.get("created-asset-index", None)

    def __repr__(self):
        rep = f"ACfgTxn({self.txn_id})"
        return rep


class AssetBaseSchema(BaseModel):
    asset_id: int
    name: str
    description: str = None
    asset_info: dict
    asset_metadata: dict = None
    is_destroyed: bool
    media: dict = None
    collection_asset: list = []
    network: str
    blockchain_updated_at: datetime.datetime

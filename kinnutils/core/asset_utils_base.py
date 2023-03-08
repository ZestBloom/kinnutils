from abc import ABC, abstractmethod


class AssetParserBase(ABC):
    def __init__(self, **kwargs):
        """Constructor"""
        pass

    @abstractmethod
    def to_pydantic(self, media_info=None, collection=None):
        pass

    @property
    @abstractmethod
    def is_destroyed(self):
        pass

    @property
    @abstractmethod
    def asset_data(self):
        pass

    @property
    @abstractmethod
    def media_cid(self):
        pass

    @property
    @abstractmethod
    def media_url(self):
        pass

    @property
    @abstractmethod
    def url(self):
        pass

    @property
    @abstractmethod
    def all_metadata(self):
        pass

    @abstractmethod
    def process_asset_media(self):
        pass

    @abstractmethod
    def get_all_asset_balances(self):
        pass

    @abstractmethod
    def get_asset_balances(
        self,
        limit=None,
        next_page=None,
        min_balance=None,
        max_balance=None,
        include_all=False,
    ):
        pass

    @abstractmethod
    def get_asset_transactions(
        self, limit=None, next_page=None, address=None, start_time=None, end_time=None
    ):
        pass

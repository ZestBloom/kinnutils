from abc import ABC, abstractmethod


class IndexParserBase(ABC):
    def __init__(self, **kwargs):
        """Constructor"""
        pass

    @abstractmethod
    def parse_block(self):
        pass

    @abstractmethod
    def get_created_assets(self):
        pass

    @abstractmethod
    def check_asset(self):
        pass

    @abstractmethod
    def current_round(self):
        pass

    @abstractmethod
    def get_block_info(self, round_num: int):
        pass

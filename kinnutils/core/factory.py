from typing import Callable
import structlog

from core.asset_utils_base import AssetParserBase
from core.index_utils_base import IndexParserBase
from core.accounts_base import AccountBase

logger = structlog.get_logger()

class AssetParserFactory:
    networks = {}
    """ Internal memory for available networks """

    @classmethod
    def register(self, network: str) -> Callable:
        """Class method to register network class to the internal network memory.
        network (str): The name of the network.
        """

        def inner_wrapper(wrapped_class: AssetParserBase) -> Callable:
            if network in self.networks:
                logger.warning("AssetParser %s already exists.", network)
                return None

            self.networks[network] = wrapped_class
            return wrapped_class

        return inner_wrapper

    @classmethod
    def get_asset_parser(self, network: str, **kwargs) -> AssetParserBase:
        """Factory command to create the AssetParser.
        This method gets the appropriate AssetParser class from the registry
        and creates an instance of it, while passing in the parameters
        given in ``kwargs``.
        Args:
            network (str): The name of the network to create.
        """
        if network not in self.networks:
            logger.warning("AssetParser %s does not exist in the memory", network)
            return None

        asset_parser_class = self.networks[network]
        instance = asset_parser_class(**kwargs)
        return instance


class IndexParserFactory:
    networks = {}

    @classmethod
    def register(self, network: str) -> Callable:
        def inner_wrapper(wrapped_class: IndexParserBase) -> Callable:
            if network in self.networks:
                logger.warning("IndexParser %s already exists.", network)
                return None

            self.networks[network] = wrapped_class
            return wrapped_class

        return inner_wrapper

    @classmethod
    def get_index_parser(self, network: str, **kwargs) -> IndexParserBase:
        if network not in self.networks:
            logger.warning("IndexParser %s does not exist in the memory", network)
            return None

        index_parser_class = self.networks[network]
        instance = index_parser_class(**kwargs)
        return instance


class AccountFactory:
    networks = {}

    @classmethod
    def register(self, network: str) -> Callable:
        def inner_wrapper(wrapped_class: AccountBase) -> Callable:
            if network in self.networks:
                logger.warning("Account %s already exists.", network)
                return None

            self.networks[network] = wrapped_class
            return wrapped_class

        return inner_wrapper

    @classmethod
    def get_account_utils(self, network: str, **kwargs) -> AccountBase:
        if network not in self.networks:
            logger.warning("Account %s does not exist in the memory", network)
            return None

        account_class = self.networks[network]
        instance = account_class(**kwargs)
        return instance

import os
import logging
import configparser

from algosdk.v2client import algod as algodv2
from algosdk.v2client import indexer

from core.settings import settings


def get_algod(testnet=False):
    header = {"X-Api-key": settings.ALGORAND_NODE_API_KEY}

    node_host = (
        settings.TESTNET_ALGORAND_NODE_HOST
        if testnet
        else settings.ALGORAND_NODE_HOST
    )
    return algodv2.AlgodClient(
        settings.ALGORAND_NODE_API_KEY, node_host, headers=header
    )


def get_indexer(endpoint=None, key=None, testnet=False):
    if key is None:
        key = os.environ["ALGORAND_INDEXER_API_KEY"]
        header = {"X-Api-key": settings.ALGORAND_INDEXER_API_KEY}
    else:
        header = None

    if endpoint is None:
        endpoint = (
            settings.TESTNET_ALGORAND_INDEXER_HOST
            if testnet
            else settings.ALGORAND_INDEXER_HOST
        )

    return indexer.IndexerClient(
        indexer_token=key, indexer_address=endpoint, headers=header
    )


class IndexerBase:
    idxr = None
    backup_idxr = None
    use_fallback = False

    def __init__(self, indexer=None, backup=None, testnet=False):
        """Initialize the Index Parser"""
        if indexer is None:
            self.idxr = get_indexer(testnet=testnet)
        else:
            self.idxr = indexer

        if backup is None:
            ep = (
                settings.TESTNET_ALGORAND_INDEXER_FALLBACK
                if testnet
                else settings.ALGORAND_INDEXER_FALLBACK
            )
            self.backup_idxr = get_indexer(ep, "")
        else:
            self.backup_idxr = backup

    @property
    def indexer(self):
        """Swap indexer API keys"""
        if self.use_fallback:
            return self.backup_idxr
        else:
            return self.idxr

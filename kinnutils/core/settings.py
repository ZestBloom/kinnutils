from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseSettings, validator
from typing import List, Optional

load_dotenv()

class Settings(BaseSettings):
    ALGORAND_INDEXER_API_KEY: Optional[str]
    ALGORAND_NODE_API_KEY: Optional[str]

    TESTNET_ALGORAND_NODE_HOST: AnyHttpUrl
    TESTNET_ALGORAND_INDEXER_HOST: AnyHttpUrl
    TESTNET_ALGORAND_INDEXER_FALLBACK: AnyHttpUrl

    ALGORAND_NODE_HOST: AnyHttpUrl
    ALGORAND_INDEXER_HOST: AnyHttpUrl
    ALGORAND_INDEXER_FALLBACK: AnyHttpUrl

    IPFS_GATEWAY: AnyHttpUrl

    ALGORAND_INDEXER_FALLBACK: AnyHttpUrl


settings = Settings()
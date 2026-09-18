import lancedb
import asyncio
from typing import Optional
from ..config.store_config import get_lancedb_store_config
from ..core.logger import CustomLogger



class LanceDBClient:
    _instance: Optional["LanceDBClient"] = None
    _lock = asyncio.Lock() 

    def __init__(self):
        if LanceDBClient._instance is not None:
            raise RuntimeError("Use LanceDBClient.get_instance() instead.")
        self.db: Optional[lancedb.AsyncConnection] = None

    @classmethod
    async def initialize(cls):
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    instance = cls()
                    db_path = get_lancedb_store_config().path
                    
                    instance.db = await lancedb.connect_async(db_path)
                    cls._instance = instance
                    logger = CustomLogger.get_instance()
                    logger.info(f"LanceDBClient initialized successfully with singleton object")
                    
        

    @classmethod
    def get_connection(cls) -> lancedb.AsyncConnection:
        if cls._instance is None:
            raise RuntimeError("LanceDBClient is not initialized! Call initialize() at startup.")
        return cls._instance.db

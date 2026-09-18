from pydantic import BaseModel, Field
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class ServerConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=int(os.getenv("PORT", 8010)))
    debug: bool = Field(default=bool(os.getenv("DEBUG", "false").lower() == "true"))
    name: str = Field(default="RAG Retrieval Server")
    description: str = Field(default="RAG Retrieval Server\n This is a server for retrieving documents from a RAG system. Here you can query the RAG system and get the relevant documents.")
    


@lru_cache(maxsize=1)
def get_server_config() -> ServerConfig:
    return ServerConfig()
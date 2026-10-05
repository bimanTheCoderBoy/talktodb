from pydantic import BaseModel, Field


class CatalogRetrievalRequest(BaseModel):
    query: str = Field(description="Natural language query to retrieve relevant catalog columns.")

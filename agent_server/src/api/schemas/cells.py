from pydantic import BaseModel, Field
from typing import Optional, List, Any, Union


class SitesCellsRequest(BaseModel):
    """Request body for POST /api/sites-cells."""
    cords: Optional[List[List[float]]] = Field(
        None,
        description="Boundary polygon coordinates as [[lon, lat], ...]. "
                    "When provided, only polygon filtering is applied (text filters are ignored).",
    )
    auth_scope: bool = Field(False, description="Auth scope")


class CellItem(BaseModel):
    cell_iid: Optional[str] = None
    azimuth: Optional[Any] = None
    band: Optional[Union[str, int]] = None
    pci: Optional[Any] = None
    technology: Optional[str] = None
    selected: Optional[bool] = None

class SiteItem(BaseModel):
    site_iid: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    state: Optional[str] = None
    address1: Optional[str] = None
    town: Optional[str] = None
    technology: List[str] = Field(default_factory=list)
    cells: List[CellItem] = Field(default_factory=list)


class SitesCellsResponse(BaseModel):
    """Response for POST /api/sites-cells."""
    sites: List[SiteItem]
    count: int

from pydantic import BaseModel
from typing import Optional

class LanggraphEvent(BaseModel):
    step: str
    status: str
    message: str
    event: Optional[str] = None
    payload: Optional[dict] = None
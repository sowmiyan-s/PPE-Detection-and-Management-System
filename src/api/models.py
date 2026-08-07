from pydantic import BaseModel, Field
from typing import List, Optional

class ZoneCreate(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = "Custom Zone"
    kind: Optional[str] = None # For backward compatibility with older dashboard payload
    zone: Optional[str] = None
    required_ppe: Optional[List[str]] = Field(default_factory=list)

class CameraCreate(BaseModel):
    id: Optional[str] = None
    name: str = "New Camera"
    source: Optional[str] = None
    streamUrl: Optional[str] = None # For backward compatibility with older dashboard payload
    location: Optional[str] = ""
    zoneId: Optional[str] = "ZONE-01"
    targetFps: Optional[int] = 20

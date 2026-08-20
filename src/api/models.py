from pydantic import BaseModel, Field
from typing import List, Optional

class ZoneCreate(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = "Custom Zone"
    kind: Optional[str] = None # For backward compatibility with older dashboard payload
    zone: Optional[str] = None
    required_ppe: Optional[List[str]] = Field(default_factory=list)
    frame_threshold: Optional[int] = Field(default=8, alias="frameThreshold")
    dwell_seconds: Optional[int] = Field(default=2, alias="dwellSeconds")
    confidence: Optional[float] = Field(default=0.60, alias="confidenceThreshold")

    class Config:
        populate_by_name = True
        extra = "allow"

class CameraCreate(BaseModel):
    id: Optional[str] = None
    name: str = "New Camera"
    source: Optional[str] = None
    streamUrl: Optional[str] = None # For backward compatibility with older dashboard payload
    type: Optional[str] = None # 'webcam' or 'stream'
    location: Optional[str] = ""
    zoneId: Optional[str] = "ZONE-01"
    targetFps: Optional[int] = 20

class DBEngineRequest(BaseModel):
    engine: str



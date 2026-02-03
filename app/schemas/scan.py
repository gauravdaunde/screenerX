from pydantic import BaseModel
from typing import List, Optional

class Signal(BaseModel):
    symbol: str
    strategy: str
    signal: str
    price: float
    stop_loss: float
    target: float
    confidence: float
    reason: str

class ScanResponse(BaseModel):
    status: str
    timestamp: str
    signals_found: int
    signals: List[Signal]

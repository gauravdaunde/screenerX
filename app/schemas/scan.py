from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any

class Signal(BaseModel):
    symbol: str
    strategy: Optional[str] = None
    strategy_name: Optional[str] = None
    signal: str
    price: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    quantity: Optional[int] = None
    invested_value: Optional[float] = None
    
    class Config:
        extra = "allow"  # Allow extra fields

class ScanResponse(BaseModel):
    status: str
    timestamp: str
    signals_found: int
    signals: List[Any]  # Allow any dict structure

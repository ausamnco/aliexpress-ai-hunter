from typing import List, Optional, Any
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    search_term: str = Field(..., description="Product name or keywords to search for on AliExpress")
    conditions: str = Field(..., description="User-specified constraints, criteria, and filters")
    gemini_api_key: str = Field(..., description="Gemini API Key provided by the user")
    max_candidates: int = Field(default=30, ge=5, le=100, description="Max products to parse and evaluate")
    ship_country: str = Field(default="AU", description="Destination country code for shipping")
    currency: str = Field(default="AUD", description="Display currency code")
    model_name: str = Field(default="gemini-2.5-flash", description="Gemini model version to use")

class CriteriaEvaluation(BaseModel):
    condition: str
    met: bool
    evidence: str

class ProductEvaluation(BaseModel):
    is_match: bool
    confidence: float
    verdict_reason: str
    criteria_evaluations: List[CriteriaEvaluation] = Field(default_factory=list)

class ItemModel(BaseModel):
    id: Optional[int] = None
    search_id: str
    item_id: str
    title: str
    price: str
    original_price: Optional[str] = None
    image_url: Optional[str] = None
    url: str
    rating: Optional[str] = None
    sales: Optional[str] = None
    is_match: bool = False
    verdict_reason: Optional[str] = None
    criteria_breakdown: List[CriteriaEvaluation] = Field(default_factory=list)
    specs: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None

class SearchRecord(BaseModel):
    id: str
    search_term: str
    conditions: str
    timestamp: str
    status: str
    total_found: int = 0
    total_matched: int = 0
    currency: str = "AUD"
    ship_country: str = "AU"
    items: Optional[List[ItemModel]] = None

class ValidateKeyRequest(BaseModel):
    api_key: str

class CaptchaActionRequest(BaseModel):
    search_id: str
    action: str = Field(default="drag", description="Action type: drag, click, resolve, cancel")
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class CriteriaEvaluation(BaseModel):
    condition: str = Field(description="The specific user condition evaluated.")
    met: bool = Field(description="True if the condition is fully met, False otherwise.")
    evidence: str = Field(description="Direct factual evidence from title, specs, or page text supporting this verdict.")

class ProductEvaluation(BaseModel):
    is_match: bool = Field(description="True ONLY if ALL user criteria are met, False otherwise.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")
    verdict_reason: str = Field(description="A clear 1-2 sentence explanation summarizing why the item matches or fails.")
    criteria_evaluations: List[CriteriaEvaluation] = Field(description="Granular evaluation for each user condition.")

class ItemDetail(BaseModel):
    item_id: str
    title: str
    price: str
    original_price: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    specs: List[str] = []
    is_match: bool = False
    verdict_reason: Optional[str] = None
    confidence: Optional[float] = None
    criteria_breakdown: List[Dict[str, Any]] = []

class SearchRequest(BaseModel):
    search_term: Optional[str] = ""
    search_terms: Optional[List[str]] = []
    conditions: str
    gemini_api_key: str
    max_candidates: int = Field(default=30, ge=5, le=100)
    ship_country: str = Field(default="AU")
    currency: str = Field(default="AUD")
    model_name: str = Field(default="gemini-2.5-flash")

class ValidateKeyRequest(BaseModel):
    api_key: str

class CaptchaActionRequest(BaseModel):
    search_id: str
    action: str  # "resolve", "sync_cookie", "sync_url", "cancel", "done"
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None
    distance_pct: Optional[float] = None
    cookie_str: Optional[str] = None
    redirect_url: Optional[str] = None

class CaptchaMouseEvent(BaseModel):
    search_id: str
    type: str  # "down", "move", "up", "click"
    x: float
    y: float

class CaptchaResumeRequest(BaseModel):
    search_id: str
    action: str  # "retry", "continue_remaining", "cancel"

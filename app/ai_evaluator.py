import json
import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from app.models import ProductEvaluation, CriteriaEvaluation

logger = logging.getLogger(__name__)

async def validate_api_key(api_key: str) -> bool:
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say 'OK'"
        )
        return bool(response and response.text)
    except Exception as e:
        logger.error(f"API key validation error: {e}")
        return False

async def generate_search_variations(search_term: str, conditions: str, api_key: str, model_name: str = "gemini-2.5-flash") -> List[str]:
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
Given a user's product search term and criteria, generate 3 to 4 distinct, highly effective AliExpress keyword search phrases (max 4-6 words each) optimized to find relevant listings.

User Product: {search_term}
User Conditions: {conditions}

Return ONLY a valid JSON array of strings, for example: ["phrase 1", "phrase 2", "phrase 3"]
"""
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            )
        )
        data = json.loads(response.text)
        if isinstance(data, list) and len(data) > 0:
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception as e:
        logger.warning(f"Error generating search variations with Gemini: {e}")
    
    # Fallback to base search term
    return [search_term]

async def evaluate_product_criteria(
    item_title: str,
    item_price: str,
    specs: List[str],
    body_snippet: str,
    user_conditions: str,
    api_key: str,
    model_name: str = "gemini-2.5-flash"
) -> ProductEvaluation:
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
You are an expert product evaluation assistant. You must rigorously check if the following AliExpress product strictly meets ALL user-defined conditions.

### USER-DEFINED CONDITIONS:
{user_conditions}

### PRODUCT TO EVALUATE:
- Title: {item_title}
- Price: {item_price}
- Specifications:
{json.dumps(specs, indent=2, ensure_ascii=False)}
- Page Snippet / Features:
{body_snippet[:3000]}

### INSTRUCTIONS:
1. Break down the user's conditions into distinct criteria checks.
2. For each condition, determine if it is TRUE (met) or FALSE (unmet) based on direct evidence from the product data.
3. If an essential condition is not met or only partially satisfied (e.g. user asked for Active Noise Cancellation, but product only has call mic noise reduction / ENC), mark that condition as unmet (met=false).
4. `is_match` should be TRUE ONLY IF ALL required user conditions are met.
5. Provide concise factual evidence for each evaluation.
"""

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProductEvaluation,
                temperature=0.1,
            )
        )
        
        if response.parsed:
            return response.parsed
            
        data = json.loads(response.text)
        return ProductEvaluation(**data)
        
    except Exception as e:
        logger.error(f"Gemini evaluation error for '{item_title}': {e}")
        # Fallback basic evaluation
        return ProductEvaluation(
            is_match=False,
            confidence=0.5,
            verdict_reason=f"AI evaluation failed: {str(e)[:100]}",
            criteria_evaluations=[
                CriteriaEvaluation(
                    condition="Automated Verification",
                    met=False,
                    evidence="AI evaluation timed out or encountered an API error."
                )
            ]
        )

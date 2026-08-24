import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types
from google.genai.errors import APIError
from app.models import ProductEvaluation, CriteriaEvaluation

logger = logging.getLogger(__name__)

async def diagnose_and_validate_key(api_key: str) -> Dict[str, Any]:
    """
    Performs a thorough diagnosis of the Gemini API key:
    1. Authenticates & lists models (checks if key is valid).
    2. Probes content generation on available models (checks quota & model availability).
    3. Returns detailed, actionable error diagnostics.
    """
    clean_key = api_key.strip()
    if not clean_key:
        return {
            "valid": False,
            "quota_available": False,
            "error_type": "EMPTY_KEY",
            "message": "The provided API key is empty.",
            "models": []
        }

    try:
        client = genai.Client(api_key=clean_key)
    except Exception as e:
        return {
            "valid": False,
            "quota_available": False,
            "error_type": "INIT_ERROR",
            "message": f"Failed to initialize Gemini client: {str(e)}",
            "models": []
        }

    # Step 1: Check authentication & list models
    discovered_models = []
    try:
        models_pager = client.models.list()
        for m in models_pager:
            name = m.name
            if name.startswith("models/"):
                name = name.replace("models/", "")
            if "gemini" in name or "gemma" in name:
                if not any(x in name for x in ["embedding", "bison", "aqa"]):
                    discovered_models.append(name)
    except Exception as e:
        err_str = str(e).lower()
        if "api_key_invalid" in err_str or "invalid api key" in err_str or "400" in err_str:
            return {
                "valid": False,
                "quota_available": False,
                "error_type": "INVALID_KEY",
                "message": "Invalid Gemini API key. Please check your key from Google AI Studio.",
                "models": []
            }
        elif "permission_denied" in err_str or "403" in err_str:
            return {
                "valid": False,
                "quota_available": False,
                "error_type": "PERMISSION_DENIED",
                "message": "Permission denied. The API key does not have Gemini API access enabled in your Google Cloud project.",
                "models": []
            }
        elif "resource_exhausted" in err_str or "429" in err_str or "quota" in err_str:
            return {
                "valid": True,
                "quota_available": False,
                "error_type": "QUOTA_EXHAUSTED",
                "message": "API key is valid, but your request quota has been exhausted (Rate Limit 429). Please wait a minute or check AI Studio quotas.",
                "models": []
            }
        elif "location" in err_str:
            return {
                "valid": False,
                "quota_available": False,
                "error_type": "LOCATION_UNSUPPORTED",
                "message": "Gemini API is not available in your region/location or IP is restricted.",
                "models": []
            }
        else:
            return {
                "valid": False,
                "quota_available": False,
                "error_type": "AUTH_ERROR",
                "message": f"Authentication failed: {str(e)[:150]}",
                "models": []
            }

    # Order models by priority
    priority = [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.7-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
        "gemini-2.5-flash"
    ]
    sorted_models = []
    for p in priority:
        if p in discovered_models:
            sorted_models.append(p)
    for m in discovered_models:
        if m not in sorted_models:
            sorted_models.append(m)

    test_models = sorted_models if sorted_models else ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]

    # Step 2: Test content generation & quota on available models
    verified_models = []
    last_err = ""
    for test_model in test_models[:6]:
        try:
            response = client.models.generate_content(
                model=test_model,
                contents="Reply with 'OK'"
            )
            if response and response.text:
                verified_models.append(test_model)
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Probe failed for {test_model}: {last_err}")
            continue

    if verified_models:
        return {
            "valid": True,
            "quota_available": True,
            "error_type": None,
            "message": f"Gemini API key is active and verified with {verified_models[0]}!",
            "models": verified_models + [m for m in test_models if m not in verified_models]
        }

    # If all generation probes failed
    return {
        "valid": True,
        "quota_available": False,
        "error_type": "GENERATION_PROBE_FAILED",
        "message": f"API key is authenticated, but generation probes failed: {last_err[:120]}",
        "models": test_models
    }

async def list_available_models(api_key: str) -> List[str]:
    diag = await diagnose_and_validate_key(api_key)
    return diag.get("models", ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"])

async def generate_search_variations(search_term: str, conditions: str, api_key: str, model_name: str = "gemini-3.6-flash") -> List[str]:
    client = genai.Client(api_key=api_key)
    prompt = f"""
Given a user's product search term and criteria, generate 3 to 4 distinct, highly effective AliExpress keyword search phrases (max 4-6 words each) optimized to find relevant listings.

User Product: {search_term}
User Conditions: {conditions}

Return ONLY a valid JSON array of strings, for example: ["phrase 1", "phrase 2", "phrase 3"]
"""
    fallback_models = [model_name, "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
    seen = set()
    models_to_try = [m for m in fallback_models if m and not (m in seen or seen.add(m))]

    for m in models_to_try:
        try:
            response = client.models.generate_content(
                model=m,
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
            logger.warning(f"Variation generation error on {m}: {e}")
            continue

    return [search_term]

async def evaluate_product_criteria(
    item_title: str,
    item_price: str,
    specs: List[str],
    body_snippet: str,
    user_conditions: str,
    api_key: str,
    model_name: str = "gemini-3.6-flash"
) -> ProductEvaluation:
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

    fallback_models = [model_name, "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
    seen = set()
    models_to_try = [m for m in fallback_models if m and not (m in seen or seen.add(m))]

    last_error = ""
    for m in models_to_try:
        try:
            response = client.models.generate_content(
                model=m,
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
            last_error = str(e)
            logger.warning(f"Evaluation error on {m}: {e}")
            continue

    logger.error(f"Gemini evaluation failed on all models for '{item_title}': {last_error}")
    return ProductEvaluation(
        is_match=False,
        confidence=0.5,
        verdict_reason=f"AI evaluation failed: {last_error[:100]}",
        criteria_evaluations=[
            CriteriaEvaluation(
                condition="Automated Verification",
                met=False,
                evidence="AI evaluation timed out or encountered an API error."
            )
        ]
    )

async def evaluate_product(
    item: Dict[str, Any],
    conditions: str,
    api_key: str,
    model_name: str = "gemini-3.7-flash"
) -> ProductEvaluation:
    title = item.get("title", "")
    price = item.get("price", "N/A")
    specs = item.get("specs", [])
    snippet = json.dumps(item, ensure_ascii=False)
    
    return await evaluate_product_criteria(
        item_title=title,
        item_price=price,
        specs=specs,
        body_snippet=snippet,
        user_conditions=conditions,
        api_key=api_key,
        model_name=model_name
    )


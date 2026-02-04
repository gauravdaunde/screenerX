from fastapi import Security, HTTPException, Query
from fastapi.security import APIKeyHeader
from app.core.config import API_KEYS, logger

API_KEY_HEADER_NAME = "access_token" 
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)

async def get_api_key(
    api_key_header: str = Security(api_key_header),
    token: str = Query(None)
):
    """
    Validate API Key from either Header or Query Parameter.
    Supports multiple API keys for different users/friends.
    """
    if not API_KEYS:
        logger.warning("⚠️ No API_KEY/API_KEYS set in .env! API is unsecured.")
        return "unsecured_mode"
    
    # Check Header
    if api_key_header and api_key_header in API_KEYS:
        return api_key_header
        
    # Check Query Param (e.g. ?token=123)
    if token and token in API_KEYS:
        return token
        
    raise HTTPException(
        status_code=403, 
        detail="Could not validate credentials. Please provide correct 'access_token' header or '?token=' query parameter."
    )


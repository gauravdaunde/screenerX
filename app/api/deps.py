from fastapi import Security, HTTPException, Query
from fastapi.security import APIKeyHeader
from app.core.config import API_KEY, logger

API_KEY_HEADER_NAME = "access_token" 
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)

async def get_api_key(
    api_key_header: str = Security(api_key_header),
    token: str = Query(None)
):
    """
    Validate API Key from either Header or Query Parameter.
    """
    if not API_KEY:
        logger.warning("⚠️ No API_KEY set in .env! API is unsecured.")
        return "unsecured_mode"
    
    # Check Header
    if api_key_header == API_KEY:
        return api_key_header
        
    # Check Query Param (e.g. ?token=123)
    if token == API_KEY:
        return token
        
    raise HTTPException(
        status_code=403, 
        detail="Could not validate credentials. Please provide correct 'access_token' header or '?token=' query parameter."
    )

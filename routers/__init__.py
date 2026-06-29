from fastapi import Header, Query, HTTPException

from config import settings


async def verify_api_key(
    x_api_key: str | None = Header(None),
    api_key: str | None = Query(None),
):
    key = x_api_key or api_key
    if not key or key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

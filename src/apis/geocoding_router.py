"""src.apis.geocoding_router
Geocoding API 라우터 - 주소 → 위도/경도 변환
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from src.models.geocoding_models import GeocodingRequest, GeocodingResponse
from src.services.geocoding_service import geocode_with_kakao
from src.utils.common import verify_api_key
from src.core.exceptions import CustomError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Geocoding API"])


@router.post("/geocode", response_model=GeocodingResponse, status_code=200)
async def geocode(
    request: GeocodingRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    주소를 위도/경도로 변환 (카카오 API)

    - 인증: X-API-Key 헤더 필요
    - POST /api/geocode
    - Body: {"address": "서울시 강남구 테헤란로 123"}
    - 성공: 200 + GeocodingResponse
    - 실패: 404 (주소 못 찾음), 401 (인증 실패)
    """
    logger.info(f"Geocoding 요청: address='{request.address}'")

    try:
        result = await geocode_with_kakao(request.address)
        return GeocodingResponse(
            address=request.address,
            latitude=result.latitude,
            longitude=result.longitude,
            provider=result.provider
        )
    except CustomError as error:
        raise HTTPException(status_code=404, detail=error.message)

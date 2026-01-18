"""src.services.geocoding_service
주소 → 위도/경도 변환 (Geocoding) 서비스
"""
import logging
from dataclasses import dataclass

from src.core.config import settings
from src.core.exceptions import CustomError
from src.utils.common import http_get_json

logger = logging.getLogger(__name__)


@dataclass
class GeocodingResult:
    """Geocoding 결과"""
    latitude: float
    longitude: float
    provider: str


async def geocode_with_kakao(address: str) -> GeocodingResult:
    """
    카카오 로컬 API로 Geocoding

    https://developers.kakao.com/docs/latest/ko/local/dev-guide#address-coord

    Args:
        address: 변환할 주소 문자열

    Returns:
        GeocodingResult: 위도, 경도, 제공자 정보

    Raises:
        CustomError: 주소를 찾을 수 없거나 API 오류 시
    """
    logger.info(f"카카오 Geocoding 요청: address='{address}'")

    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}
    params = {"query": address}

    data = await http_get_json(url, params=params, headers=headers)

    if data.get("documents"):
        document = data["documents"][0]
        result = GeocodingResult(
            latitude=float(document["y"]),
            longitude=float(document["x"]),
            provider="kakao"
        )
        logger.info(f"카카오 Geocoding 성공: lat={result.latitude}, lon={result.longitude}")
        return result

    logger.warning(f"카카오 Geocoding 결과 없음: address='{address}'")
    raise CustomError(f"주소를 찾을 수 없습니다: {address}")


async def geocode_with_nominatim(address: str) -> GeocodingResult:
    """
    Nominatim (OpenStreetMap) API로 Geocoding

    Rate limit: 1 request/second
    https://nominatim.org/release-docs/develop/api/Search/

    Args:
        address: 변환할 주소 문자열

    Returns:
        GeocodingResult: 위도, 경도, 제공자 정보

    Raises:
        CustomError: 주소를 찾을 수 없거나 API 오류 시
    """
    logger.info(f"Nominatim Geocoding 요청: address='{address}'")

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "MapSee-AI/1.0"}

    data = await http_get_json(url, params=params, headers=headers)

    if data:
        result = GeocodingResult(
            latitude=float(data[0]["lat"]),
            longitude=float(data[0]["lon"]),
            provider="nominatim"
        )
        logger.info(f"Nominatim Geocoding 성공: lat={result.latitude}, lon={result.longitude}")
        return result

    logger.warning(f"Nominatim Geocoding 결과 없음: address='{address}'")
    raise CustomError(f"주소를 찾을 수 없습니다: {address}")


async def geocode_with_fallback(address: str) -> GeocodingResult | None:
    """
    Kakao → Nominatim 순서로 Geocoding 시도 (fallback 로직)

    실패해도 예외를 발생시키지 않고 None 반환

    Args:
        address: 변환할 주소 문자열

    Returns:
        GeocodingResult | None: 성공 시 결과, 모두 실패 시 None
    """
    # 1. Kakao API 시도
    try:
        return await geocode_with_kakao(address)
    except CustomError:
        logger.warning(f"카카오 Geocoding 실패, Nominatim으로 fallback: address='{address}'")

    # 2. Nominatim fallback
    try:
        return await geocode_with_nominatim(address)
    except CustomError:
        logger.warning(f"Nominatim Geocoding도 실패: address='{address}'")

    return None

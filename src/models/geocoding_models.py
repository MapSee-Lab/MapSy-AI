"""src.models.geocoding_models
Geocoding API 요청/응답 스키마
"""
from enum import Enum
from pydantic import BaseModel, Field


class GeocodingProvider(str, Enum):
    """Geocoding 제공자"""
    KAKAO = "kakao"
    NOMINATIM = "nominatim"


class GeocodingRequest(BaseModel):
    """메인 API 요청 (카카오 전용)"""
    address: str = Field(..., description="변환할 주소", min_length=1)


class GeocodingTestRequest(BaseModel):
    """테스트 API 요청 (provider 선택 가능)"""
    address: str = Field(..., description="변환할 주소", min_length=1)
    provider: GeocodingProvider = Field(
        default=GeocodingProvider.KAKAO,
        description="Geocoding 제공자 선택"
    )


class GeocodingResponse(BaseModel):
    """Geocoding 응답"""
    address: str = Field(..., description="입력된 주소")
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")
    provider: str = Field(..., description="사용된 제공자")

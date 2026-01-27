"""src.models.callback_request.py
AI -> 백엔드 콜백 요청 DTO

통합 장소 검색 결과를 백엔드에 전달하기 위한 모델들입니다.
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional
from uuid import UUID


class SnsInfoCallback(BaseModel):
    """SNS 콘텐츠 메타데이터 (콜백용)"""
    platform: Literal["INSTAGRAM", "YOUTUBE", "YOUTUBE_SHORTS", "TIKTOK", "FACEBOOK", "TWITTER"] = Field(
        ..., description="SNS 플랫폼"
    )
    contentType: str = Field(..., description="콘텐츠 타입 (post, reel, video, shorts 등)")
    url: str = Field(..., description="원본 URL")
    author: Optional[str] = Field(default=None, description="작성자")
    caption: Optional[str] = Field(default=None, description="게시물 본문")
    likesCount: Optional[int] = Field(default=None, description="좋아요 수")
    commentsCount: Optional[int] = Field(default=None, description="댓글 수")
    postedAt: Optional[str] = Field(default=None, description="게시 날짜")
    hashtags: List[str] = Field(default_factory=list, description="해시태그 리스트")
    thumbnailUrl: Optional[str] = Field(default=None, description="대표 이미지 URL")
    imageUrls: List[str] = Field(default_factory=list, description="이미지 URL 리스트")
    authorProfileImageUrl: Optional[str] = Field(default=None, description="작성자 프로필 이미지 URL")


class PlaceDetailCallback(BaseModel):
    """네이버 지도 장소 상세 정보 (콜백용)"""
    # 필수 정보
    placeId: str = Field(..., description="네이버 Place ID")
    name: str = Field(..., description="장소명")

    # 위치 정보
    latitude: Optional[float] = Field(default=None, description="위도")
    longitude: Optional[float] = Field(default=None, description="경도")
    address: Optional[str] = Field(default=None, description="주소")
    roadAddress: Optional[str] = Field(default=None, description="도로명 주소")

    # 카테고리/설명
    category: Optional[str] = Field(default=None, description="카테고리")
    description: Optional[str] = Field(default=None, description="한줄 설명")

    # 평점/리뷰
    rating: Optional[float] = Field(default=None, description="별점 (0.0 ~ 5.0)")
    visitorReviewCount: Optional[int] = Field(default=None, description="방문자 리뷰 수")
    blogReviewCount: Optional[int] = Field(default=None, description="블로그 리뷰 수")

    # 영업 정보
    businessStatus: Optional[str] = Field(default=None, description="영업 상태")
    businessHours: Optional[str] = Field(default=None, description="영업 시간 요약")
    openHoursDetail: List[str] = Field(default_factory=list, description="요일별 상세 영업시간")
    holidayInfo: Optional[str] = Field(default=None, description="휴무일 정보")

    # 연락처/링크
    phoneNumber: Optional[str] = Field(default=None, description="전화번호")
    homepageUrl: Optional[str] = Field(default=None, description="홈페이지 URL")
    naverMapUrl: Optional[str] = Field(default=None, description="네이버 지도 URL")
    reservationAvailable: bool = Field(default=False, description="예약 가능 여부")

    # 부가 정보
    subwayInfo: Optional[str] = Field(default=None, description="지하철 정보")
    directionsText: Optional[str] = Field(default=None, description="찾아가는 길")
    amenities: List[str] = Field(default_factory=list, description="편의시설 목록")
    keywords: List[str] = Field(default_factory=list, description="키워드/태그")
    tvAppearances: List[str] = Field(default_factory=list, description="TV 방송 출연 정보")
    menuInfo: List[str] = Field(default_factory=list, description="대표 메뉴")

    # 이미지
    imageUrl: Optional[str] = Field(default=None, description="대표 이미지 URL")
    imageUrls: List[str] = Field(default_factory=list, description="이미지 URL 목록")


class ExtractionStatistics(BaseModel):
    """추출 처리 통계"""
    extractedPlaceNames: List[str] = Field(default_factory=list, description="LLM이 추출한 장소명 리스트")
    totalExtracted: int = Field(default=0, description="LLM이 추출한 장소 수")
    totalFound: int = Field(default=0, description="네이버 지도에서 찾은 장소 수")
    failedSearches: List[str] = Field(default_factory=list, description="검색 실패한 장소명")


class AiCallbackRequest(BaseModel):
    """AI 서버 → 백엔드 콜백 요청"""
    contentId: UUID = Field(..., description="Content UUID")
    resultStatus: Literal["SUCCESS", "FAILED"] = Field(..., description="처리 결과 상태")

    # SNS 정보
    snsInfo: Optional[SnsInfoCallback] = Field(default=None, description="SNS 콘텐츠 정보")

    # 장소 정보 리스트
    placeDetails: List[PlaceDetailCallback] = Field(default_factory=list, description="장소 상세 정보 리스트")

    # 추출 통계
    statistics: Optional[ExtractionStatistics] = Field(default=None, description="추출 처리 통계")

    # 에러 정보 (FAILED 시)
    errorMessage: Optional[str] = Field(default=None, description="실패 시 에러 메시지")

    @model_validator(mode="after")
    def validate_success_payload(cls, model: "AiCallbackRequest") -> "AiCallbackRequest":
        if model.resultStatus == "SUCCESS":
            if model.snsInfo is None:
                raise ValueError("snsInfo is required when resultStatus is SUCCESS")
        else:
            # FAILED 시 placeDetails 비우기
            model.placeDetails = []
        return model

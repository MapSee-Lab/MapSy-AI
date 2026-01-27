"""src.services.background_tasks.py
비동기로 통합 장소 검색 파이프라인을 실행하고 완료 결과를 백엔드에 callback으로 전달하는 모듈입니다.
"""

import logging
import httpx

from src.core.config import settings
from src.services.integrated_workflow import run_integrated_workflow
from src.models.place_extraction_request import PlaceExtractionRequest
from src.models.callback_request import (
    AiCallbackRequest,
    SnsInfoCallback,
    PlaceDetailCallback,
    ExtractionStatistics
)
from src.models.naver_place_info import NaverPlaceInfo

logging.getLogger("httpx").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def convert_platform_to_callback_format(platform: str) -> str:
    """플랫폼 문자열을 콜백 형식으로 변환"""
    platform_upper = platform.upper()
    if platform_upper in ["INSTAGRAM", "YOUTUBE", "YOUTUBE_SHORTS", "TIKTOK", "FACEBOOK", "TWITTER"]:
        return platform_upper
    # 기본값
    return "INSTAGRAM"


def convert_sns_data_to_callback(sns_data: dict, url: str) -> SnsInfoCallback:
    """SNS 스크래핑 데이터를 콜백용 모델로 변환"""
    platform = convert_platform_to_callback_format(sns_data.get("platform", "instagram"))

    return SnsInfoCallback(
        platform=platform,
        contentType=sns_data.get("content_type", "unknown"),
        url=sns_data.get("url", url),
        author=sns_data.get("author"),
        caption=sns_data.get("caption"),
        likesCount=sns_data.get("likes_count"),
        commentsCount=sns_data.get("comments_count"),
        postedAt=sns_data.get("posted_at"),
        hashtags=sns_data.get("hashtags", []),
        thumbnailUrl=sns_data.get("og_image"),
        imageUrls=sns_data.get("image_urls", []),
        authorProfileImageUrl=sns_data.get("author_profile_image_url")
    )


def convert_naver_place_to_callback(place: NaverPlaceInfo) -> PlaceDetailCallback:
    """NaverPlaceInfo를 콜백용 모델로 변환"""
    return PlaceDetailCallback(
        placeId=place.place_id,
        name=place.name,
        latitude=place.latitude,
        longitude=place.longitude,
        address=place.address,
        roadAddress=place.road_address,
        category=place.category,
        description=place.description,
        rating=place.rating,
        visitorReviewCount=place.visitor_review_count,
        blogReviewCount=place.blog_review_count,
        businessStatus=place.business_status,
        businessHours=place.business_hours,
        openHoursDetail=place.open_hours_detail,
        holidayInfo=place.holiday_info,
        phoneNumber=place.phone_number,
        homepageUrl=place.homepage_url,
        naverMapUrl=place.naver_map_url,
        reservationAvailable=place.reservation_available,
        subwayInfo=place.subway_info,
        directionsText=place.directions_text,
        amenities=place.amenities,
        keywords=place.keywords,
        tvAppearances=place.tv_appearances,
        menuInfo=place.menu_info,
        imageUrl=place.image_url,
        imageUrls=place.image_urls
    )


async def send_callback(payload: AiCallbackRequest) -> bool:
    """
    백엔드 콜백 API로 최종 결과를 전송합니다.

    Args:
        payload: 콜백 요청 페이로드

    Returns:
        bool: 전송 성공 여부
    """
    url = settings.BACKEND_CALLBACK_URL
    logger.info(f"[Callback] 전송 준비: {url} (Status: {payload.resultStatus})")

    headers = {
        "X-API-Key": settings.BACKEND_API_KEY
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json=payload.model_dump(mode="json"),
                headers=headers
            )

        if 200 <= response.status_code < 300:
            logger.info(f"[Callback] 완료: {response.status_code}")
            logger.info(f"[Callback] 응답 본문: {response.text}")
            return True
        else:
            logger.error(f"[Callback] 전송 실패 (HTTP {response.status_code}): {response.text}")
            return False

    except httpx.TimeoutException:
        logger.error("[Callback] 전송 실패: HTTP 요청 타임아웃 발생")
        return False
    except Exception as error:
        logger.error(f"[Callback] 전송 중 예외 발생: {type(error).__name__} - {str(error)}")
        return False


async def send_failed_callback(request: PlaceExtractionRequest, error: Exception) -> bool:
    """
    예외 발생 시 FAILED 상태의 콜백을 전송합니다.

    Args:
        request: 원본 요청
        error: 발생한 예외

    Returns:
        bool: 전송 성공 여부
    """
    # URL에서 플랫폼 추출
    url = request.snsUrl.lower()
    if "youtube.com" in url or "youtu.be" in url:
        platform = "YOUTUBE"
    elif "instagram.com" in url:
        platform = "INSTAGRAM"
    else:
        platform = "INSTAGRAM"

    failed_payload = AiCallbackRequest(
        contentId=request.contentId,
        resultStatus="FAILED",
        snsInfo=None,
        placeDetails=[],
        statistics=None,
        errorMessage=str(error)
    )

    return await send_callback(failed_payload)


async def process_extraction_in_background(request: PlaceExtractionRequest) -> bool:
    """
    백엔드에서 전달받은 장소 추출 요청을 처리하고,
    완료되면 콜백으로 결과를 전송합니다.

    Args:
        request: 장소 추출 요청 (contentId, snsUrl)

    Returns:
        bool: 처리 및 콜백 전송 성공 여부
    """
    try:
        logger.info(f"[Background] 시작: contentId={request.contentId}, url={request.snsUrl}")

        # 통합 워크플로우 실행
        result = await run_integrated_workflow(request.contentId, request.snsUrl)

        logger.info(f"[Background] 워크플로우 완료: 총 {len(result.place_details)}개 장소 발견")

        # SNS 정보 변환
        sns_info = convert_sns_data_to_callback(result.sns_data, request.snsUrl)

        # 장소 정보 변환
        place_details = [
            convert_naver_place_to_callback(place)
            for place in result.place_details
        ]

        # 통계 정보 구성
        statistics = ExtractionStatistics(
            extractedPlaceNames=result.extracted_place_names,
            totalExtracted=len(result.extracted_place_names),
            totalFound=len(result.place_details),
            failedSearches=result.failed_searches
        )

        # 콜백 페이로드 구성
        callback_payload = AiCallbackRequest(
            contentId=request.contentId,
            resultStatus="SUCCESS",
            snsInfo=sns_info,
            placeDetails=place_details,
            statistics=statistics
        )

        # 콜백 전송 전 로깅
        logger.info(f"[Background] 콜백 페이로드 구성 완료:")
        logger.info(f"  - contentId: {callback_payload.contentId}")
        logger.info(f"  - snsInfo.platform: {sns_info.platform}")
        logger.info(f"  - snsInfo.author: {sns_info.author}")
        logger.info(f"  - placeDetails 수: {len(place_details)}")
        logger.info(f"  - statistics.totalExtracted: {statistics.totalExtracted}")
        logger.info(f"  - statistics.totalFound: {statistics.totalFound}")

        # 콜백 전송
        callback_success = await send_callback(callback_payload)

        return callback_success

    except Exception as error:
        logger.exception("[Background] 예외 발생")

        # FAILED 콜백 전송
        await send_failed_callback(request, error)

        return False

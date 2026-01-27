"""src.apis.place_router
장소 추출 API 라우터
"""
import asyncio
import logging
from fastapi import APIRouter, Depends

from src.models import PlaceExtractionRequest
from src.utils.common import verify_api_key
from src.services.background_tasks import process_extraction_in_background

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI 서버 API"])


@router.post("/extract-places", status_code=200)
async def extract_places(
    request: PlaceExtractionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    인증(API Key): 필요

    기능
    SNS 콘텐츠 URL과 contentId를 입력받아 통합 장소 검색 파이프라인을 비동기 방식으로 실행합니다.
    요청은 즉시 200 OK를 반환하며, 실제 처리 결과는 백엔드의 `/api/ai/callback`으로 전송됩니다.

    ------------------------------------------------------------
    파이프라인
    1. SNS 스크래핑 (Playwright) - 메타데이터 및 캡션 추출
    2. LLM 장소명 추출 (Ollama) - 캡션에서 장소명 추출
    3. 네이버 지도 검색 - 장소 상세 정보 획득

    ------------------------------------------------------------
    요청 파라미터 (PlaceExtractionRequest)
    - contentId (UUID): 콘텐츠 고유 식별자
    - snsUrl (string): SNS 원본 URL (Instagram, YouTube 등)

    ------------------------------------------------------------
    반환값 (즉시 응답)
    ```json
    {
      "received": true,
      "message": "Processing started"
    }
    ```

    ------------------------------------------------------------
    콜백 응답 (비동기 - /api/ai/callback)

    SUCCESS 시:
    ```json
    {
      "contentId": "UUID",
      "resultStatus": "SUCCESS",
      "snsInfo": {
        "platform": "INSTAGRAM",
        "contentType": "reel",
        "url": "...",
        "author": "username",
        "caption": "게시물 본문",
        "likesCount": 1234,
        "commentsCount": 56,
        "hashtags": ["태그1", "태그2"],
        "thumbnailUrl": "...",
        "imageUrls": ["..."],
        "authorProfileImageUrl": "..."
      },
      "placeDetails": [
        {
          "placeId": "11679241",
          "name": "장소명",
          "latitude": 37.5112,
          "longitude": 127.0867,
          "address": "주소",
          "category": "카테고리",
          "rating": 4.42,
          "businessStatus": "영업 중",
          "phoneNumber": "02-xxx-xxxx",
          "naverMapUrl": "https://map.naver.com/..."
        }
      ],
      "statistics": {
        "extractedPlaceNames": ["장소1", "장소2"],
        "totalExtracted": 2,
        "totalFound": 1,
        "failedSearches": ["장소2"]
      }
    }
    ```

    FAILED 시:
    ```json
    {
      "contentId": "UUID",
      "resultStatus": "FAILED",
      "errorMessage": "에러 메시지"
    }
    ```

    ------------------------------------------------------------
    에러 코드
    - 인증 실패 시: 401 UNAUTHORIZED (API Key 누락 또는 불일치)
    """

    logger.info(
        f"extract-places 요청 수신: contentId={request.contentId}, url={request.snsUrl}"
    )

    # 비동기 백그라운드 처리 시작
    asyncio.create_task(
        process_extraction_in_background(request)
    )

    # 즉시 응답 반환
    return {
        "received": True,
        "message": "Processing started"
    }

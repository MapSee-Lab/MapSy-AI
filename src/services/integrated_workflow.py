"""src.services.integrated_workflow.py
통합 장소 검색 워크플로우

Instagram URL에서 장소 정보를 통합 추출하는 파이프라인:
1. SNS 스크래핑 (Playwright)
2. LLM 장소명 추출 (Ollama)
3. 네이버 지도 검색
"""

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.services.scraper.scrape_router import route_and_scrape
from src.services.scraper.platforms.naver_map_scraper import NaverMapScraper
from src.services.modules.ollama_llm import extract_place_names_with_ollama
from src.models.naver_place_info import NaverPlaceInfo

logger = logging.getLogger(__name__)


@dataclass
class IntegratedWorkflowResult:
    """통합 워크플로우 결과"""
    sns_data: dict  # SNS 스크래핑 결과 (platform, content_type, author, caption 등)
    extracted_place_names: list[str]  # LLM이 추출한 장소명
    has_places: bool  # 장소 존재 여부
    place_details: list[NaverPlaceInfo]  # 네이버 지도 검색 결과
    failed_searches: list[str]  # 검색 실패한 장소명


async def run_integrated_workflow(content_id: UUID, sns_url: str) -> IntegratedWorkflowResult:
    """
    통합 장소 검색 워크플로우 실행

    Args:
        content_id: 콘텐츠 UUID (로깅용)
        sns_url: SNS URL (Instagram/YouTube)

    Returns:
        IntegratedWorkflowResult: 워크플로우 결과

    Raises:
        Exception: SNS 스크래핑 실패 시
    """
    logger.info(f"[통합 워크플로우] 시작 - contentId={content_id}, url={sns_url}")

    # Step 1: SNS 스크래핑
    logger.info("[통합 워크플로우] Step 1/3: SNS 스크래핑 시작")
    sns_data = await route_and_scrape(sns_url)
    logger.info(f"[통합 워크플로우] Step 1/3: SNS 스크래핑 완료 - platform={sns_data.get('platform')}, author={sns_data.get('author')}")

    # Step 2: LLM 장소명 추출
    caption = sns_data.get("caption") or ""
    logger.info(f"[통합 워크플로우] Step 2/3: LLM 장소명 추출 시작 - caption 길이={len(caption)}")

    if not caption.strip():
        logger.info("[통합 워크플로우] Step 2/3: caption이 비어있어 장소 추출 스킵")
        extracted_place_names = []
        has_places = False
    else:
        llm_result = await extract_place_names_with_ollama(caption)
        extracted_place_names = llm_result.place_names
        has_places = llm_result.has_places
        logger.info(f"[통합 워크플로우] Step 2/3: LLM 장소명 추출 완료 - 추출된 장소 수={len(extracted_place_names)}")

    # Step 3: 네이버 지도 검색
    place_details: list[NaverPlaceInfo] = []
    failed_searches: list[str] = []

    if extracted_place_names:
        logger.info(f"[통합 워크플로우] Step 3/3: 네이버 지도 검색 시작 - 검색할 장소 수={len(extracted_place_names)}")
        scraper = NaverMapScraper()

        for index, place_name in enumerate(extracted_place_names, 1):
            logger.info(f"[통합 워크플로우] Step 3/3: 네이버 지도 검색 ({index}/{len(extracted_place_names)}) - query={place_name}")
            try:
                place_info = await scraper.search_and_scrape(place_name)
                place_details.append(place_info)
                logger.info(f"[통합 워크플로우] Step 3/3: 검색 성공 - {place_info.name} ({place_info.place_id})")
            except Exception as error:
                logger.warning(f"[통합 워크플로우] Step 3/3: 검색 실패 - query={place_name}, error={error}")
                failed_searches.append(place_name)

        logger.info(f"[통합 워크플로우] Step 3/3: 네이버 지도 검색 완료 - 성공={len(place_details)}, 실패={len(failed_searches)}")
    else:
        logger.info("[통합 워크플로우] Step 3/3: 추출된 장소가 없어 네이버 지도 검색 스킵")

    logger.info(f"[통합 워크플로우] 완료 - contentId={content_id}, 총 추출={len(extracted_place_names)}, 총 발견={len(place_details)}")

    return IntegratedWorkflowResult(
        sns_data=sns_data,
        extracted_place_names=extracted_place_names,
        has_places=has_places,
        place_details=place_details,
        failed_searches=failed_searches
    )

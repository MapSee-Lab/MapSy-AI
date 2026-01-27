"""src.services.modules.ollama_llm
Ollama API를 사용하여 텍스트에서 장소명을 추출합니다.
ai.suhsaechan.kr 서버의 gemma3:1b-it-qat 모델을 사용합니다.
"""

import json
import logging
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.exceptions import CustomError
from src.utils.common import http_post_json

logger = logging.getLogger(__name__)


# =============================================
# Pydantic 모델
# =============================================
class OllamaPlaceResult(BaseModel):
    """Ollama 장소명 추출 결과"""
    place_names: list[str] = Field(default_factory=list, description="추출된 장소명 리스트")
    has_places: bool = Field(default=False, description="장소 존재 여부")


# =============================================
# JSON Schema (Ollama format 파라미터용)
# =============================================
PLACE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "place_names": {
            "type": "array",
            "items": {"type": "string"}
        },
        "has_places": {
            "type": "boolean"
        }
    },
    "required": ["place_names", "has_places"],
    "additionalProperties": False
}


# =============================================
# 프롬프트 템플릿
# =============================================
PLACE_EXTRACTION_PROMPT = """다음 텍스트에서 장소명(가게명, 상호명, 식당명, 카페명, 관광지명 등)을 추출하세요.

장소명 예시:
- 스타벅스 종합운동장사거리점
- 블루보틀 성수
- 스시호
- 사사노하

규칙:
1. 텍스트에 언급된 실제 장소명만 추출하세요.
2. 해시태그(#)가 붙어있어도 장소명이면 추출하세요. (#스시호 → 스시호)
3. 일반 명사(맛집, 초밥, 카페 등)는 장소명이 아닙니다.
4. 장소가 없으면 빈 배열 []을 반환하세요.

<Context>
{caption}
</Context>"""


# =============================================
# Ollama API 호출 함수
# =============================================
async def extract_place_names_with_ollama(
    caption: str,
    max_retries: int = 3
) -> OllamaPlaceResult:
    """
    Ollama API를 사용하여 텍스트에서 장소명을 추출합니다.

    Args:
        caption: 인스타그램 게시물 본문 텍스트
        max_retries: 최대 재시도 횟수 (기본 3회)

    Returns:
        OllamaPlaceResult: 추출된 장소명 리스트와 존재 여부

    Raises:
        CustomError: API 호출 실패 또는 파싱 실패 시
    """
    if not caption or not caption.strip():
        logger.warning("빈 caption이 전달되었습니다.")
        return OllamaPlaceResult(place_names=[], has_places=False)

    prompt = PLACE_EXTRACTION_PROMPT.format(caption=caption)

    request_body = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "format": PLACE_EXTRACTION_SCHEMA
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": settings.OLLAMA_API_KEY
    }

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Ollama API 호출 시도 {attempt}/{max_retries} (model={settings.OLLAMA_MODEL})")

            response = await http_post_json(
                url=settings.OLLAMA_API_URL,
                json_body=request_body,
                headers=headers
            )

            # 응답에서 content 추출
            message = response.get("message", {})
            content = message.get("content", "")

            if not content:
                logger.warning(f"Ollama 응답에 content가 없습니다: {response}")
                last_error = CustomError("Ollama 응답에 content가 없습니다")
                continue

            # JSON 파싱
            try:
                parsed = json.loads(content)
                result = OllamaPlaceResult.model_validate(parsed)

                logger.info(f"장소명 추출 성공: {result.place_names}")
                return result

            except json.JSONDecodeError as json_error:
                logger.warning(f"JSON 파싱 실패 (시도 {attempt}): {json_error}")
                last_error = CustomError(f"JSON 파싱 실패: {json_error}")
                continue

        except CustomError as error:
            logger.warning(f"Ollama API 호출 실패 (시도 {attempt}): {error.message}")
            last_error = error
            continue

        except Exception as error:
            logger.error(f"예기치 않은 오류 (시도 {attempt}): {error}")
            last_error = CustomError(f"예기치 않은 오류: {error}")
            continue

    # 모든 재시도 실패
    logger.error(f"Ollama API 호출 {max_retries}회 모두 실패")

    # 실패 시 빈 결과 반환 (에러를 던지지 않음)
    return OllamaPlaceResult(place_names=[], has_places=False)

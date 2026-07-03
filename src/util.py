"""소소한 유틸 — LLM 응답 정규화, JSON 안전 추출."""
from __future__ import annotations

import json
import re


def text_of(resp) -> str:
    """LLM 응답을 항상 문자열로. 일부 모델(신형 lite 등)은 content 를
    문자열이 아닌 콘텐츠 블록 리스트([{'type':'text','text':...}])로 반환한다."""
    c = getattr(resp, "content", resp)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in c
        )
    return str(c)


def extract_json(text: str):
    """LLM 응답에서 JSON(배열/객체)만 뽑아 파싱. 코드펜스·잡텍스트 제거."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", t, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        raise

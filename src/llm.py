"""Gemini LLM · 임베딩 래퍼 (LangChain 경유).

LangChain 이 공급자를 추상화하므로, Claude/OpenAI 로 바꾸거나 노드별로
모델 티어를 달리 하고 싶을 때 이 파일만 고치면 된다.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# 이 리포 루트의 .env 만 명시적으로 읽는다 — CWD 기준 상위 탐색을 쓰면
# 다른 프로젝트의 .env 를 잘못 읽을 수 있다. override 로 OS 잔여 변수보다 우선.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/gemini-embedding-001")

# 설정 오류/무료티어 미지원 자동 교정. 이 키 티어는 2.0 계열 무료할당량이 0이라
# 무료 할당량이 있는 2.5-flash 로 보정한다(품질도 더 높음).
if "embedding" in CHAT_MODEL or CHAT_MODEL.startswith("gemini-2.0"):
    CHAT_MODEL = "gemini-2.5-flash"
# text-embedding-004 는 일부 신형 키 티어(v1beta)에서 미노출(404). 자동 대체.
if "text-embedding-004" in EMBED_MODEL or "embedding" not in EMBED_MODEL:
    EMBED_MODEL = "models/gemini-embedding-001"


FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-flash-lite-latest")


@lru_cache(maxsize=None)
def get_chat(temperature: float = 0.2):
    """주 모델 + 폴백 체인.

    - max_retries: 분당 한도(429, 수초 내 재시도 가능)를 지수 백오프로 흡수
    - with_fallbacks: 일일 한도(무료 티어 2.5-flash 는 20 req/day) 소진 시
      무료 할당이 남은 lite 모델로 자동 전환 — 실행이 죽지 않는다
    """
    # primary 재시도는 1회만 — 일일 한도 소진 상태에서 재시도로 시간을 끌지 않고
    # 빠르게 폴백으로 넘어간다. 분당 한도성 429 흡수는 fallback 쪽에 맡긴다.
    primary = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=temperature, max_retries=1)
    fallback = ChatGoogleGenerativeAI(model=FALLBACK_MODEL, temperature=temperature, max_retries=6)
    return primary.with_fallbacks([fallback])


@lru_cache(maxsize=1)
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(model=EMBED_MODEL)

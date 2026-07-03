"""RAG 인덱스 구축 — docs/*.md 를 청크·임베딩하여 Chroma 에 저장.

실행:  python data/build_index.py   (사전에 .env 의 GOOGLE_API_KEY 필요)
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from langchain_chroma import Chroma  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

from src.llm import get_embeddings  # noqa: E402
from src.tools import CHROMA_COLLECTION, CHROMA_DIR  # noqa: E402

DOCS = REPO / "data" / "docs"

META = {
    "sop_rtp.md": {"process": "RTP", "equipment": "RTP", "doctype": "SOP"},
    "sop_ion_implant.md": {"process": "Implant", "equipment": "IMP", "doctype": "SOP"},
    "sop_deposition.md": {"process": "Deposition", "equipment": "DEP", "doctype": "SOP"},
    "sop_clean.md": {"process": "Clean", "equipment": "CLN", "doctype": "SOP"},
    "fdc_alarm_guide.md": {"process": "공통", "equipment": "FDC", "doctype": "가이드"},
    "yield_cost_glossary.md": {"process": "공통", "equipment": "-", "doctype": "용어"},
    "issue_rtp_peaktemp_2025.md": {"process": "RTP", "equipment": "RTP-01", "doctype": "이슈리포트"},
    "issue_deposition_particle_2025.md": {"process": "Deposition", "equipment": "DEP-03", "doctype": "이슈리포트"},
}


def build():
    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    texts, metas = [], []
    for md in sorted(DOCS.glob("*.md")):
        meta = META.get(md.name, {"process": "?", "equipment": "?", "doctype": "?"})
        meta = {**meta, "source": md.name}
        for chunk in splitter.split_text(md.read_text(encoding="utf-8")):
            texts.append(chunk)
            metas.append(meta)

    vs = Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )
    try:
        vs.delete_collection()
    except Exception:
        pass
    vs = Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )
    vs.add_texts(texts=texts, metadatas=metas)
    print(f"indexed {len(texts)} chunks from {len(list(DOCS.glob('*.md')))} docs → {CHROMA_DIR}")


if __name__ == "__main__":
    build()

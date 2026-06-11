"""Q&A API — dual-path grounded answers (US9 / FR-018).

Numeric answers are computed in code from real rows; semantic answers come from
real retrieved rows; anything else is an explicit "not available". The LLM never
computes a figure.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.services import persistence
from src.services.persistence import PersistenceError
from src.services.qa_service import answer_question

logger = logging.getLogger("billology.qa")
router = APIRouter(tags=["qa"])


class QARequest(BaseModel):
    question: str


def _embed_fn():
    # Lazy: only import the embedder when a semantic question actually needs it.
    from src.services.embedding_service import embed

    return embed


def _llm():
    try:
        from src.services.llm_service import get_llm_service

        return get_llm_service()
    except Exception:
        return None


@router.post("/qa")
def ask(req: QARequest):
    try:
        result = answer_question(
            req.question, db=persistence, embed_fn=_embed_fn(), llm=_llm()
        )
    except PersistenceError as exc:
        logger.error("qa persistence error: %s", exc)
        return JSONResponse(status_code=502, content={"error": "persist_failed", "detail": str(exc)})
    return result

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .notice_search_models import (
    NoticeSearchFilters,
    NoticeSearchResponse,
    NoticeSearchResultItem,
    SearchMode,
)
from .notice_search_tools import NoticeSearchTool, SemanticSearchTool, TextSqlSearchTool

logger = logging.getLogger(__name__)


class NoticeSearchState(TypedDict, total=False):
    query: str
    filters: NoticeSearchFilters
    top_k: int
    include_reason: bool
    text_results: list[NoticeSearchResultItem]
    semantic_results: list[NoticeSearchResultItem]
    text_error: str | None
    semantic_error: str | None
    results: list[NoticeSearchResultItem]
    mode: SearchMode
    errors: list[str]


def _recency_score(posted_date: date | None) -> float:
    if posted_date is None:
        return 0.0
    days = max((date.today() - posted_date).days, 0)
    return 1.0 / (1.0 + (days / 30.0))


class NoticeSearchService:
    def __init__(
        self,
        *,
        text_sql_tool: NoticeSearchTool | None = None,
        semantic_tool: NoticeSearchTool | None = None,
    ) -> None:
        self.text_sql_tool = text_sql_tool or TextSqlSearchTool()
        self.semantic_tool = semantic_tool or SemanticSearchTool()
        self._graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(NoticeSearchState)
        workflow.add_node("text_sql_search", self._text_sql_search_node)
        workflow.add_node("semantic_search", self._semantic_search_node)
        workflow.add_node("merge", self._merge_node)
        workflow.add_edge(START, "text_sql_search")
        workflow.add_edge(START, "semantic_search")
        workflow.add_edge("text_sql_search", "merge")
        workflow.add_edge("semantic_search", "merge")
        workflow.add_edge("merge", END)
        return workflow.compile()

    async def _text_sql_search_node(
        self, state: NoticeSearchState
    ) -> NoticeSearchState:
        try:
            results = await self.text_sql_tool.search(
                query=state.get("query", ""),
                filters=state.get("filters", NoticeSearchFilters()),
                top_k=state.get("top_k", 10),
            )
            return {"text_results": results, "text_error": None}
        except Exception as exc:
            logger.exception("text_sql_search failed")
            return {"text_results": [], "text_error": repr(exc)}

    async def _semantic_search_node(
        self, state: NoticeSearchState
    ) -> NoticeSearchState:
        try:
            results = await self.semantic_tool.search(
                query=state.get("query", ""),
                filters=state.get("filters", NoticeSearchFilters()),
                top_k=state.get("top_k", 10),
            )
            return {"semantic_results": results, "semantic_error": None}
        except Exception as exc:
            logger.exception("semantic_search failed")
            return {"semantic_results": [], "semantic_error": repr(exc)}

    def _merge_node(self, state: NoticeSearchState) -> NoticeSearchState:
        text_results = state.get("text_results", [])
        semantic_results = state.get("semantic_results", [])
        top_k = state.get("top_k", 10)
        include_reason = state.get("include_reason", True)

        merged: dict[int, NoticeSearchResultItem] = {}
        for item in text_results:
            merged[item.source_notice_id] = NoticeSearchResultItem(**asdict(item))

        for semantic_item in semantic_results:
            existing = merged.get(semantic_item.source_notice_id)
            if existing is None:
                merged[semantic_item.source_notice_id] = NoticeSearchResultItem(
                    **asdict(semantic_item)
                )
                continue

            existing.semantic_score = max(
                existing.semantic_score, semantic_item.semantic_score
            )
            if semantic_item.keyword_score > existing.keyword_score:
                existing.keyword_score = semantic_item.keyword_score
            for reason in semantic_item.match_reason:
                if reason not in existing.match_reason:
                    existing.match_reason.append(reason)

        ranked: list[NoticeSearchResultItem] = []
        for item in merged.values():
            item.recency_score = _recency_score(item.posted_date)
            item.score = (
                0.50 * item.keyword_score
                + 0.35 * item.semantic_score
                + 0.15 * item.recency_score
            )
            if not include_reason:
                item.match_reason = []
            ranked.append(item)

        ranked.sort(
            key=lambda item: (item.score, item.posted_date or date.min),
            reverse=True,
        )

        if text_results and semantic_results:
            mode: SearchMode = "hybrid"
        elif semantic_results:
            mode = "semantic_only"
        else:
            mode = "sql_only"

        errors: list[str] = []
        text_error = state.get("text_error")
        semantic_error = state.get("semantic_error")
        if text_error:
            errors.append(f"text_sql:{text_error}")
        if semantic_error:
            errors.append(f"semantic:{semantic_error}")

        return {"results": ranked[:top_k], "mode": mode, "errors": errors}

    async def search_notices(
        self,
        *,
        query: str,
        filters: NoticeSearchFilters | None = None,
        top_k: int = 10,
        include_reason: bool = True,
    ) -> dict[str, Any]:
        normalized_filters = filters or NoticeSearchFilters()
        final_state = await self._graph.ainvoke(
            {
                "query": query.strip(),
                "filters": normalized_filters,
                "top_k": max(1, min(top_k, 50)),
                "include_reason": include_reason,
            }
        )

        response = NoticeSearchResponse(
            query=query,
            applied_filters=normalized_filters.to_dict(),
            mode=final_state.get("mode", "sql_only"),
            results=final_state.get("results", []),
            total_returned=len(final_state.get("results", [])),
            errors=final_state.get("errors", []),
        )
        return asdict(response)

from __future__ import annotations

import asyncio
import argparse
import logging
import os
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any, Protocol

from langsmith import traceable
from mcp.server.fastmcp import FastMCP

from notice_chat.db import SessionLocal, close_db, init_db
from notice_chat.models import DBSkuNotice
from notice_chat.observability import configure_langsmith
from notice_chat.repositories import SkuNoticeRepository
from notice_chat.services import NoticeSearchFilters, NoticeSearchService

from .settings import SKU_NOTICE_MCP_SETTINGS, SkuNoticeMCPSettings

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Any]
RepositoryFactory = Callable[[Any], Any]


class NoticeSearchServiceProtocol(Protocol):
    async def search_notices(
        self,
        *,
        query: str,
        filters: NoticeSearchFilters | None = None,
        top_k: int = 10,
        include_reason: bool = True,
    ) -> dict[str, Any]:
        raise NotImplementedError


def _configure_windows_event_loop_policy() -> None:
    """Ensure psycopg async compatibility on Windows."""
    if os.name != "nt":
        return
    policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy_cls is None:
        return
    asyncio.set_event_loop_policy(policy_cls())


def _parse_optional_date(value: str | None, *, field_name: str) -> date | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    try:
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD format") from exc


def _jsonify(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonify(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonify(inner) for inner in value]
    return value


def _serialize_notice(notice: DBSkuNotice) -> dict[str, Any]:
    return _jsonify(
        {
            "id": notice.id,
            "source_notice_id": notice.source_notice_id,
            "detail_url": notice.detail_url,
            "title": notice.title,
            "category": notice.category,
            "author_org": notice.author_org,
            "posted_date": notice.posted_date,
            "status": notice.status,
            "list_number": notice.list_number,
            "period_start": notice.period_start,
            "period_end": notice.period_end,
            "summary_text": notice.summary_text,
            "attachments": notice.attachments,
            "has_embedding": notice.embedding is not None,
            "embedding_updated_at": notice.embedding_updated_at,
            "created_at": notice.created_at,
            "updated_at": notice.updated_at,
        }
    )


def create_notice_mcp_server(
    *,
    settings: SkuNoticeMCPSettings | None = None,
    search_service: NoticeSearchServiceProtocol | None = None,
    session_factory: SessionFactory | None = None,
    repository_factory: RepositoryFactory | None = None,
    enable_lifespan: bool = True,
) -> FastMCP:
    resolved_settings = settings or SKU_NOTICE_MCP_SETTINGS
    resolved_search_service = search_service or NoticeSearchService()
    resolved_session_factory = session_factory or SessionLocal
    resolved_repository_factory = repository_factory or SkuNoticeRepository

    @asynccontextmanager
    async def server_lifespan(_: FastMCP):
        await init_db()
        try:
            yield
        finally:
            await close_db()

    server = FastMCP(
        name=resolved_settings.server_name,
        instructions=(
            "Search and retrieve Seokyeong University notice data stored "
            "in the local PostgreSQL database."
        ),
        host=resolved_settings.host,
        port=resolved_settings.port,
        log_level=resolved_settings.log_level,
        lifespan=server_lifespan if enable_lifespan else None,
    )

    @traceable(name="mcp.search_notices", run_type="tool", tags=["mcp", "notice-search"])
    async def _run_search_notices(
        *,
        query: str,
        top_k: int,
        category: str | None,
        author_org: str | None,
        posted_from: str | None,
        posted_to: str | None,
        status: str | None,
        include_reason: bool,
    ) -> dict[str, Any]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")

        filters = NoticeSearchFilters(
            category=category,
            author_org=author_org,
            posted_from=_parse_optional_date(posted_from, field_name="posted_from"),
            posted_to=_parse_optional_date(posted_to, field_name="posted_to"),
            status=status,
        )
        result = await resolved_search_service.search_notices(
            query=query,
            filters=filters,
            top_k=min(top_k, 50),
            include_reason=include_reason,
        )
        return _jsonify(result)

    @traceable(
        name="mcp.get_notice_detail",
        run_type="tool",
        tags=["mcp", "notice-detail"],
    )
    async def _run_get_notice_detail(*, source_notice_id: int) -> dict[str, Any]:
        if source_notice_id < 1:
            raise ValueError("source_notice_id must be >= 1")

        async with resolved_session_factory() as session:
            repository = resolved_repository_factory(session)
            notice = await repository.get_by_source_notice_id(source_notice_id)

        if notice is None:
            return {"found": False, "notice": None}
        return {"found": True, "notice": _serialize_notice(notice)}

    @traceable(
        name="mcp.list_recent_notices",
        run_type="tool",
        tags=["mcp", "notice-list"],
    )
    async def _run_list_recent_notices(
        *,
        limit: int,
        offset: int,
        category: str | None,
        status: str | None,
    ) -> dict[str, Any]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if offset < 0:
            raise ValueError("offset must be >= 0")

        normalized_limit = min(limit, 100)
        async with resolved_session_factory() as session:
            repository = resolved_repository_factory(session)
            notices: Sequence[DBSkuNotice] = await repository.list(
                limit=normalized_limit,
                offset=offset,
                category=category,
                status=status,
            )

        items = [_serialize_notice(notice) for notice in notices]
        return {
            "count": len(items),
            "limit": normalized_limit,
            "offset": offset,
            "items": items,
        }

    @server.tool(
        name="search_notices",
        description="Search notices with hybrid ranking (keyword + semantic + recency).",
        structured_output=True,
    )
    async def search_notices(
        query: str,
        top_k: int = 10,
        category: str | None = None,
        author_org: str | None = None,
        posted_from: str | None = None,
        posted_to: str | None = None,
        status: str | None = None,
        include_reason: bool = True,
    ) -> dict[str, Any]:
        return await _run_search_notices(
            query=query,
            top_k=top_k,
            category=category,
            author_org=author_org,
            posted_from=posted_from,
            posted_to=posted_to,
            status=status,
            include_reason=include_reason,
        )

    @server.tool(
        name="get_notice_detail",
        description="Get a single notice by source_notice_id.",
        structured_output=True,
    )
    async def get_notice_detail(source_notice_id: int) -> dict[str, Any]:
        return await _run_get_notice_detail(source_notice_id=source_notice_id)

    @server.tool(
        name="list_recent_notices",
        description="List recent notices ordered by posted_date desc.",
        structured_output=True,
    )
    async def list_recent_notices(
        limit: int = 20,
        offset: int = 0,
        category: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        return await _run_list_recent_notices(
            limit=limit,
            offset=offset,
            category=category,
            status=status,
        )

    return server


def run_notice_mcp_server(
    *,
    settings: SkuNoticeMCPSettings | None = None,
) -> None:
    _configure_windows_event_loop_policy()
    configure_langsmith()
    resolved_settings = settings or SKU_NOTICE_MCP_SETTINGS
    logging.basicConfig(level=resolved_settings.log_level)
    server = create_notice_mcp_server(settings=resolved_settings)
    logger.info(
        "Starting MCP server name=%s transport=%s host=%s port=%s",
        resolved_settings.server_name,
        resolved_settings.transport,
        resolved_settings.host,
        resolved_settings.port,
    )
    server.run(transport=resolved_settings.transport)


def _build_settings_from_args() -> SkuNoticeMCPSettings:
    parser = argparse.ArgumentParser(description="Run SKU notice MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default=SKU_NOTICE_MCP_SETTINGS.transport,
    )
    parser.add_argument("--host", default=SKU_NOTICE_MCP_SETTINGS.host)
    parser.add_argument("--port", type=int, default=SKU_NOTICE_MCP_SETTINGS.port)
    parser.add_argument("--server-name", default=SKU_NOTICE_MCP_SETTINGS.server_name)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default=SKU_NOTICE_MCP_SETTINGS.log_level,
    )
    args = parser.parse_args()
    return SkuNoticeMCPSettings(
        server_name=args.server_name,
        transport=args.transport,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


def main() -> None:
    settings = _build_settings_from_args()
    run_notice_mcp_server(settings=settings)


if __name__ == "__main__":
    main()

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ListNoticeItem:
    source_notice_id: int
    detail_url: str
    title: str
    category: str
    author_org: str | None
    posted_date: date | None
    status: str | None
    list_number: int | None


@dataclass(slots=True)
class CrawledNotice:
    source_notice_id: int
    detail_url: str
    title: str
    category: str
    author_org: str | None
    posted_date: date | None
    status: str | None
    list_number: int | None
    period_start: date | None
    period_end: date | None
    raw_text: str
    image_urls: list[str]
    attachments: list[dict[str, Any]]


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def parse_notice_id_from_url(url: str) -> int | None:
    match = re.search(r"/notice/(\d+)", url)
    if match is None:
        return None
    return int(match.group(1))


def parse_date_from_text(value: str | None) -> date | None:
    if not value:
        return None

    text = clean_text(value)
    match = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", text)
    if match is None:
        return None

    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    return date(year, month, day)


def dedupe_by_notice_id(items: list[ListNoticeItem]) -> list[ListNoticeItem]:
    deduped: dict[int, ListNoticeItem] = {}
    for item in items:
        deduped[item.source_notice_id] = item
    return sorted(deduped.values(), key=lambda item: item.source_notice_id, reverse=True)


class SkuNoticeCrawler:
    def __init__(
        self,
        *,
        base_url: str = "https://www.skuniv.ac.kr",
        list_path: str = "/notice",
        user_agent: str | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.list_url = f"{self.base_url}{list_path}"
        self.upload_base_url = f"{self.base_url}/wp-content/uploads"
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
        self.timeout = timeout or httpx.Timeout(30.0, connect=10.0)

    def build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
            follow_redirects=True,
        )

    async def fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    def parse_list_page(self, html: str) -> list[ListNoticeItem]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[ListNoticeItem] = []

        for row in soup.select("table.board-list-table tbody tr"):
            link = row.select_one("td.post-title a[href*='/notice/']")
            if link is None:
                continue

            href = clean_text(link.get("href"))
            detail_url = urljoin(self.base_url, href).split("?", 1)[0].split("#", 1)[0]
            source_notice_id = parse_notice_id_from_url(detail_url)
            if source_notice_id is None:
                continue

            category_node = row.select_one("td.category-badge span")
            category = clean_text(category_node.get_text() if category_node else "") or "unknown"

            status_node = row.select_one("td.post-title .icons .badge span")
            status = clean_text(status_node.get_text()) or None if status_node else None

            number_node = row.select_one("td.number-badge span")
            number_text = clean_text(number_node.get_text()) if number_node else ""
            list_number = int(number_text) if number_text.isdigit() else None

            info_values: list[str] = []
            for div in row.select("td.post-info .post-info-wrap > div"):
                classes = div.get("class", [])
                if "divider" in classes:
                    continue
                info_values.append(clean_text(div.get_text(" ", strip=True)))

            author_org = info_values[0] if len(info_values) >= 1 else None
            posted_date = parse_date_from_text(info_values[1] if len(info_values) >= 2 else None)

            items.append(
                ListNoticeItem(
                    source_notice_id=source_notice_id,
                    detail_url=detail_url,
                    title=clean_text(link.get_text()),
                    category=category,
                    author_org=author_org,
                    posted_date=posted_date,
                    status=status,
                    list_number=list_number,
                )
            )

        return items

    def parse_detail_page(self, html: str, list_item: ListNoticeItem) -> CrawledNotice:
        soup = BeautifulSoup(html, "html.parser")

        title_node = soup.select_one(".post-detail-wrap .title-wrap h3")
        title = clean_text(title_node.get_text()) if title_node else list_item.title

        meta_map: dict[str, str] = {}
        for li in soup.select(".post-detail-wrap .base-meta-data-wrap li"):
            key_node = li.select_one(".meta-title")
            value_node = li.select_one(".meta-value")
            if key_node is None or value_node is None:
                continue
            meta_map[clean_text(key_node.get_text())] = clean_text(value_node.get_text())

        author_org = (
            meta_map.get("작성부서")
            or meta_map.get("작성자")
            or meta_map.get("담당부서")
            or meta_map.get("부서")
            or list_item.author_org
        )
        posted_date = (
            parse_date_from_text(meta_map.get("등록일"))
            or parse_date_from_text(meta_map.get("게시일"))
            or parse_date_from_text(meta_map.get("작성일"))
            or list_item.posted_date
        )

        status_node = soup.select_one(".post-detail-wrap .progress-meta-data-wrap .badge span")
        status = clean_text(status_node.get_text()) if status_node else list_item.status

        period_values = [
            clean_text(node.get_text())
            for node in soup.select(".post-detail-wrap .progress-meta-data-wrap .meta-value")
        ]
        period_start = parse_date_from_text(period_values[0]) if len(period_values) >= 1 else None
        period_end = parse_date_from_text(period_values[1]) if len(period_values) >= 2 else None

        content_wrap = soup.select_one(".post-detail-wrap .post-content-wrap")
        raw_text = clean_text(content_wrap.get_text("\n", strip=True)) if content_wrap else ""

        image_urls: list[str] = []
        if content_wrap is not None:
            for img in content_wrap.select("img"):
                src = clean_text(img.get("src") or "")
                if not src:
                    srcset = clean_text(img.get("srcset") or "")
                    if srcset:
                        src = srcset.split(",", 1)[0].strip().split(" ")[0]
                if not src:
                    continue
                normalized = urljoin(self.base_url, src).replace("http://", "https://", 1)
                image_urls.append(normalized)

        image_urls = list(dict.fromkeys(image_urls))

        attachments: list[dict[str, Any]] = []
        for anchor in soup.select(".post-detail-wrap .attachment-wrap a[data-file-key]"):
            file_key = clean_text(anchor.get("data-file-key") or "").lstrip("/")
            if not file_key:
                continue
            file_name = clean_text(anchor.get_text(" ", strip=True))
            attachments.append(
                {
                    "file_name": file_name,
                    "file_url": f"{self.upload_base_url}/{file_key}",
                }
            )

        return CrawledNotice(
            source_notice_id=list_item.source_notice_id,
            detail_url=list_item.detail_url,
            title=title,
            category=list_item.category,
            author_org=author_org,
            posted_date=posted_date,
            status=status,
            list_number=list_item.list_number,
            period_start=period_start,
            period_end=period_end,
            raw_text=raw_text,
            image_urls=image_urls,
            attachments=attachments,
        )

    async def crawl_notice_list(
        self,
        client: httpx.AsyncClient,
        *,
        pages_to_scan: int = 3,
    ) -> list[ListNoticeItem]:
        all_items: list[ListNoticeItem] = []

        for page in range(1, pages_to_scan + 1):
            page_url = self.list_url if page == 1 else f"{self.list_url}/page/{page}"
            html = await self.fetch_html(client, page_url)
            page_items = self.parse_list_page(html)
            if not page_items:
                logger.info("No list rows found for page=%s; stopping pagination", page)
                break
            all_items.extend(page_items)

        return dedupe_by_notice_id(all_items)

    async def crawl_notice_details(
        self,
        client: httpx.AsyncClient,
        items: list[ListNoticeItem],
        *,
        concurrency: int = 5,
    ) -> list[CrawledNotice]:
        semaphore = asyncio.Semaphore(concurrency)

        async def crawl_one(item: ListNoticeItem) -> CrawledNotice:
            async with semaphore:
                html = await self.fetch_html(client, item.detail_url)
                return self.parse_detail_page(html, item)

        tasks = [crawl_one(item) for item in items]
        return await asyncio.gather(*tasks)

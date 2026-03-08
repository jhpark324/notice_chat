from __future__ import annotations

from datetime import date

from notice_chat.services import ListNoticeItem, SkuNoticeCrawler


def test_parse_list_page_extracts_notice_rows() -> None:
    crawler = SkuNoticeCrawler()
    html = """
    <table class="board-list-table">
      <tbody>
        <tr>
          <td class="number-badge"><span>7</span></td>
          <td class="category-badge"><span>장학</span></td>
          <td class="post-title">
            <a href="/notice/61471"> 2026 장학금 신청 안내 </a>
            <div class="icons"><div class="badge"><span>진행중</span></div></div>
          </td>
          <td class="post-info">
            <div class="post-info-wrap">
              <div>학생처</div>
              <div class="divider">|</div>
              <div>2026-03-07</div>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    """

    items = crawler.parse_list_page(html)

    assert len(items) == 1
    item = items[0]
    assert item.source_notice_id == 61471
    assert item.detail_url == "https://www.skuniv.ac.kr/notice/61471"
    assert item.title == "2026 장학금 신청 안내"
    assert item.category == "장학"
    assert item.author_org == "학생처"
    assert item.posted_date == date(2026, 3, 7)
    assert item.status == "진행중"
    assert item.list_number == 7


def test_parse_detail_page_extracts_metadata_and_attachments() -> None:
    crawler = SkuNoticeCrawler()
    list_item = ListNoticeItem(
        source_notice_id=61471,
        detail_url="https://www.skuniv.ac.kr/notice/61471",
        title="fallback title",
        category="장학",
        author_org="학생처",
        posted_date=date(2026, 3, 7),
        status=None,
        list_number=7,
    )
    html = """
    <div class="post-detail-wrap">
      <div class="title-wrap"><h3>2026 장학금 신청 안내</h3></div>
      <ul class="base-meta-data-wrap">
        <li><span class="meta-title">작성부서</span><span class="meta-value">학생처</span></li>
        <li><span class="meta-title">등록일</span><span class="meta-value">2026.03.07</span></li>
      </ul>
      <div class="progress-meta-data-wrap">
        <div class="badge"><span>진행중</span></div>
        <span class="meta-value">2026-03-07</span>
        <span class="meta-value">2026-03-20</span>
      </div>
      <div class="post-content-wrap">
        <p>신청 대상은 재학생입니다.</p>
        <img src="/wp-content/uploads/2026/03/image.png" />
      </div>
      <div class="attachment-wrap">
        <a data-file-key="/2026/03/apply.hwp">신청서.hwp</a>
      </div>
    </div>
    """

    detail = crawler.parse_detail_page(html, list_item)

    assert detail.source_notice_id == 61471
    assert detail.title == "2026 장학금 신청 안내"
    assert detail.status == "진행중"
    assert detail.period_start == date(2026, 3, 7)
    assert detail.period_end == date(2026, 3, 20)
    assert "신청 대상은 재학생입니다." in detail.raw_text
    assert detail.image_urls == ["https://www.skuniv.ac.kr/wp-content/uploads/2026/03/image.png"]
    assert detail.attachments == [
        {
            "file_name": "신청서.hwp",
            "file_url": "https://www.skuniv.ac.kr/wp-content/uploads/2026/03/apply.hwp",
        }
    ]

# notice_chat HANDOFF

## 현재 스냅샷
- 기준일: 2026-03-08 (Asia/Seoul)
- 브랜치: `feat/sku-notice-langgraph-ingest`
- 단위 테스트: `uv run pytest tests/unit -q` 통과

## 이번 세션에서 완료한 작업
1. SKU 공지 인제스트를 3노드 LangGraph 워크플로우로 구성
- `crawl -> summarize -> persist`
- 파일: `notice_chat/services/sku_notice_ingest_service.py`

2. 크롤링/요약/인제스트 서비스 분리
- 크롤러: `notice_chat/services/sku_notice_crawler.py`
- 요약 서비스: `notice_chat/services/sku_notice_summary.py`
- 인제스트 오케스트레이션: `notice_chat/services/sku_notice_ingest_service.py`

3. 인제스트 그래프 문서화
- Mermaid 원본: `docs/sku_notice_ingest_graph.mmd`
- Markdown 보기용: `docs/sku_notice_ingest_graph.md`

4. 테스트 추가
- 크롤러 파서 테스트: `tests/unit/test_sku_notice_crawler.py`
- 인제스트 서비스 테스트: `tests/unit/test_sku_notice_ingest_service.py`

5. API 레이어 롤백
- 어드민 인제스트 API 라우터 삭제
- 인메모리 잡 매니저 삭제
- API/잡 매니저 관련 단위 테스트 삭제

## 아직 남은 작업
1. MCP 검색 툴 구현
- `search_notices`, `get_notice_detail`, `list_recent_notices` 우선 구현
- 초기 버전은 SQL 기반 필터/정렬/검색으로 구성

2. 검색 서비스 분리
- repository 위에 검색/랭킹 service 계층 추가
- MCP와 향후 API가 동일 service를 재사용하도록 정리

3. 관측성 강화
- 검색 모드(`sql_only`/`hybrid`)와 응답 시간 structured logging
- 실패 코드 표준화(`INVALID_ARGUMENT`, `NOTICE_NOT_FOUND` 등)

## 바로 실행/확인 방법
1. 서버 실행
```bash
uv run uvicorn main:app --reload
```

## 커밋 분리 권장(원자 단위)
1. `feat: SKU 공지 인제스트 3노드 LangGraph 워크플로우 도입`
2. `test: 인제스트 서비스/크롤러 단위 테스트 추가`
3. `refactor: API 레이어 제거 및 MCP 우선 구조 정리`
4. `docs: 인제스트 그래프 및 handoff 문서 업데이트`

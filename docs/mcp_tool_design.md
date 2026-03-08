# 서경대 공지사항 MCP 툴 설계안

## 목적

이 문서는 서경대학교 공지사항을 LLM 클라이언트에 전달하기 위한 첫 번째
MCP 툴 설계안을 정의한다. 현재 코드베이스에는 이미 다음 요소가 있다.

- 공지사항 저장 모델: `notice_chat/models/sku_notice.py`
- 공지사항 저장소 계층: `notice_chat/repositories/sku_notice_repository.py`
- 공지사항 Pydantic 스키마: `notice_chat/schemas/sku_notice.py`

MCP 계층은 저장소 종류 기준이 아니라 사용자 의도 기준으로 툴을 노출해야
한다. 즉, LLM이 "벡터 DB를 조회할지", "RDB를 조회할지" 직접 결정하게 하지
않고, 하나의 툴이 내부에서 적절한 검색 전략을 선택하도록 설계하는 것이
좋다.

## 설계 원칙

- 원본 데이터의 기준 저장소는 RDB로 둔다.
- 벡터 검색은 보조 검색 수단으로만 사용한다.
- 사용자 관점에서 `검색`, `상세 조회`, `최근 목록 조회`를 분리한다.
- 카테고리, 날짜, 부서, 상태 같은 구조화 조건은 결정적으로 처리한다.
- 결과에는 왜 이 공지가 매칭되었는지 설명 가능한 메타데이터를 포함한다.
- 1차 버전은 벡터 DB 없이도 동작할 수 있어야 한다.

## 권장 MCP 툴 구성

### 1. `search_notices`

자연어 기반 공지 검색의 메인 툴이다.

사용 예시:

- "장학금 공지 찾아줘"
- "휴학 관련 공지 보여줘"
- "최근 수강신청 공지 알려줘"

역할:

- 자연어 질의를 입력받는다.
- 선택적으로 구조화 필터를 입력받는다.
- 내부에서 하이브리드 검색을 수행한다.
- 점수순으로 정렬된 공지 요약 목록을 반환한다.

이 툴이 필요한 이유:

- 대부분의 사용자 요청은 검색 요청이다.
- 호출자는 데이터 저장 방식을 알 필요가 없다.
- 서버 내부 구현을 SQL 중심에서 하이브리드 검색으로 확장해도 툴 계약은
  유지할 수 있다.

### 2. `get_notice_detail`

선택된 공지 1건의 상세 정보를 가져오는 툴이다.

사용 예시:

- "첫 번째 결과 열어줘"
- "61447번 공지 상세 보여줘"
- "첨부파일도 같이 알려줘"

역할:

- 내부 ID 또는 학교 원본 공지 ID로 공지 1건을 조회한다.
- 메타데이터, 요약, 첨부파일, 원문 URL을 반환한다.
- 생성 시각과 수정 시각도 함께 제공한다.

이 툴이 필요한 이유:

- 검색 결과는 가볍게 유지하는 편이 좋다.
- 보통 검색 후 상세 조회가 2단계로 이어진다.

### 3. `list_recent_notices`

최근 공지를 빠르게 나열하는 툴이다.

사용 예시:

- "최신 공지 보여줘"
- "최근 장학금 공지 목록 보여줘"
- "이번 주 학사 공지 알려줘"

역할:

- 최근 공지를 날짜순으로 반환한다.
- 카테고리, 날짜, 상태 등의 필터를 적용할 수 있다.
- 의미 기반 검색 없이 결정적 정렬과 필터에 집중한다.

이 툴이 필요한 이유:

- 많은 질의는 사실상 "검색"이 아니라 "최신 목록 조회"에 가깝다.
- 이런 요청은 벡터 검색보다 RDB 정렬과 필터가 더 정확하고 저렴하다.

## 툴 계약

### `search_notices`

권장 입력 예시:

```json
{
  "query": "3월 이후 학생지원처 장학금 공지",
  "category": "scholarship",
  "author_org": "student support center",
  "posted_from": "2026-03-01",
  "posted_to": null,
  "status": "ongoing",
  "top_k": 10,
  "include_reason": true
}
```

입력 필드 규칙:

- `query`: 필수 자연어 질의, 1자 이상 500자 이하
- `category`: 선택적 카테고리 정확 일치 필터
- `author_org`: 선택적 작성 부서 필터
- `posted_from`: 선택적 게시일 시작 범위
- `posted_to`: 선택적 게시일 종료 범위
- `status`: 선택적 상태 필터
- `top_k`: 선택적 반환 개수, 기본값 5, 최대 20
- `include_reason`: 선택적 매칭 사유 포함 여부, 기본값 `true`

권장 출력 예시:

```json
{
  "query": "3월 이후 학생지원처 장학금 공지",
  "applied_filters": {
    "category": "scholarship",
    "author_org": "student support center",
    "posted_from": "2026-03-01",
    "posted_to": null,
    "status": "ongoing"
  },
  "results": [
    {
      "id": 10,
      "source_notice_id": 61447,
      "title": "2026학년도 장학금 신청 안내",
      "category": "scholarship",
      "author_org": "student office",
      "posted_date": "2026-03-05",
      "status": "ongoing",
      "detail_url": "https://www.skuniv.ac.kr/notice/61447",
      "summary_text": "장학금 신청 대상 및 제출 서류 안내",
      "score": 0.91,
      "match_reason": [
        "keyword:title",
        "semantic:summary_text",
        "filter:posted_date"
      ]
    }
  ],
  "total_returned": 1
}
```

서버 내부 동작:

- 클라이언트가 구조화 필터를 직접 주면 그대로 적용한다.
- 질의에서 제목, 요약, 본문에 대한 키워드 검색을 수행한다.
- 임베딩이 준비된 경우 벡터 검색도 함께 수행한다.
- 후보 집합을 병합한다.
- 재정렬 또는 점수 합산을 수행한다.
- 결과는 목록에 적합한 크기로 요약해서 반환한다.

### `get_notice_detail`

권장 입력 예시:

```json
{
  "id": 10,
  "source_notice_id": null
}
```

입력 필드 규칙:

- `id` 또는 `source_notice_id` 중 정확히 하나만 입력해야 한다.

권장 출력 예시:

```json
{
  "notice": {
    "id": 10,
    "source_notice_id": 61447,
    "title": "2026학년도 장학금 신청 안내",
    "category": "scholarship",
    "author_org": "student office",
    "posted_date": "2026-03-05",
    "status": "ongoing",
    "period_start": "2026-03-05",
    "period_end": "2026-03-20",
    "detail_url": "https://www.skuniv.ac.kr/notice/61447",
    "summary_text": "장학금 신청 대상 및 제출 서류 안내",
    "attachments": [
      {
        "file_name": "apply.hwp",
        "file_url": "https://files.example/a.hwp"
      }
    ],
    "created_at": "2026-03-07T09:00:00Z",
    "updated_at": "2026-03-07T09:00:00Z"
  }
}
```

서버 내부 동작:

- 조회 인자를 검증한다.
- RDB에서만 1건을 조회한다.
- 없으면 구조화된 not-found 오류를 반환한다.

### `list_recent_notices`

권장 입력 예시:

```json
{
  "category": "academic",
  "author_org": null,
  "posted_from": "2026-03-01",
  "posted_to": null,
  "status": null,
  "limit": 10
}
```

권장 출력 예시:

```json
{
  "results": [
    {
      "id": 21,
      "source_notice_id": 61521,
      "title": "수강신청 일정 변경 안내",
      "category": "academic",
      "author_org": "academic affairs",
      "posted_date": "2026-03-06",
      "status": "ongoing",
      "detail_url": "https://www.skuniv.ac.kr/notice/61521",
      "summary_text": "수강신청 일정과 유의사항이 변경되었습니다."
    }
  ],
  "total_returned": 1
}
```

서버 내부 동작:

- `posted_date desc`, `id desc` 순으로 정렬한다.
- 정확한 필터만 적용한다.
- 벡터 검색은 사용하지 않는다.

## 검색 전략

### 1단계: SQL 우선

초기 버전은 벡터 검색 없이 구현하는 것이 좋다.

권장 정렬 기준:

- 카테고리, 상태, 날짜 필터를 먼저 적용
- 제목 키워드 매칭 가중치 높게
- 요약 또는 본문 키워드 매칭 가중치 중간
- 최신성 보정은 작지만 일관되게 반영

이 단계만으로도 다음 요구를 상당수 처리할 수 있다.

- 최근 공지 조회
- 카테고리별 조회
- 제목 또는 제목에 가까운 검색

### 2단계: 하이브리드 검색

SQL 기반 검색의 품질이 한계에 도달하면 임베딩을 추가한다.

권장 파이프라인:

1. 검색용 문서를 다음 필드로 구성한다.
   - `title`
   - `summary_text`
   - 향후 추가될 `body_text`
   - `category`
   - `author_org`
2. 공지별 임베딩을 생성한다.
3. 키워드 검색으로 상위 N개 후보를 가져온다.
4. 벡터 검색으로 상위 N개 후보를 가져온다.
5. 공지 ID 기준으로 병합한다.
6. 단순 가중치 또는 재정렬 모델로 순위를 다시 계산한다.

권장 초기 점수식:

- `0.50 * keyword_score`
- `0.35 * vector_score`
- `0.15 * recency_score`

이 로직은 전부 `search_notices` 내부 구현에 숨겨져 있어야 한다.

## 데이터 모델 매핑

현재 저장 필드만으로도 MCP 1차 요구사항 대부분을 충족할 수 있다.

- `id`
- `source_notice_id`
- `detail_url`
- `title`
- `category`
- `author_org`
- `posted_date`
- `status`
- `list_number`
- `period_start`
- `period_end`
- `summary_text`
- `attachments`
- `created_at`
- `updated_at`

향후 추가를 권장하는 필드:

- `body_text`: 전체 본문 정규화 텍스트
- `embedding`: 벡터 컬럼 또는 외부 벡터 저장소 키
- `embedding_updated_at`: 임베딩 갱신 시각
- `source_page_fetched_at`: 크롤링 최신성 추적용 시각
- `is_pinned`: 상단 고정 공지 여부

## 내부 서비스 구조

권장 패키지 구조:

```text
notice_chat/
  mcp/
    server.py
    tools/
      search_notices.py
      get_notice_detail.py
      list_recent_notices.py
    schemas/
      tool_inputs.py
      tool_outputs.py
  services/
    notice_search_service.py
    notice_ranking_service.py
  repositories/
    sku_notice_repository.py
```

권장 책임 분리:

- repository: DB 입출력만 담당
- service: 필터 해석, 검색 조합, 점수 계산 담당
- MCP tool: 입력 검증, 서비스 호출, 출력 직렬화 담당

이렇게 분리해두면 나중에 같은 검색 로직을 FastAPI 엔드포인트나 배치 작업,
테스트 코드에서도 재사용하기 쉽다.

## 오류 계약

오류는 기계적으로 처리 가능한 고정 코드로 반환하는 것이 좋다.

예시:

```json
{
  "error": {
    "code": "NOTICE_NOT_FOUND",
    "message": "해당 식별자에 대응하는 공지를 찾지 못했습니다."
  }
}
```

```json
{
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "id 또는 source_notice_id 중 하나만 입력해야 합니다."
  }
}
```

권장 오류 코드:

- `INVALID_ARGUMENT`
- `NOTICE_NOT_FOUND`
- `SEARCH_BACKEND_UNAVAILABLE`
- `EMBEDDING_INDEX_NOT_READY`

## 관찰 가능성

각 MCP 호출에 대해 최소한 다음 정보를 구조화 로그로 남기는 것이 좋다.

- tool 이름
- 정규화된 필터 값
- 사용한 검색 모드: `sql_only` 또는 `hybrid`
- 후보 수
- 최종 반환 수
- 응답 시간 밀리초

이 정보는 나중에 랭킹 품질을 조정할 때 유용하다.

## 1차 구현 순서

### Step 1

다음 세 툴을 먼저 구현한다.

- `search_notices`
- `get_notice_detail`
- `list_recent_notices`

이 단계에서는 SQL만 사용한다.

### Step 2

repository 계층을 다음 요구에 맞게 확장한다.

- `author_org` 필터
- 날짜 범위 필터
- `title`, `summary_text` 텍스트 검색

### Step 3

service 계층을 추가해서 다음 모드를 선택하게 한다.

- 최근 공지 목록 조회
- 필터 기반 SQL 검색
- 임베딩 준비 시 하이브리드 검색

### Step 4

벡터 인덱싱과 하이브리드 점수 계산을 기존 `search_notices` 계약 뒤에
추가한다.

## 결론

서경대 공지사항 MCP의 첫 번째 툴 표면은 아래 3개가 가장 적절하다.

- `search_notices`
- `get_notice_detail`
- `list_recent_notices`

`RDB 조회 툴`과 `벡터 조회 툴`을 별도로 노출하지 않는 것이 중요하다.
저장소 선택 로직이 프롬프트 계층으로 새어 나오면 예측 가능성이 떨어지고,
추후 검색 구조를 바꿀 때도 호환성이 나빠진다. 저장 전략은 서버 내부에
감추고, MCP 툴은 사용자 의도 중심으로 유지하는 편이 더 안정적이다.

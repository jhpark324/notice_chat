from __future__ import annotations

from dataclasses import dataclass

from langchain_core.prompts import ChatPromptTemplate


@dataclass(frozen=True, slots=True)
class SummaryPromptSettings:
    """Prompt-level knobs for summary format requirements."""

    min_bullets: int = 5
    max_bullets: int = 10
    missing_info_message: str = "상세 공지사항 참조"


DEFAULT_SUMMARY_PROMPT_SETTINGS = SummaryPromptSettings()


def build_summary_prompt(
    settings: SummaryPromptSettings = DEFAULT_SUMMARY_PROMPT_SETTINGS,
) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "당신은 대학교 공지사항을 한국어로 간결하게 요약하는 도우미입니다. "
                    "사실을 정확히 유지하고, 없는 정보를 추측해서 만들지 마세요."
                ),
            ),
            (
                "human",
                f"""
DB 컬럼 `summary_text`에 저장할 최종 한국어 요약을 작성하세요.

공지 제목: {{title}}
상세 URL: {{detail_url}}
카테고리: {{category}}
작성 부서: {{author_org}}
게시일: {{posted_date}}
진행 상태: {{status}}
기간: {{period_start}} ~ {{period_end}}

첨부파일:
{{attachments}}

본문 원문:
{{raw_text}}

출력 형식:
- 짧은 불릿 포인트 {settings.min_bullets}~{settings.max_bullets}개
- 반드시 포함: 대상자, 핵심 행동, 마감/기간, 필요 서류, 유의사항
- 정보가 없으면 "{settings.missing_info_message}"라고 명시
""",
            ),
        ]
    )


SKU_NOTICE_SUMMARY_PROMPT = build_summary_prompt()

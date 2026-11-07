"""LIT 11월 Meetup: 기본 스키마와 설명을 개선한 스키마.

CU의 fieldSchema 설명만 바꾸어 추출 결과를 비교하기 위해 나머지 조건은 같다.
"""

from __future__ import annotations

import hashlib
import json

MODEL_NAMES = {"completion": "gpt-4.1-mini", "embedding": "text-embedding-3-small"}

FIELD_LABELS = {
    "event_title": "행사명",
    "event_date": "행사 날짜",
    "start_time": "시작 시간",
    "end_time": "종료 시간",
    "location": "장소",
    "registration_deadline": "신청 마감일",
    "registration_url": "신청 링크",
    "organizer": "주최/주관",
}

BASE_DESCRIPTIONS = {
    "event_title": "Title of the event or meetup shown in the poster.",
    "event_date": "Date shown in the event poster.",
    "start_time": "Start time of the event.",
    "end_time": "End time of the event, if shown.",
    "location": "Location or venue in the poster.",
    "registration_deadline": "Registration deadline, if shown.",
    "registration_url": "Registration website or QR code URL, if visible as text.",
    "organizer": "Organizer or host of the event.",
}

TUNED_DESCRIPTIONS = {
    "event_title": (
        "The actual event name, not the organizer, club name alone, or a registration slogan. "
        "Keep the title exactly as written on the poster, including Korean text."
    ),
    "event_date": (
        "Only the date on which attendees should GO TO or JOIN the event. "
        "Never use an application deadline, registration period, announcement date, or application opening date. "
        "For a contest, 공모기간, 접수기간 and 모집기간 describe submission/application periods, not attendance dates. "
        "If only those periods are printed, leave event_date empty and use registration_deadline for their closing date. "
        "If multiple sessions are listed, preserve the entire date range as written. "
        "If the year is missing, preserve month/day WITHOUT inventing a year. "
        "Return an empty value if no event date is stated."
    ),
    "start_time": (
        "Time the event actually STARTS, not the application deadline or check-in deadline. "
        "Preserve the printed time, including AM/PM notation if present; do not guess a missing time."
    ),
    "end_time": (
        "Time the event actually ENDS. Return empty if no end time is printed. "
        "Do not confuse closing time for applications with the end of the event."
    ),
    "location": (
        "Physical venue or online meeting platform where the event takes place, "
        "including building and room number. Do not use the organizer's address. "
        "Preserve abbreviations such as IT-5 B102 exactly."
    ),
    "registration_deadline": (
        "Last day to APPLY or REGISTER. This must remain separate from event_date. "
        "For contests, also extract the closing/end date of 공모기간, 접수기간, 모집기간 or 응모기간, "
        "even without the word 마감. For example, 공모기간 2025.7.16 ~ 9.15 means the deadline is 2025-09-15. "
        "A year explicitly shared by that date range applies to its end date. "
        "If the year is absent from the entire range, do not infer one. Return empty if no deadline or application period is printed."
    ),
    "registration_url": (
        "Exact visible link for applying to the event; never invent a URL from a QR image. "
        "If a QR code is present but its destination is not printed, return empty."
    ),
    "organizer": (
        "Organization that hosts or organizes the event, not the venue or speaker."
    ),
}


def make_analyzer_definition(tuned: bool, event_date_description: str | None = None, *, descriptions_override: dict[str, str] | None = None) -> dict:
    descriptions = (TUNED_DESCRIPTIONS if tuned else BASE_DESCRIPTIONS).copy()
    if event_date_description is not None:
        descriptions["event_date"] = event_date_description
    if descriptions_override is not None:
        unknown = set(descriptions_override) - set(FIELD_LABELS)
        if unknown:
            raise ValueError("알 수 없는 필드: " + ", ".join(sorted(unknown)))
        for field, value in descriptions_override.items():
            if not isinstance(value, str) or not value.strip() or len(value) > 1000:
                raise ValueError(f"{FIELD_LABELS[field]} 설명은 1~1000자로 입력해 주세요.")
            descriptions[field] = value.strip()
    return {
        "description": (
            "LIT Meetup event poster extraction: tuned field instructions"
            if tuned
            else "LIT Meetup event poster extraction: baseline field instructions"
        ),
        "baseAnalyzerId": "prebuilt-document",
        "models": MODEL_NAMES.copy(),
        "config": {
            "enableOcr": True,
            "enableLayout": True,
            "enableFormula": False,
            "returnDetails": True,
        },
        "fieldSchema": {
            "name": "MeetupEvent",
            "description": "Extract meetup details from event posters and notices.",
            "fields": {
                field: {
                    "type": "string",
                    "method": "extract",
                    "estimateSourceAndConfidence": True,
                    "description": description,
                }
                for field, description in descriptions.items()
            },
        },
    }


def analyzer_id(tuned: bool, event_date_description: str | None = None, *, descriptions_override: dict[str, str] | None = None) -> str:
    """Content-addressed ID avoids accidentally replacing an unrelated analyzer."""
    definition = make_analyzer_definition(tuned, event_date_description, descriptions_override=descriptions_override)
    digest = hashlib.sha256(
        json.dumps(definition, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:10]
    kind = "tuned" if tuned else "basic"
    return f"lit_meetup_{kind}_{digest}"


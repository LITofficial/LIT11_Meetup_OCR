"""기본 스키마 한 개와 사용자가 직접 수정하는 필드 설명."""

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
    "event_title": "포스터에 표시된 행사 또는 모임의 이름.",
    "event_date": "행사 포스터에 표시된 날짜.",
    "start_time": "행사가 시작하는 시각.",
    "end_time": "행사 종료 시각이 표시되어 있으면 추출.",
    "location": "포스터에 표시된 장소 또는 행사장.",
    "registration_deadline": "신청 마감일이 표시되어 있으면 추출.",
    "registration_url": "글자로 표시된 신청 웹사이트 주소 또는 QR 코드의 연결 주소.",
    "organizer": "행사를 주최하거나 주관하는 단체.",
}


def make_analyzer_definition(tuned: bool, event_date_description: str | None = None, *, descriptions_override: dict[str, str] | None = None) -> dict:
    # Keep the legacy boolean argument for older callers; there is one base schema.
    descriptions = BASE_DESCRIPTIONS.copy()
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
        "description": "LIT 행사 포스터 정보 추출: 기본 스키마와 사용자 필드 설명",
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
            "description": "행사 포스터와 안내문에서 모임의 상세 정보를 추출한다.",
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
    return f"lit_meetup_{digest}"


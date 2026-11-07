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
    "event_title": "포스터에 표시된 행사 또는 모임의 이름.",
    "event_date": "행사 포스터에 표시된 날짜.",
    "start_time": "행사가 시작하는 시각.",
    "end_time": "행사 종료 시각이 표시되어 있으면 추출.",
    "location": "포스터에 표시된 장소 또는 행사장.",
    "registration_deadline": "신청 마감일이 표시되어 있으면 추출.",
    "registration_url": "글자로 표시된 신청 웹사이트 주소 또는 QR 코드의 연결 주소.",
    "organizer": "행사를 주최하거나 주관하는 단체.",
}

TUNED_DESCRIPTIONS = {
    "event_title": (
        "주최 단체명이나 동아리 이름만, 또는 신청을 독려하는 문구가 아닌 실제 행사 이름을 추출한다. "
        "한글을 포함해 포스터에 적힌 제목을 그대로 유지한다."
    ),
    "event_date": (
        "참가자가 실제로 방문하거나 참석하는 날짜만 추출한다. "
        "신청 마감일, 접수 기간, 결과 발표일, 신청 시작일은 사용하지 않는다. "
        "공모전의 공모기간·접수기간·모집기간은 응모 또는 신청을 받는 기간이며 참석 날짜가 아니다. "
        "이러한 기간만 적혀 있으면 행사 날짜는 비워 두고, 기간의 마지막 날을 신청 마감일에 추출한다. "
        "여러 회차가 표시되어 있으면 적힌 날짜 범위 전체를 유지한다. "
        "연도가 없으면 임의로 만들지 말고 월·일만 유지한다. 행사 날짜가 명시되지 않으면 빈 값으로 반환한다."
    ),
    "start_time": (
        "신청 마감 시각이나 입장 마감 시각이 아닌, 행사가 실제로 시작하는 시각을 추출한다. "
        "오전·오후 표시를 포함해 인쇄된 시각을 유지한다. 적혀 있지 않은 시각은 추측하지 않는다."
    ),
    "end_time": (
        "행사가 실제로 종료되는 시각을 추출한다. 종료 시각이 적혀 있지 않으면 빈 값으로 반환한다. "
        "접수 마감 시각을 행사 종료 시각으로 혼동하지 않는다."
    ),
    "location": (
        "행사가 열리는 실제 장소 또는 온라인 회의 플랫폼을 추출한다. 건물명과 강의실 번호를 포함한다. "
        "주최 단체의 주소는 사용하지 않는다. IT-5 B102와 같은 약칭은 그대로 유지한다."
    ),
    "registration_deadline": (
        "신청 또는 등록을 받는 마지막 날짜를 행사 날짜와 구분해 추출한다. "
        "공모전에서는 '마감'이라는 단어가 없어도 공모기간·접수기간·모집기간·응모기간의 마지막 날짜를 추출한다. "
        "예를 들어 '공모기간 2025.7.16 ~ 9.15'의 마감일은 2025-09-15이다. "
        "날짜 범위 전체에 공통으로 명시된 연도는 종료 날짜에도 적용한다. "
        "범위 전체에 연도가 없으면 임의로 추측하지 않는다. 마감일이나 접수 기간이 없으면 빈 값으로 반환한다."
    ),
    "registration_url": (
        "행사 신청을 위해 글자로 표시된 정확한 주소를 추출한다. QR 코드 이미지로부터 주소를 만들어 내지 않는다. "
        "QR 코드만 있고 연결 주소가 글자로 적혀 있지 않으면 빈 값으로 반환한다."
    ),
    "organizer": "행사를 주최하거나 주관하는 단체를 추출한다. 행사장이나 발표자를 주최 단체로 사용하지 않는다.",
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
            "LIT 모임 행사 포스터 정보 추출: 개선된 필드 설명"
            if tuned
            else "LIT 모임 행사 포스터 정보 추출: 기본 필드 설명"
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
    kind = "tuned" if tuned else "basic"
    return f"lit_meetup_{kind}_{digest}"


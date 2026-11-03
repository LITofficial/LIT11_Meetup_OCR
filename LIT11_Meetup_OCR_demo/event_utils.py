"""CU 결과 정리와 검토한 일정의 iCalendar(.ics) 내보내기."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse

from analyzer_schemas import FIELD_LABELS

SEOUL = timezone(timedelta(hours=9))


def normalize_fields(result: dict) -> tuple[dict[str, str], dict[str, float | None]]:
    """CU의 valueString/valueDate 등 여러 타입을 안전하게 평문 값으로 변환."""
    fields: dict[str, str] = {name: "" for name in FIELD_LABELS}
    confidences: dict[str, float | None] = {name: None for name in FIELD_LABELS}
    contents = result.get("result", {}).get("contents", [])
    for content in contents:
        for name, value in (content.get("fields") or {}).items():
            if name not in fields or not isinstance(value, dict):
                continue
            text = next(
                (str(value[key]) for key in ("valueString", "valueDate", "valueTime", "valueNumber")
                 if value.get(key) is not None),
                "",
            )
            if not text and value.get("valueArray"):
                text = ", ".join(
                    str(item.get("valueString", "")) for item in value["valueArray"]
                )
            if text:
                fields[name] = text.strip()
                confidence = value.get("confidence")
                if isinstance(confidence, (float, int)):
                    confidences[name] = float(confidence)
    return fields, confidences


def extract_markdown(result: dict) -> str:
    return "\n\n".join(
        content.get("markdown", "")
        for content in result.get("result", {}).get("contents", [])
        if content.get("markdown")
    )


def parse_explicit_date(text: str) -> date | None:
    """연도가 명시된 날짜만 해석한다. 행사 연도를 임의로 채우지 않는다."""
    match = re.search(
        r"(?<!\d)(?P<year>(?:19|20)\d{2})\s*(?:[-./]|년\s*)\s*"
        r"(?P<month>\d{1,2})\s*(?:[-./]|월\s*)\s*(?P<day>\d{1,2})",
        text.strip(),
    )
    if not match:
        return None
    try:
        return date(int(match["year"]), int(match["month"]), int(match["day"]))
    except ValueError:
        return None


def parse_event_time(text: str) -> time | None:
    value = text.strip()
    match = re.search(r"(?<!\w)(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>AM|PM)(?!\w)", value, re.I)
    if match:
        hour, minute = int(match["hour"]), int(match["minute"] or 0)
        if 1 <= hour <= 12 and 0 <= minute < 60:
            return time(hour % 12 + (12 if match["ampm"].upper() == "PM" else 0), minute)
    match = re.search(
        r"(?P<ampm>오전|오후)\s*(?P<hour>\d{1,2})(?::(?P<colon_min>\d{2})|\s*시\s*(?P<korean_min>\d{1,2})?)?",
        value,
    )
    if match:
        hour = int(match["hour"])
        minute = int(match["colon_min"] or match["korean_min"] or 0)
        if 1 <= hour <= 12 and 0 <= minute < 60:
            return time(hour % 12 + (12 if match["ampm"] == "오후" else 0), minute)
    match = re.search(r"(?<!\d)(?P<hour>\d{1,2}):(?P<minute>\d{2})(?!\d)", value)
    if match:
        hour, minute = int(match["hour"]), int(match["minute"])
        if 0 <= hour < 24 and 0 <= minute < 60:
            return time(hour, minute)
    match = re.search(r"(?<!\d)(?P<hour>\d{1,2})\s*시\s*(?P<minute>\d{1,2})?", value)
    if match and not re.search(r"오전|오후", value):
        hour, minute = int(match["hour"]), int(match["minute"] or 0)
        if 0 <= hour < 24 and 0 <= minute < 60:
            return time(hour, minute)
    return None


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _fold_ics_line(line: str) -> str:
    """RFC 5545의 75-octet folding; 한글 UTF-8 문자를 중간에서 자르지 않음."""
    segments: list[str] = []
    chunk = ""
    byte_count = 0
    for char in line:
        count = len(char.encode("utf-8"))
        if byte_count + count > 75:
            segments.append(chunk)
            chunk = " " + char
            byte_count = 1 + count
        else:
            chunk += char
            byte_count += count
    segments.append(chunk)
    return "\r\n".join(segments)


def make_ics(
    *,
    title: str,
    date_text: str,
    start_text: str,
    end_text: str = "",
    location: str = "",
    description: str = "",
    url: str = "",
) -> bytes:
    """사용자가 검토한 입력만으로 일정을 생성; 연도와 시간은 필수."""
    if not title.strip():
        raise ValueError("행사명을 입력해 주세요.")
    event_date = parse_explicit_date(date_text)
    if event_date is None:
        raise ValueError("행사 날짜를 연도까지 포함해 입력해 주세요 (예: 2026-11-11).")
    start_time = parse_event_time(start_text)
    if start_time is None:
        raise ValueError("시작 시간을 입력해 주세요 (예: 18:00).")
    end_time = parse_event_time(end_text) if end_text.strip() else None
    if end_text.strip() and end_time is None:
        raise ValueError("종료 시간을 HH:MM 형식으로 확인해 주세요.")

    start = datetime.combine(event_date, start_time, tzinfo=SEOUL)
    end = datetime.combine(event_date, end_time, tzinfo=SEOUL) if end_time else start + timedelta(hours=1)
    if end <= start:
        end += timedelta(days=1)  # 자정을 넘어가는 행사

    def utc_string(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LIT Meetup//Poster to Calendar//KO",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@lit-meetup.local",
        f"DTSTAMP:{utc_string(datetime.now(timezone.utc))}",
        f"DTSTART:{utc_string(start)}",
        f"DTEND:{utc_string(end)}",
        f"SUMMARY:{_ics_escape(title.strip())}",
        f"LOCATION:{_ics_escape(location.strip())}",
        f"DESCRIPTION:{_ics_escape(description.strip())}",
    ]
    if url.strip():
        parsed = urlparse(url.strip())
        if parsed.scheme in ("https", "http") and parsed.netloc:
            lines.append(f"URL:{_ics_escape(url.strip())}")
    lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
    return "\r\n".join(_fold_ics_line(line) for line in lines).encode("utf-8")


def deadline_status(text: str, today: date | None = None) -> tuple[str, int | None]:
    deadline = parse_explicit_date(text)
    if deadline is None:
        return ("확인 필요" if text.strip() else "마감일 없음", None)
    days = (deadline - (today or datetime.now(SEOUL).date())).days
    return ("마감됨" if days < 0 else "오늘 마감" if days == 0 else f"D-{days}", days)


def source_regions(result: dict, field: str) -> list[tuple[int, list[tuple[float, float]]]]:
    """Decode CU document polygons and bounding boxes."""
    regions = []
    for content in result.get("result", {}).get("contents", []):
        value = (content.get("fields") or {}).get(field) or {}
        source = value.get("source", "") if isinstance(value, dict) else ""
        if not isinstance(source, str):
            continue
        for match in re.finditer(r"D\(([^)]*)\)", source):
            try:
                nums = [float(part.strip()) for part in match.group(1).split(",")]
                page = int(nums[0])
                if page < 1 or nums[0] != page:
                    continue
                coords = nums[1:]
                if len(coords) == 4:
                    x, y, w, h = coords
                    points = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
                elif len(coords) >= 6 and len(coords) % 2 == 0:
                    points = list(zip(coords[::2], coords[1::2]))
                else:
                    continue
                regions.append((page, points))
            except (ValueError, IndexError, OverflowError):
                continue
    return regions


def make_deadline_ics(title: str, deadline: str, url: str = "") -> bytes:
    """A 9 AM Seoul deadline event with a one-day-prior display alarm."""
    if not title.strip():
        raise ValueError("행사명을 입력해 주세요.")
    data = make_ics(title=f"신청 마감: {title}", date_text=deadline, start_text="09:00", url=url)
    return data.replace(b"END:VEVENT\r\n", b"BEGIN:VALARM\r\nTRIGGER:-P1D\r\nACTION:DISPLAY\r\nDESCRIPTION:Registration deadline tomorrow\r\nEND:VALARM\r\nEND:VEVENT\r\n")

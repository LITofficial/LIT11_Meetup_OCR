"""LIT 11월 Meetup: 포스터 → Content Understanding → 캘린더.

실행: streamlit run app.py
"""

from __future__ import annotations

import hashlib
import json
import os
from io import BytesIO

from PIL import Image, ImageDraw

import streamlit as st
from dotenv import load_dotenv

from analyzer_schemas import FIELD_LABELS, BASE_DESCRIPTIONS, analyzer_id, make_analyzer_definition
from cu_client import CUClient, CUError
from event_utils import (deadline_status, extract_markdown, make_deadline_ics, make_ics,
                         normalize_fields, parse_explicit_date, source_regions)

load_dotenv()

MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

st.set_page_config(page_title="포스터를 일정으로 | LIT", page_icon="🗓️", layout="wide")
st.markdown(
    """
    <style>
      .block-container { max-width: 1120px; padding-top: 2rem; }
      .hero { padding: 1.4rem 1.7rem; border-radius: 18px;
              background: linear-gradient(125deg, #10233d, #13475c); color: white; }
      .hero h1 { color: white; margin: 0 0 .35rem 0; font-size: 2rem; }
      .hero p { color: #d2e8ef; margin: 0; }
      .step-note { color: #64748b; font-size: .92rem; }
    </style>
    <div class="hero">
      <h1>🗓️ 포스터를 일정으로</h1>
      <p>Azure Content Understanding · OCR → 의미 추출 → 스키마 개선 → 캘린더</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("LIT 11월 Meetup 라이브 데모 · Azure AI Language 없이 Content Understanding만 사용")


def build_client() -> CUClient:
    return CUClient(endpoint=endpoint, api_key=api_key)


# Credentials stay on the server; visitors cannot alter shared Azure settings.
endpoint = os.getenv("AZURE_CU_ENDPOINT", "")
api_key = os.getenv("AZURE_CU_KEY", "")
completion_deployment = os.getenv("AZURE_CU_COMPLETION_DEPLOYMENT", "gpt-4.1-mini")
embedding_deployment = os.getenv("AZURE_CU_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
with st.sidebar:
    st.info("Azure 연결은 서버 관리자가 설정합니다.")
    st.caption("스키마 변경 후 재분석할 때마다 Azure 요청이 발생합니다.")

st.subheader("1. 행사 포스터 업로드")
left, right = st.columns([1, 1], gap="large")
with left:
    uploads = st.file_uploader(
        "JPG · PNG · PDF (최대 10MB)",
        type=["jpg", "jpeg", "png", "pdf"],
        accept_multiple_files=True,
        help="개인정보가 없는 포스터나 공개 행사 안내문을 이용해 주세요.",
    )
    analysis_mode = st.radio(
        "테스트 모드",
        ["OCR만 확인 (1회 분석)", "기본 스키마 vs 개선 스키마 (3회 분석)"],
        horizontal=False,
        help="맞춤 스키마 비교는 OCR + 기본 분석기 + 개선 분석기를 각각 호출합니다.",
    )
    date_description = st.text_area(
        "행사 날짜를 찾는 설명을 직접 수정해 보세요",
        value=BASE_DESCRIPTIONS["event_date"],
        max_chars=500,
        help="참가자가 실제로 참석하는 날짜인지, 신청 마감일을 제외할지 적어 보세요.",
    )
with right:
    upload = st.selectbox("확인할 포스터", uploads, format_func=lambda f: f.name) if uploads else None
    if upload is not None:
        if MIME_BY_SUFFIX.get(os.path.splitext(upload.name.lower())[1], "").startswith("image/"):
            st.image(upload, caption=upload.name, use_container_width=True)
        else:
            st.success(f"📄 {upload.name} · {upload.size / 1024:.1f} KB")
            st.caption("PDF 원본은 업로드되며, 분석된 글자는 아래에서 확인할 수 있어요.")
    else:
        st.info("왼쪽에 행사 포스터를 넣으면 원본과 분석 결과를 비교할 수 있어요.")

file_bytes = upload.getvalue() if upload is not None else b""
if len(file_bytes) > 10 * 1024 * 1024:
    st.error("파일 크기가 10MB를 초과했어요. PDF나 이미지를 압축해 주세요.")
file_hash = hashlib.sha256(file_bytes).hexdigest() if file_bytes else None
if st.session_state.get("file_hash") != file_hash:
    st.session_state["file_hash"] = file_hash
    st.session_state["results"] = st.session_state.get("batch_results", {}).get(file_hash, {})
    st.session_state.pop("calendar_bytes", None)
    st.session_state.pop("deadline_bytes", None)
    for name in ("event_title", "event_date", "start_time", "end_time", "location", "registration_deadline", "registration_url", "organizer"):
        st.session_state.pop(f"edit_{name}", None)

run_clicked = st.button(
    "🔎 포스터 분석 실행",
    type="primary",
    use_container_width=True,
    disabled=not uploads,
)
if run_clicked:
    st.session_state["batch_results"] = {}
    st.session_state["batch_rows"] = []
    for name in FIELD_LABELS:
        st.session_state.pop(f"edit_{name}", None)
    st.session_state["results"] = {}
    st.session_state.pop("calendar_bytes", None)
    st.session_state.pop("deadline_bytes", None)
    batch_rows = []
    try:
        client = build_client()
        deployments = {"gpt-4.1-mini": completion_deployment, "text-embedding-3-small": embedding_deployment}
        with st.status("포스터별 Azure 분석 중…", expanded=True) as status:
            for item in uploads:
                data = item.getvalue()
                key = hashlib.sha256(data).hexdigest()
                item_results = {}
                try:
                    st.write(f"분석 중: {item.name}")
                    item_results["ocr"] = client.analyze("prebuilt-read", data, item.name, MIME_BY_SUFFIX[os.path.splitext(item.name.lower())[1]])
                    if analysis_mode.startswith("기본 스키마"):
                        for label, tuned in (("basic", False), ("tuned", True)):
                            description = date_description.strip() if tuned else None
                            if tuned and not description:
                                raise CUError("행사 날짜 필드 설명을 입력해 주세요.")
                            definition = make_analyzer_definition(tuned, description)
                            current_id = analyzer_id(tuned, description)
                            client.ensure_analyzer(current_id, definition)
                            item_results[label] = client.analyze(current_id, data, item.name, MIME_BY_SUFFIX[os.path.splitext(item.name.lower())[1]], model_deployments=deployments)
                    fields, _ = normalize_fields(item_results.get("tuned", {}))
                    batch_rows.append({"파일": item.name, "결과": "성공", "행사명": fields.get("event_title", ""), "신청 마감": fields.get("registration_deadline", ""), "마감 상태": deadline_status(fields.get("registration_deadline", ""))[0]})
                except CUError as exc:
                    batch_rows.append({"파일": item.name, "결과": f"실패: {exc}"})
                st.session_state["batch_results"][key] = item_results
            status.update(label="일괄 분석 완료", state="complete", expanded=False)
        st.session_state["batch_rows"] = batch_rows
        st.session_state["results"] = st.session_state["batch_results"].get(file_hash, {})
    except CUError as exc:
        st.error(f"연결 설정 오류: {exc}")

if st.session_state.get("batch_rows"):
    st.subheader("일괄 분석 현황")
    st.dataframe(st.session_state["batch_rows"], use_container_width=True, hide_index=True)
    st.caption("파일을 선택하면 해당 포스터의 상세 결과를 확인할 수 있습니다. 같은 내용의 파일은 결과를 공유합니다.")

results = st.session_state.get("results", {})
if results:
    st.divider()
    st.subheader("2. Content Understanding 추출 결과")
    ocr_markdown = extract_markdown(results.get("ocr", {}))
    with st.expander("🔤 OCR로 읽은 원문 (글자 인식)", expanded=True):
        if ocr_markdown:
            st.text_area("OCR 결과", ocr_markdown, height=220, label_visibility="collapsed")
        else:
            st.warning("OCR 문자가 반환되지 않았어요.")

    if "basic" in results or "tuned" in results:
        basic, basic_conf = normalize_fields(results.get("basic", {}))
        tuned, tuned_conf = normalize_fields(results.get("tuned", {}))
        st.caption("같은 포스터와 모델을 사용합니다. 오른쪽은 직접 입력한 행사 날짜 설명과 개선된 나머지 필드 설명을 사용합니다.")
        rows = [
            {"필드": label, "기본 스키마": basic[name] or "—", "수정 스키마": tuned[name] or "—"}
            for name, label in FIELD_LABELS.items()
        ]
        st.table(rows)
        with st.expander("📊 필드별 신뢰도 및 원본 JSON"):
            st.write("신뢰도는 API가 제공한 필드만 표시합니다. 값이 없으면 정확도를 의미하지 않아요.")
            st.table([
                {
                    "필드": FIELD_LABELS[name],
                    "기본 신뢰도": f"{basic_conf[name]:.1%}" if basic_conf[name] is not None else "—",
                    "개선 신뢰도": f"{tuned_conf[name]:.1%}" if tuned_conf[name] is not None else "—",
                }
                for name in FIELD_LABELS
            ])
            st.json({"basic": results.get("basic"), "tuned": results.get("tuned")})
        st.download_button(
            "📥 비교 JSON 다운로드",
            data=json.dumps({"basic": basic, "tuned": tuned}, ensure_ascii=False, indent=2),
            file_name="lit-poster-comparison.json",
            mime="application/json",
        )

        st.divider()
        st.subheader("추출 근거 확인")
        evidence_result = results.get("tuned") or results.get("basic", {})
        evidence_field = st.selectbox("확인할 필드", list(FIELD_LABELS), format_func=lambda name: FIELD_LABELS[name])
        regions = source_regions(evidence_result, evidence_field)
        if not regions:
            st.info("이 필드에 Azure가 반환한 위치 근거가 없습니다. OCR 원문과 포스터를 직접 확인해 주세요.")
        elif upload and upload.type.startswith("image/"):
            image = Image.open(BytesIO(file_bytes)).convert("RGB")
            draw = ImageDraw.Draw(image)
            contents = evidence_result.get("result", {}).get("contents", [])
            pages = [page for content in contents for page in content.get("pages", [])]
            page = next((p for p in pages if p.get("pageNumber") == 1), {})
            width, height = page.get("width"), page.get("height")
            if width and height:
                for number, points in regions:
                    if number == 1:
                        scaled = [(x * image.width / width, y * image.height / height) for x, y in points]
                        draw.line(scaled + [scaled[0]], fill="red", width=max(3, image.width // 300))
                st.image(image, caption="빨간 선: Azure가 반환한 추출 근거", use_container_width=True)
            else:
                st.info("페이지 크기 정보가 없어 이미지 위에 표시할 수 없습니다.")
        else:
            st.info("PDF는 아래 페이지 번호와 좌표로 근거를 확인해 주세요. 좌표 단위는 Azure 응답의 페이지 unit을 따릅니다.")
        if regions:
            st.write([{"페이지": number, "좌표": points} for number, points in regions])

        st.divider()
        st.subheader("3. 사람이 확인한 뒤 캘린더 일정 만들기")
        st.caption("연도가 적혀 있지 않다면 임의로 보완하지 않아요. 아래에서 직접 확인해 주세요.")
        source = tuned if "tuned" in results else basic
        for name in ("event_title", "event_date", "start_time", "end_time", "location", "registration_deadline", "registration_url", "organizer"):
            st.session_state.setdefault(f"edit_{name}", source.get(name, ""))

        if source.get("event_date") and parse_explicit_date(source["event_date"]) is None:
            st.warning("포스터의 행사 날짜에 연도가 없거나 형식이 모호해요. 직접 확인한 연도를 입력해 주세요.")

        with st.form("calendar_review"):
            form_a, form_b = st.columns(2)
            with form_a:
                title = st.text_input("행사명", key="edit_event_title")
                date_text = st.text_input("행사 날짜 (YYYY-MM-DD)", key="edit_event_date")
                start_text = st.text_input("시작 시간 (HH:MM)", key="edit_start_time")
                end_text = st.text_input("종료 시간 (선택)", key="edit_end_time")
            with form_b:
                location = st.text_input("장소", key="edit_location")
                organizer = st.text_input("주최/주관", key="edit_organizer")
                url = st.text_input("신청 링크 (선택)", key="edit_registration_url")
                deadline = st.text_input("신청 마감일 (YYYY-MM-DD)", key="edit_registration_deadline")
            create_calendar = st.form_submit_button("✅ 검토한 정보로 .ics 생성", type="primary")

        if create_calendar:
            st.session_state.pop("deadline_bytes", None)

        deadline_label, days = deadline_status(deadline)
        if days is None:
            st.info(f"신청 마감: {deadline_label} · 연도를 포함해 확인해 주세요.")
        elif days < 0:
            st.warning(f"신청 마감: {deadline_label} ({deadline})")
        elif days <= 7:
            st.warning(f"신청 마감: {deadline_label} ({deadline})")
        else:
            st.success(f"신청 마감: {deadline_label} ({deadline})")
        if st.button("🔔 신청 마감 알림 파일 만들기"):
            try:
                st.session_state["deadline_bytes"] = make_deadline_ics(title, deadline, url)
            except ValueError as exc:
                st.error(str(exc))
        if st.session_state.get("deadline_bytes"):
            st.download_button("신청 마감 알림 .ics 다운로드", st.session_state["deadline_bytes"], file_name="registration-deadline.ics", mime="text/calendar")
            st.caption("마감일 오전 9시(한국 시간) 일정과 하루 전 알림입니다. 캘린더에 가져와야 알림을 받을 수 있습니다.")

        if create_calendar:
            try:
                description = f"주최/주관: {organizer}" if organizer else ""
                st.session_state["calendar_bytes"] = make_ics(
                    title=title,
                    date_text=date_text,
                    start_text=start_text,
                    end_text=end_text,
                    location=location,
                    description=description,
                    url=url,
                )
                st.success("캘린더 파일 생성 완료 · 다운로드 후 Google/Outlook 캘린더에 가져올 수 있어요.")
            except ValueError as exc:
                st.error(str(exc))

        if st.session_state.get("calendar_bytes"):
            st.download_button(
                "🗓️ 일정 파일(.ics) 다운로드",
                data=st.session_state["calendar_bytes"],
                file_name="lit-meetup-event.ics",
                mime="text/calendar; charset=utf-8",
                type="primary",
            )
    else:
        st.info("맞춤 일정 추출과 스키마 비교를 하려면 분석기 준비 후 비교 모드로 다시 실행해 주세요.")

st.divider()
st.caption("분석 요청은 Azure 사용량에 따라 요금이 발생할 수 있습니다. 추출된 일정은 자동 등록되지 않으며 사용자가 검토하고 다운로드합니다.")


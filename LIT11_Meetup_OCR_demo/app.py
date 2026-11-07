"""Interactive LIT poster demo. Run: streamlit run app.py"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, UnidentifiedImageError
from analyzer_schemas import FIELD_LABELS, BASE_DESCRIPTIONS, TUNED_DESCRIPTIONS, analyzer_id, make_analyzer_definition
from cu_client import CUClient, CUError
from demo_logic import MODE_LABELS, analysis_steps, validate_inputs, comparison_rows
from event_utils import normalize_fields, extract_markdown, source_regions, make_ics, make_deadline_ics

load_dotenv()
st.set_page_config(page_title="포스터를 일정으로 | LIT", page_icon="🗓️", layout="wide")
st.markdown("""
<style>
.block-container {max-width:1180px;padding-top:2rem;padding-bottom:3rem;}
.hero {background:linear-gradient(120deg,#102b41,#12636c);padding:32px;border-radius:20px;margin-bottom:24px;color:white;}
.hero .eyebrow {font-size:12px;letter-spacing:3px;color:#98e4d3;}
.hero h1 {color:white;font-size:2.3rem;line-height:1.25;margin:12px 0;}
.hero p {color:#daebef;margin-bottom:0;max-width:650px;}
div[data-testid="stExpander"] {border-radius:12px;}
@media(max-width:640px){.block-container{padding:1rem;}.hero{padding:22px;}.hero h1{font-size:1.7rem;}}
</style>
<div class="hero"><div class="eyebrow">LIT · DOCUMENT PLAYGROUND</div>
<h1>같은 포스터, 다른 질문.</h1>
<p>AI가 무엇을 찾아야 할지 직접 정해 보세요.<br>필드 설명을 바꾸고, 결과를 비교하고, 확인한 정보를 일정으로 가져갑니다.</p></div>
""", unsafe_allow_html=True)

MIME = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
endpoint = os.getenv("AZURE_CU_ENDPOINT", "")
deployments = {"gpt-4.1-mini": os.getenv("AZURE_CU_COMPLETION_DEPLOYMENT", "gpt-4.1-mini"),
               "text-embedding-3-small": os.getenv("AZURE_CU_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")}
records = st.session_state.setdefault("records", {})
for field in FIELD_LABELS:
    st.session_state.setdefault(f"schema_{field}", TUNED_DESCRIPTIONS[field])

def preset(values):
    for field in FIELD_LABELS:
        st.session_state[f"schema_{field}"] = values[field]

def show_source(data, name, result=None, field=None, widget_key="source"):
    if Path(name).suffix.lower() == ".pdf":
        st.info("PDF 원본은 내려받아 확인할 수 있습니다.")
        st.download_button("PDF 원본 보기", data, file_name=name, mime="application/pdf", key=widget_key)
        if result and field:
            regions = source_regions(result, field)
            st.caption("API가 제공한 근거 페이지와 좌표")
            st.write(regions or "위치 근거가 제공되지 않았습니다.")
        return
    try:
        img = Image.open(BytesIO(data)).convert("RGB")
        if result and field:
            regions = source_regions(result, field)
            pages = [p for c in result.get("result", {}).get("contents", []) for p in c.get("pages", [])]
            page = next((p for p in pages if p.get("pageNumber") == 1), {})
            if regions and page.get("width") and page.get("height"):
                draw = ImageDraw.Draw(img)
                for number, points in regions:
                    if number == 1 and points:
                        scaled = [(x * img.width / page["width"], y * img.height / page["height"]) for x, y in points]
                        draw.line(scaled + [scaled[0]], fill="#ff5757", width=max(3, img.width // 250))
                st.caption("빨간 선은 API가 반환한 근거 위치입니다.")
            else:
                st.caption("이 필드의 위치 근거가 제공되지 않았습니다.")
        st.image(img, caption=name, use_container_width=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        st.warning("이미지를 미리 볼 수 없습니다. 파일 형식을 확인해 주세요.")

st.subheader("01 · 자료 선택")
input_col, tip_col = st.columns([3, 2], gap="large")
with input_col:
    source_type = st.radio("자료 가져오기", ["내 파일", "예제 포스터"], horizontal=True)
    files = []
    if source_type == "내 파일":
        uploads = st.file_uploader("포스터를 놓거나 파일을 선택하세요", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True)
        files = [(f.name, f.getvalue()) for f in uploads or []]
    else:
        sample_dir = Path(__file__).parent / "samples"
        available = [p for p in sample_dir.glob("*.pdf")]
        selected = st.multiselect("예제 선택", available, default=available[:1], format_func=lambda p: {"easy_event.pdf":"기본 행사 안내", "tricky_event.pdf":"날짜가 여러 개인 안내"}.get(p.name, p.name))
        files = [(p.name, p.read_bytes()) for p in selected]
        if not available:
            st.info("예제 파일이 없습니다. 저장소의 samples 폴더를 함께 받아 주세요.")
    st.caption("최대 5개 · 파일당 10MB · JPG / PNG / PDF")
with tip_col:
    with st.container(border=True):
        st.markdown("**오늘의 미션**")
        st.write("신청 마감일과 행사 날짜를 구분해 보세요. 장소, 주최, 신청 링크의 설명도 각각 바꿀 수 있어요.")
        st.caption("설명을 수정해도 바로 요청하지 않습니다. 아래 실행 버튼을 눌러 적용하세요.")
if files:
    with st.expander("선택한 원본 미리보기"):
        preview_index = st.selectbox("미리 볼 파일", range(len(files)), format_func=lambda i: f"{i+1}. {files[i][0]}")
        preview_name, preview_data = files[preview_index]
        if len(preview_data) <= 10 * 1024 * 1024:
            show_source(preview_data, preview_name, widget_key="input_source")

st.subheader("02 · 분석 방식")
mode = st.radio("어떻게 읽을까요?", list(MODE_LABELS), format_func=MODE_LABELS.get, horizontal=True)
st.caption({"tuned":"직접 편집한 스키마로 정보를 추출합니다. 파일당 1회 분석.",
            "compare":"OCR · 기본 스키마 · 직접 편집한 스키마를 같은 파일에 적용합니다. 파일당 3회 분석.",
            "ocr":"구조화된 필드 없이 포스터의 글자만 읽습니다. 파일당 1회 분석."}[mode])
descriptions = {k: st.session_state[f"schema_{k}"] for k in FIELD_LABELS}
if mode != "ocr":
    with st.expander("스키마 편집 · 8개 필드를 각각 수정", expanded=True):
        st.caption("필드는 추출할 항목이고, 설명은 그 항목을 찾는 기준입니다. 한국어로 작성해도 됩니다.")
        a, b = st.columns(2)
        a.button("기본 설명 불러오기", on_click=preset, args=(BASE_DESCRIPTIONS,), use_container_width=True)
        b.button("개선 예시 불러오기", on_click=preset, args=(TUNED_DESCRIPTIONS,), use_container_width=True)
        columns = st.columns(2)
        for index, (field, label) in enumerate(FIELD_LABELS.items()):
            with columns[index % 2]:
                descriptions[field] = st.text_area(label, key=f"schema_{field}", height=110, max_chars=1000)
    changed = sum(descriptions[k].strip() != BASE_DESCRIPTIONS[k] for k in FIELD_LABELS)
    st.caption(f"기본 설명과 다른 필드 {changed}개 · 값이 달라져도 정확도가 높아졌다는 뜻은 아닙니다. 원문을 확인하세요.")

scope = st.radio("실행할 파일", ["모두", "하나만"], horizontal=True) if len(files) > 1 else "모두"
targets = files
if scope == "하나만":
    target_index = st.selectbox("실행 대상", range(len(files)), format_func=lambda i: f"{i+1}. {files[i][0]}")
    targets = [files[target_index]]
errors = validate_inputs(targets, descriptions, mode)
if not endpoint:
    st.info("현재 Azure 연결이 설정되지 않았습니다. 화면을 살펴볼 수 있으며, 실제 분석에는 서버 연결이 필요합니다.")
if files:
    for error in errors:
        st.warning(error)
cooldown = max(0, 10 - int(time.time() - st.session_state.get("last_request", 0)))
st.caption(f"이번 실행: 파일 {len(targets)}개 × {len(analysis_steps(mode))}회 = 최대 {len(targets)*len(analysis_steps(mode))}회 분석 요청. 새 스키마 준비에는 추가 시간이 걸릴 수 있습니다.")
if cooldown:
    st.caption(f"연속 요청 간격: 약 {cooldown}초 후 실행할 수 있습니다.")

if st.button("분석 실행" if mode == "ocr" else "이 스키마로 분석 실행", type="primary", use_container_width=True, disabled=bool(errors) or not endpoint):
    if cooldown:
        st.warning("연속 실행을 잠시 기다려 주세요.")
    else:
        st.session_state["last_request"] = time.time()
        client = None
        failures = 0
        prepared = set()
        with st.status("분석 요청 중…", expanded=True) as status:
            for name, data in targets:
                digest = hashlib.sha256(data).hexdigest()
                record = records.setdefault(digest, {"name":name, "data":data, "runs":[]})
                run = {"id":uuid.uuid4().hex, "mode":mode, "descriptions":dict(descriptions) if mode != "ocr" else {},
                       "results":{}, "error":"", "time":datetime.now().strftime("%H:%M:%S")}
                started = time.monotonic()
                try:
                    if client is None:
                        client = CUClient(endpoint=endpoint, api_key=os.getenv("AZURE_CU_KEY", ""))
                    for step in analysis_steps(mode):
                        st.write(f"{name} · " + {"ocr":"글자 읽는 중", "basic":"기본 스키마 분석", "tuned":"수정 스키마 분석"}[step])
                        if step == "ocr":
                            run["results"][step] = client.analyze("prebuilt-read", data, name, MIME[Path(name).suffix.lower()])
                        else:
                            tuned = step == "tuned"
                            overrides = descriptions if tuned else None
                            aid = analyzer_id(tuned, descriptions_override=overrides)
                            if aid not in prepared:
                                client.ensure_analyzer(aid, make_analyzer_definition(tuned, descriptions_override=overrides))
                                prepared.add(aid)
                            run["results"][step] = client.analyze(aid, data, name, MIME[Path(name).suffix.lower()], model_deployments=deployments)
                except (CUError, ValueError) as exc:
                    failures += 1
                    # Keep detailed service errors in server logs, not a shared visitor page.
                    print(f"Analysis failed: {type(exc).__name__}: {exc}")
                    run["error"] = "분석을 완료하지 못했습니다. 서버 연결·배포 설정을 확인한 뒤 재시도해 주세요."
                run["seconds"] = round(time.monotonic() - started, 1)
                record["runs"].append(run)
                record["runs"] = record["runs"][-10:]
                st.session_state["selected_record"] = digest
            status.update(label="일부 분석 실패 · 결과에서 확인해 주세요" if failures else "분석 완료", state="error" if failures else "complete", expanded=False)

st.divider()
st.subheader("03 · 결과 확인")
if not records:
    st.info("분석하면 여기에 파일별 결과가 나타납니다. 이전 결과는 재분석해도 유지됩니다.")
    st.stop()
st.caption("파일별 최근 10회 결과를 현재 접속 세션에서 보관합니다. 새로 접속하면 사라질 수 있습니다.")
for digest, record in records.items():
    latest = record["runs"][-1]
    with st.expander(f'{record["name"]} · {MODE_LABELS[latest["mode"]]} · {len(record["runs"])}회 기록'):
        if latest["error"]:
            st.warning(latest["error"])
        for step, result in latest["results"].items():
            if step == "ocr":
                st.text(extract_markdown(result) or "인식된 글자 없음")
            else:
                values, _ = normalize_fields(result)
                st.caption("기본 스키마" if step == "basic" else "수정 스키마")
                st.table([{"항목":label, "결과":values[k] or "정보 없음"} for k,label in FIELD_LABELS.items()])
chosen = st.selectbox("자세히 볼 포스터", list(records), key="selected_record", format_func=lambda k: records[k]["name"])
record = records[chosen]
run_index = st.selectbox("실행 기록", list(reversed(range(len(record["runs"])))), format_func=lambda i: f'{i+1}번째 · {MODE_LABELS[record["runs"][i]["mode"]]} · {record["runs"][i]["seconds"]}초', key=f"run_{chosen}_{record['runs'][-1]['id']}")
run = record["runs"][run_index]
results = run["results"]
st.caption("아래는 선택한 실행 당시의 결과입니다. 위 편집창의 수정은 다음 실행에 적용됩니다.")
if run["error"]:
    st.warning(run["error"])
result_tab, diff_tab, evidence_tab, calendar_tab = st.tabs(["추출 결과", "변경 전후", "원문 · 근거", "일정 만들기"])
structured = results.get("tuned") or results.get("basic")
values, confidence = normalize_fields(structured or {})
with result_tab:
    if structured:
        st.table([{"항목": label, "결과":values[k] or "정보 없음"} for k,label in FIELD_LABELS.items()])
    if "ocr" in results:
        with st.expander("OCR 원문", expanded=not bool(structured)):
            st.text(extract_markdown(results["ocr"]) or "인식된 글자 없음")
    with st.expander("이 실행에 사용한 설명 · 원본 응답"):
        if run["descriptions"]:
            st.table([{"필드":label, "설명":run["descriptions"][k]} for k,label in FIELD_LABELS.items()])
        st.caption("API 신뢰도는 정답률이 아닙니다. 제공된 값만 표시합니다.")
        st.json({FIELD_LABELS[k]:v for k,v in confidence.items() if v is not None})
        st.json(results)
    st.download_button("분석 기록 JSON 저장", json.dumps(run, ensure_ascii=False, indent=2), file_name="poster-analysis.json", mime="application/json")
with diff_tab:
    if "basic" in results and "tuned" in results:
        st.markdown("**같은 실행의 기본 → 수정 스키마**")
        st.table(comparison_rows(normalize_fields(results["basic"])[0], normalize_fields(results["tuned"])[0]))
    previous = [i for i in range(run_index) if "tuned" in record["runs"][i]["results"]]
    if "tuned" in results and previous:
        prev_index = st.selectbox("비교할 이전 실행", list(reversed(previous)), format_func=lambda i: f"{i+1}번째 실행")
        prev = record["runs"][prev_index]
        st.markdown("**이전 실행 → 선택한 실행**")
        st.table(comparison_rows(normalize_fields(prev["results"]["tuned"])[0], values))
        changed_rows = [{"필드":label, "이전 설명":prev["descriptions"].get(k,""), "현재 설명":run["descriptions"].get(k,"")} for k,label in FIELD_LABELS.items() if prev["descriptions"].get(k) != run["descriptions"].get(k)]
        if changed_rows:
            st.table(changed_rows)
        else:
            st.info("설명은 동일합니다. 동일한 설정으로 재실행해도 모델 결과가 달라질 수 있습니다.")
    elif not ("basic" in results and "tuned" in results):
        st.info("스키마를 바꾸고 같은 포스터를 다시 분석하면 이전 결과와 비교할 수 있습니다.")
    st.caption("결과 차이를 보여줍니다. 개선 여부는 원문과 대조해 판단하세요.")
with evidence_tab:
    field = st.selectbox("근거를 확인할 필드", list(FIELD_LABELS), format_func=FIELD_LABELS.get) if structured else None
    show_source(record["data"], record["name"], structured, field)
with calendar_tab:
    if not structured:
        st.info("스키마 튜닝 또는 비교 모드로 분석한 뒤 일정을 만들 수 있습니다.")
    else:
        st.caption("원문과 대조한 뒤 저장하세요. 날짜는 연도를 포함해 입력하고, 여러 날짜 중 한 일정을 선택해 주세요.")
        st.caption("종료 시간이 없으면 캘린더 일정 길이는 기본 1시간입니다.")
        prefix = run["id"]
        with st.form(f"calendar_{prefix}"):
            edited = {}
            cols = st.columns(2)
            for i,(k,label) in enumerate(FIELD_LABELS.items()):
                with cols[i%2]:
                    edited[k] = st.text_input(label, value=values[k], key=f"{prefix}_{k}")
            confirmed = st.checkbox("원문과 날짜·시간을 확인했습니다.")
            submitted = st.form_submit_button("확인한 정보로 일정 생성", type="primary")
        if submitted:
            st.session_state.pop("calendar_output", None)
            st.session_state.pop("deadline_output", None)
            if not confirmed:
                st.warning("원문 확인란을 선택해 주세요.")
            else:
                try:
                    event = make_ics(title=edited["event_title"], date_text=edited["event_date"], start_text=edited["start_time"],
                                     end_text=edited["end_time"], location=edited["location"], description=edited["organizer"], url=edited["registration_url"])
                    st.session_state["calendar_output"] = (prefix, event)
                    st.success("일정 파일을 만들었습니다.")
                    if edited["registration_deadline"].strip():
                        try:
                            deadline = make_deadline_ics(edited["event_title"], edited["registration_deadline"], edited["registration_url"])
                            st.session_state["deadline_output"] = (prefix, deadline)
                        except ValueError as exc:
                            st.warning(f"행사 일정은 생성했지만 마감 알림은 생성하지 못했습니다: {exc}")
                except ValueError as exc:
                    st.error(str(exc))
        output = st.session_state.get("calendar_output")
        if output and output[0] == prefix:
            st.download_button("일정 .ics 다운로드", output[1], file_name="event.ics", mime="text/calendar")
        deadline_output = st.session_state.get("deadline_output")
        if deadline_output and deadline_output[0] == prefix:
            st.download_button("신청 마감 알림 .ics 다운로드", deadline_output[1], file_name="deadline.ics", mime="text/calendar")
            st.caption("마감일 오전 9시(한국 시간) 일정과 하루 전 알림을 생성합니다.")
        st.caption("다운로드한 파일을 캘린더에 가져와야 등록됩니다.")

st.divider()
st.caption("LIT · Azure Content Understanding | 분석 요청에는 Azure 사용 요금이 발생할 수 있습니다.")

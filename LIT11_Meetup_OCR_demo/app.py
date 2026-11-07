"""Interactive LIT poster demo. Run: streamlit run app.py"""
from __future__ import annotations

import hashlib
from html import escape
from ui_tables import TABLE_CSS, table_html
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
from analyzer_schemas import FIELD_LABELS, BASE_DESCRIPTIONS, analyzer_id, make_analyzer_definition
from cu_client import CUClient, CUError
from demo_logic import MODE_LABELS, analysis_steps, validate_inputs, comparison_rows, file_options, history_options
from event_utils import normalize_fields, extract_markdown, source_regions, make_ics, make_deadline_ics

load_dotenv()
st.set_page_config(page_title="포스터를 일정으로 | LIT", page_icon="🗓️", layout="wide", initial_sidebar_state="auto")
st.markdown(f"<style>{TABLE_CSS}</style>", unsafe_allow_html=True)
st.markdown("""
<style>
.block-container {max-width:1100px;padding-top:2rem;padding-bottom:3rem;}
.hero {background:#102b41;padding:24px 28px;border-radius:16px;margin-bottom:24px;color:#fff;}
.hero .eyebrow {font-size:14px;letter-spacing:1px;color:#98e4d3;}
.hero h1 {color:#fff;font-size:2rem;line-height:1.3;margin:8px 0;}
.hero p {color:#daebef;margin:0;max-width:55ch;line-height:1.7;}
[data-testid="stMain"] p,[data-testid="stSidebar"] p {line-height:1.65;overflow-wrap:anywhere;}
[data-testid="stCaptionContainer"] p {font-size:0.9rem;color:#475569;}
[data-testid="stText"] pre {white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:1rem;line-height:1.75;}
.ocr-output {background:#f1f5f9;color:#0f172a;border:1px solid #cbd5e1;border-radius:12px;padding:20px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:1rem;line-height:1.8;margin:12px 0 20px;}
[data-testid="stTextArea"] textarea {font-size:1rem;line-height:1.6;}
[data-testid="stTextInput"] input {font-size:1rem;}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button,[data-testid="stFormSubmitButton"] button {min-height:44px;}
[data-testid="stRadio"] label {min-height:44px;align-items:center;}
button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible {outline:3px solid #1d4ed8;outline-offset:3px;}
div[data-testid="stExpander"] {border-radius:12px;}

@media(max-width:640px){
  .block-container{padding:1rem;}
  .hero{padding:20px;}.hero h1{font-size:1.6rem;}
  [data-testid="stHorizontalBlock"]{flex-wrap:wrap;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important;min-width:0;}
  [role="tablist"]{flex-wrap:wrap;gap:4px;}
  [role="tab"]{min-height:44px;white-space:normal;}
}
</style>
<div class="hero"><div class="eyebrow">LIT · DOCUMENT PLAYGROUND</div>
<h1>포스터를 읽고, 일정으로.</h1>
<p>글자만 읽어 보거나, 필요한 정보를 정해 추출해 보세요.</p></div>
""", unsafe_allow_html=True)

MIME = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
endpoint = os.getenv("AZURE_CU_ENDPOINT", "")
deployments = {"gpt-4.1-mini": os.getenv("AZURE_CU_COMPLETION_DEPLOYMENT", "gpt-4.1-mini"),
               "text-embedding-3-small": os.getenv("AZURE_CU_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")}
records = st.session_state.setdefault("records", {})
saved_schema = st.session_state.setdefault("saved_schema", dict(BASE_DESCRIPTIONS))
for field in FIELD_LABELS:
    st.session_state.setdefault(f"schema_{field}", saved_schema[field])

def remember_schema(field):
    saved_schema[field] = st.session_state[f"schema_{field}"]

def preset(values):
    for field in FIELD_LABELS:
        saved_schema[field] = values[field]
        st.session_state[f"schema_{field}"] = values[field]

def show_table(rows):
    st.markdown(table_html(rows), unsafe_allow_html=True)

def show_ocr_text(text):
    st.markdown(f'<div class="ocr-output" role="region" aria-label="OCR 추출 결과">{escape(text)}</div>', unsafe_allow_html=True)

def remember_sample(name):
    st.session_state["sample_choices"][name] = st.session_state[f"sample_{name}"]

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
    source_type = st.radio("자료 가져오기", ["내 파일", "예제 포스터"], horizontal=True, key="input_source_type")
    files = []
    if source_type == "내 파일":
        uploads = st.file_uploader("포스터를 놓거나 파일을 선택하세요", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True)
        files = [(f.name, f.getvalue()) for f in uploads or []]
    else:
        sample_dir = Path(__file__).parent / "samples"
        sample_labels = {
            "knu.jpg": "경북대학교 별빛수기 공모전",
            "lit11.jpg": "2026 LIT 11월 Meetup",
            "lit6.jpg": "2026 LIT 6월 Meetup",
        }
        available = [sample_dir / name for name in sample_labels if (sample_dir / name).is_file()]
        choices = st.session_state.setdefault("sample_choices", {name: i == 0 for i, name in enumerate(sample_labels)})
        st.write("분석할 예제를 선택하세요. 여러 개 선택할 수 있습니다.")
        selected = []
        for sample in available:
            widget_key = f"sample_{sample.name}"
            st.session_state.setdefault(widget_key, choices[sample.name])
            if st.checkbox(sample_labels[sample.name], key=widget_key, on_change=remember_sample, args=(sample.name,)):
                selected.append(sample)
        files = [(p.name, p.read_bytes()) for p in selected]
        if not available:
            st.info("예제 이미지가 없습니다. samples 폴더에 knu_slogan.png, lit11.jpg, lit6.jpg를 넣어 주세요. 내 파일에서 직접 올려도 분석할 수 있습니다.")
    st.caption("최대 5개 · 파일당 10MB · JPG / PNG / PDF")
with tip_col:
    with st.container(border=True):
        st.markdown("**처음이라면 이렇게 해 보세요**")
        st.markdown("① 포스터 선택\n\n② 글자만 읽기\n\n③ 스키마 튜닝")
        st.caption("스키마는 행사 날짜·장소처럼 AI가 찾아야 할 항목과 그 설명입니다.")
if files:
    with st.expander("선택한 원본 미리보기"):
        previews = file_options(files)
        if st.session_state.get("preview_file") not in previews:
            st.session_state["preview_file"] = next(iter(previews))
        preview_id = st.selectbox("미리 볼 파일", list(previews), format_func=lambda k: previews[k][0], key="preview_file")
        preview_name, preview_data = previews[preview_id]
        if len(preview_data) <= 10 * 1024 * 1024:
            show_source(preview_data, preview_name, widget_key="input_source")

st.subheader("02 · 분석 방식")
mode = st.radio("어떻게 읽을까요?", ["ocr", "tuned"], format_func=MODE_LABELS.get, horizontal=True)
st.caption({"tuned":"직접 편집한 스키마로 정보를 추출합니다. 파일당 1회 분석.",
            "ocr":"구조화된 필드 없이 포스터의 글자만 읽습니다. 파일당 1회 분석."}[mode])
descriptions = dict(saved_schema)
if mode == "tuned":
    with st.sidebar:
        st.subheader("스키마 설정")
        st.write("각 항목의 설명을 확인하고 필요하면 수정하세요.")
        editing = st.toggle("수정 활성화", value=False, key="schema_editing")
        st.caption("수정 중" if editing else "읽기 전용 · 수정을 켜면 설명을 바꿀 수 있어요.")
        st.button("기본 설명으로 초기화", on_click=preset, args=(BASE_DESCRIPTIONS,), use_container_width=True, disabled=not editing)
        for field, label in FIELD_LABELS.items():
            with st.expander(label, expanded=False):
                descriptions[field] = st.text_area(label, key=f"schema_{field}", height=140, max_chars=1000, disabled=not editing, on_change=remember_schema, args=(field,))
        st.caption("수정을 잠가도 설명은 유지됩니다. 분석 실행을 눌러야 결과에 적용됩니다.")
    st.info("왼쪽 스키마 설정에서 ‘수정 활성화’를 켜면 설명을 바꿀 수 있어요. 휴대폰에서는 왼쪽 위 메뉴를 여세요.")

scope = st.radio("실행할 파일", ["모두", "하나만"], horizontal=True) if len(files) > 1 else "모두"
targets = files
if scope == "하나만":
    target_options = file_options(files)
    if st.session_state.get("target_file") not in target_options:
        st.session_state["target_file"] = next(iter(target_options))
    target_id = st.selectbox("실행 대상", list(target_options), format_func=lambda k: target_options[k][0], key="target_file")
    targets = [target_options[target_id]]
errors = validate_inputs(targets, descriptions, mode)
if not endpoint:
    st.info("현재 Azure 연결이 설정되지 않았습니다. 화면을 살펴볼 수 있으며, 실제 분석에는 서버 연결이 필요합니다.")
if files:
    for error in errors:
        st.warning(error)
cooldown = max(0, 10 - int(time.time() - st.session_state.get("last_request", 0)))
st.caption(f"선택한 파일 {len(targets)}개 · 파일당 1회 분석 · 실행 시 Azure 사용 요금이 발생할 수 있습니다.")
if cooldown:
    st.caption(f"연속 요청 간격: 약 {cooldown}초 후 실행할 수 있습니다.")

if st.button(f"글자 읽기 · {len(targets)}개 파일" if mode == "ocr" else f"정보 추출 · {len(targets)}개 파일", type="primary", use_container_width=True, disabled=bool(errors) or not endpoint):
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
                       "methods":{}, "model_deployments":dict(deployments) if mode != "ocr" else {},
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
                            definition = make_analyzer_definition(tuned, descriptions_override=overrides)
                            run["methods"] = {k: v["method"] for k, v in definition["fieldSchema"]["fields"].items()}
                            aid = analyzer_id(tuned, descriptions_override=overrides)
                            if aid not in prepared:
                                client.ensure_analyzer(aid, definition)
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
                st.session_state[f"history_{digest}"] = run["id"]
            status.update(label="일부 분석 실패 · 결과에서 확인해 주세요" if failures else "분석 완료", state="error" if failures else "complete", expanded=False)

st.divider()
st.subheader("03 · 결과 확인")
if not records:
    st.info("분석하면 여기에 파일별 결과가 나타납니다. 이전 결과는 재분석해도 유지됩니다.")
    st.stop()
if len(records) > 1:
    with st.expander("다른 포스터 결과도 함께 보기"):
        for digest, record in records.items():
            latest = record["runs"][-1]
            st.markdown(f'**{record["name"]} · {MODE_LABELS[latest["mode"]]}**')
            if latest["error"]:
                st.warning(latest["error"])
            if latest["mode"] == "ocr":
                show_ocr_text(extract_markdown(latest["results"].get("ocr", {})) or "인식된 글자 없음")
            else:
                summary, _ = normalize_fields(latest["results"].get("tuned", {}))
                show_table([{"항목":label, "결과":summary[k] or "정보 없음"} for k,label in FIELD_LABELS.items()])
if st.session_state.get("selected_record") not in records:
    st.session_state["selected_record"] = next(iter(records))
chosen = st.selectbox("확인할 포스터", list(records), key="selected_record", format_func=lambda k: records[k]["name"])
record = records[chosen]
runs_by_id = history_options(record["runs"])
history_key = f"history_{chosen}"
if st.session_state.get(history_key) not in runs_by_id:
    st.session_state[history_key] = next(iter(runs_by_id))
st.caption("OCR과 스키마 튜닝 기록을 함께 표시합니다. 선택한 기록에 맞는 결과 화면이 열립니다.")
selected_run_id = st.selectbox(
    "실행 기록",
    list(runs_by_id),
    format_func=lambda rid: f'{next(i+1 for i,r in enumerate(record["runs"]) if r["id"] == rid)}번째 · {MODE_LABELS[runs_by_id[rid]["mode"]]} · {runs_by_id[rid]["seconds"]}초',
    key=history_key,
)
st.caption("파일별 최근 10회 기록을 이 접속 세션에서 보관합니다.")
run = runs_by_id[selected_run_id]
run_index = next(i for i, item in enumerate(record["runs"]) if item["id"] == selected_run_id)
results = run["results"]
st.caption(f"선택한 결과: {record['name']} · {MODE_LABELS[run['mode']]} · 처리 시간 {run['seconds']}초")
if run["error"]:
    st.warning(run["error"])
if run["mode"] == "ocr":
    st.markdown("**추출 결과**")
    ocr_text = extract_markdown(results.get("ocr", {}))
    if ocr_text:
        st.markdown("아래 글자는 포스터에 적힌 내용을 읽은 결과입니다.")
        show_ocr_text(ocr_text)
        st.download_button("추출한 글자 저장", ocr_text, file_name="poster-text.txt", mime="text/plain; charset=utf-8")
    elif not run["error"]:
        st.info("인식된 글자가 없습니다.")
    st.stop()
result_tab, diff_tab, evidence_tab, calendar_tab = st.tabs(["추출 결과", "변경 전후", "원문 · 근거", "일정 만들기"])
structured = results.get("tuned") or results.get("basic")
values, confidence = normalize_fields(structured or {})
with result_tab:
    if structured:
        show_table([{"항목": label, "결과":values[k] or "정보 없음"} for k,label in FIELD_LABELS.items()])
    if "ocr" in results:
        with st.expander("OCR 원문", expanded=not bool(structured)):
            show_ocr_text(extract_markdown(results["ocr"]) or "인식된 글자 없음")
    with st.expander("이 실행에 사용한 설명 · 원본 응답"):
        if run["descriptions"]:
            st.caption("현재 편집창이 아니라, 선택한 실행에 실제로 사용한 설명입니다.")
            for k, label in FIELD_LABELS.items():
                st.markdown(f"**{label}**")
                st.write(run["descriptions"][k])
        if run.get("methods"):
            st.caption("이 실행의 필드별 추출 방식")
            show_table([{"필드":FIELD_LABELS[k], "방식":v} for k,v in run["methods"].items()])
        else:
            st.caption("이전 버전 기록에는 추출 방식 정보가 없습니다.")
        st.caption("API 신뢰도는 정답률이 아닙니다. 제공된 값만 표시합니다.")
        st.json({FIELD_LABELS[k]:v for k,v in confidence.items() if v is not None})
        st.json(results)
    st.download_button("분석 기록 JSON 저장", json.dumps(run, ensure_ascii=False, indent=2), file_name="poster-analysis.json", mime="application/json")
with diff_tab:
    if "basic" in results and "tuned" in results:
        st.markdown("**같은 실행의 기본 → 수정 스키마**")
        show_table(comparison_rows(normalize_fields(results["basic"])[0], normalize_fields(results["tuned"])[0]))
    previous = [i for i in range(run_index) if "tuned" in record["runs"][i]["results"]]
    if "tuned" in results and previous:
        prev_index = st.selectbox("비교할 이전 실행", list(reversed(previous)), format_func=lambda i: f"{i+1}번째 실행")
        prev = record["runs"][prev_index]
        if not prev.get("methods") or not run.get("methods"):
            st.warning("추출 방식이 기록되지 않은 실행이 포함되어 있습니다. 설명 변경만의 효과를 비교하려면 새 버전에서 두 번 분석해 주세요.")
        elif prev["methods"] != run["methods"] or prev.get("model_deployments") != run.get("model_deployments"):
            st.warning("추출 방식 또는 모델 배포가 달라졌습니다. 아래 차이를 설명 변경만의 효과로 해석할 수 없습니다.")
        else:
            st.caption("두 실행의 필드별 추출 방식과 모델 배포 설정이 같습니다.")
        st.markdown("**이전 실행 → 선택한 실행**")
        show_table(comparison_rows(normalize_fields(prev["results"]["tuned"])[0], values))
        changed_rows = [{"필드":label, "이전 설명":prev["descriptions"].get(k,""), "현재 설명":run["descriptions"].get(k,"")} for k,label in FIELD_LABELS.items() if prev["descriptions"].get(k) != run["descriptions"].get(k)]
        if changed_rows:
            show_table(changed_rows)
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
        st.info("스키마 튜닝으로 분석한 뒤 일정을 만들 수 있습니다.")
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

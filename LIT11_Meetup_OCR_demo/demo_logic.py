"""Pure helpers for request planning, validation and result comparison."""
from analyzer_schemas import FIELD_LABELS
import hashlib

MODE_LABELS = {"tuned": "스키마 튜닝", "compare": "기본 · 수정 비교", "ocr": "글자만 읽기"}

def file_options(files):
    """Selection follows file identity, not a position in a changing list."""
    return {hashlib.sha256(data).hexdigest() + ":" + name: (name, data) for name, data in files}

def history_options(runs):
    """Keep every mode, newest first, keyed by stable run IDs."""
    return {run["id"]: run for run in reversed(runs)}

def analysis_steps(mode):
    return {"tuned": ("tuned",), "compare": ("ocr", "basic", "tuned"), "ocr": ("ocr",)}[mode]

def validate_inputs(files, descriptions, mode):
    errors = []
    if not files:
        errors.append("포스터를 먼저 선택해 주세요.")
    if len(files) > 5:
        errors.append("한 번에 최대 5개 파일을 분석할 수 있어요.")
    for name, data in files:
        if not data or len(data) > 10 * 1024 * 1024:
            errors.append(f"{name}: 비어 있거나 10MB를 초과한 파일입니다.")
    if mode != "ocr":
        for key, label in FIELD_LABELS.items():
            value = descriptions.get(key, "")
            if not isinstance(value, str) or not value.strip() or len(value) > 1000:
                errors.append(f"{label}: 설명을 1~1000자로 입력해 주세요.")
    return errors

def comparison_rows(before, after):
    return [{"필드": label, "이전": before.get(key) or "—", "현재": after.get(key) or "—",
             "변경": "변경됨" if before.get(key, "") != after.get(key, "") else "동일"}
            for key, label in FIELD_LABELS.items()]

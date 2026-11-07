# 스키마 튜닝 데모

개발 브랜치: feature/live-schema-tuning. 기존 Demo 브랜치는 유지합니다.

## 실행
LIT11_Meetup_OCR_demo 폴더에서:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

기존 환경변수를 그대로 사용합니다:
AZURE_CU_ENDPOINT, AZURE_CU_KEY, AZURE_CU_COMPLETION_DEPLOYMENT,
AZURE_CU_EMBEDDING_DEPLOYMENT. 키를 공개 저장소에 저장하지 마세요.

## 동작
- 글자만 읽기: OCR 분석 1회.
- 스키마 튜닝: 파일당 분석 1회. 왼쪽 사이드바에서 8개 필드 설명 확인.
- 모드 순서는 글자만 읽기 → 스키마 튜닝. 별도 비교 모드는 제공하지 않음.
- 스키마는 BASE_DESCRIPTIONS 하나만 사용. 별도 개선 예시는 제공하지 않음.
- 사이드바의 수정 활성화를 켜면 기본 설명을 항목별로 직접 편집할 수 있음.
- 기본 설명으로 초기화 버튼으로 작성 내용을 원래 기본값으로 복원.
  수정을 잠가도 입력한 설명은 유지되고 다음 분석에 사용됨.
  글자만 읽기에서는 스키마 편집이 비활성화됨.
- 입력 파일 전체 또는 한 파일만 실행. 파일당 최대 10MB, 요청당 최대 5개.
- 파일별로 현재 접속 세션의 최근 10회 결과와 당시 설명을 보관.
- 필드 결과 차이와 설명 차이를 함께 표시. 결과 변경을 정확도 향상으로 표시하지 않음.
- 실패 시 이전 결과를 유지하며, 부분 결과와 실패 상태를 함께 표시.
- 캘린더 생성은 원문 확인 후 실행. 종료 시간 미입력 시 기존 동작대로 1시간.
- 예제는 samples 폴더의 knu_slogan.png, lit11.jpg, lit6.jpg 원본 이미지를 사용.

## 발표 전 확인
실제 Azure 분석 및 브라우저에서의 화면 확인은 별도로 필요합니다.
로컬 환경에서 Streamlit을 실행할 수 없어 화면을 렌더링해 검증하지 못했습니다.
단위 테스트는 python -m unittest discover -s tests -v 로 실행합니다.

같은 설명 조합은 같은 분석기 ID를 사용합니다. 다른 설명 조합은 새 Azure 분석기를
생성할 수 있으므로 발표 전 리소스 한도를 확인하고 사용하지 않는 분석기를 관리해야 합니다.
10초 간격 제한은 세션 단위입니다. 공개 서비스의 전체 요청량/비용 제한이나
동시 생성 충돌 방지를 대신하지 않습니다. 이 부분은 서버 연결 담당자와 점검하세요.

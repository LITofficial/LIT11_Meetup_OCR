# 발표·모바일 체험 화면 개선 기준

대상: 발표 화면을 보는 관객과 QR로 휴대폰에 접속하는 체험자.
기준은 아래 원문을 확인한 뒤 이 프로젝트에 맞게 적용했다.
이 문서는 접근성 인증이나 실제 브라우저 검사 완료를 의미하지 않는다.

## 조사와 적용

| 기본기 | 근거 | 적용 |
|---|---|---|
| 대비 | WCAG 2.2 일반 텍스트 최소 4.5:1, 큰 텍스트 3:1 | 밝은 배경·짙은 글자 테마. 보조 설명도 읽을 수 있는 짙은 회색 사용 |
| 시각적 위계와 근접성 | NN/g의 크기·위계·대비·게슈탈트 원칙 | 작은 소개 영역, 단계 제목, 입력 근처의 안내, 실행 버튼에 구체적인 동작명 표시 |
| 단계적 공개 | NN/g: 중요한 선택을 먼저, 전문 설정은 요청 시 표시 | OCR에서는 스키마 설정 숨김. 튜닝에서만 사이드바 표시. 예시·과거 기록·JSON은 펼치기 안에 배치 |
| 모바일 줄바꿈 | WCAG Reflow는 320 CSS px에서도 내용 손실 없는 재배치를 목표로 함 | 좁은 화면에서 열을 1열로, 긴 OCR 문장 줄바꿈, 탭 줄바꿈, 표 내부 가로 스크롤 |
| 조작 크기와 키보드 포커스 | WCAG 2.5.8 최소 24×24 CSS px 또는 간격 예외 | 주요 버튼·탭 높이는 프로젝트 목표로 44px, 라디오 레이블 간격 확대, 키보드 포커스 테두리 추가 |
| 현재 작업과 결과의 연결 | 모드에 필요한 정보만 보여주는 프로젝트 적용 판단 | 모드별 파일·실행 이력 필터링. 파일명·모드·처리 시간을 결과 바로 위에 표시 |

## 구체적인 변경

- OCR로 전환해도 편집한 스키마 설명은 별도 세션 값으로 유지.
- 결과를 요약과 상세에 항상 중복 표시하던 구성을 정리.
  여러 포스터를 한 번에 보는 기능은 접힌 영역에 유지.
- 최신 결과를 먼저 표시하고 이전 실행 선택은 접어 둠.
- ‘분석 실행’ 대신 ‘글자 읽기 · N개 파일’ / ‘정보 추출 · N개 파일’ 표시.
- 설명 전문은 좁은 표 대신 필드 제목 아래 본문으로 표시.
- 한국어 본문과 입력은 읽기 쉬운 행간, OCR에는 일반 글꼴·자동 줄바꿈 적용.
- 테마는 .streamlit/config.toml에서 관리. Streamlit 실행 폴더를 데모 폴더로 유지.

## 검증

- Python 문법 검사 및 기존 단위 테스트 20개 통과.
- 지정한 색상 조합의 대비율을 계산해 일반 텍스트 목표 4.5:1 이상 확인.
- 실제 브라우저 렌더링, 320/390/1280px 화면, 키보드 이동, 200% 확대와
  스크린리더 동작은 이 환경에서 확인하지 못함.
- CSS 일부는 Streamlit의 data-testid 구조를 사용하므로 버전 업데이트 시 확인 필요.
- 공개 전 OCR → 튜닝 → OCR 전환, 편집한 설명 유지, 여러 파일의 결과 선택,
  모바일에서 사이드바 열기, 캘린더 입력/다운로드를 실제 기기에서 확인할 것.

## 참고 원문

- W3C Contrast: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum
- W3C Reflow: https://www.w3.org/WAI/WCAG22/Understanding/reflow
- W3C Target Size: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum
- NN/g Progressive Disclosure: https://www.nngroup.com/articles/progressive-disclosure/
- NN/g Visual Design Principles: https://www.nngroup.com/articles/principles-visual-design/
- Streamlit Widget Behavior: https://docs.streamlit.io/develop/concepts/architecture/widget-behavior

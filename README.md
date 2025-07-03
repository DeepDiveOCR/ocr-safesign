# SafeSign - 부동산 계약 분석 시스템

부동산 임대차 계약서와 등기부등본을 AI로 분석하여 전세사기 위험도를 탐지하는 웹 애플리케이션입니다.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![EasyOCR](https://img.shields.io/badge/EasyOCR-1.7.1-orange.svg)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-1.5%20Flash-yellow.svg)
![Firebase](https://img.shields.io/badge/Firebase-Admin%20SDK-red.svg)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-3.0-38B2AC.svg)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E.svg)
![MIT License](https://img.shields.io/badge/License-MIT-green.svg)

## 주요 기능

### 1. 문서 인식 및 텍스트 추출
- 등기부등본과 임대차 계약서 이미지 업로드
- EasyOCR을 활용한 한글 텍스트 인식
- Gemini AI를 통한 텍스트 보정 및 구조화

### 2. 실시간 진행 상황 표시
- 4단계 진행 상황 모니터링
  - 문서 인식 중 (25%)
  - 부동산 시세 조회 중 (50%)
  - 문서 분석 중 (75%)
  - 최종 리포트 작성 중 (100%)
- 시각적 Progress Bar와 단계별 상태 표시

### 3. 종합 위험도 분석
- **소유자-임대인 일치 여부**: 등기부등본 소유주와 계약서 임대인 비교
- **주소 일치 여부**: 계약서 주소와 등기부등본 주소 검증
- **시세 대비 보증금 위험**: 실거래가 API 기반 시세 비교
- **담보 여유 초과 여부**: 근저당권과 보증금 비율 분석

### 4. 특약사항 분석
- 계약서 특약사항 자동 추출
- 위험도별 분류 (위험/주의/안전)
- 종합 의견 및 권고사항 제공

### 5. 사용자 관리
- 카카오 로그인 연동
- 분석 기록 저장 및 조회
- Firebase Firestore 기반 데이터 관리

## 기술 스택

### Backend
- **Flask**: 웹 프레임워크
- **EasyOCR**: 한글 OCR 엔진 (커스텀 모델 사용)
- **Google Gemini AI**: 텍스트 분석 및 보정
- **Firebase Admin SDK**: 사용자 인증 및 데이터베이스
- **OpenCV**: 이미지 전처리

### Frontend
- **HTML5/CSS3**: 반응형 웹 디자인
- **JavaScript (ES6+)**: 동적 UI 구현
- **Tailwind CSS**: 스타일링 프레임워크
- **Firebase Auth**: 클라이언트 인증

### 외부 API
- **국토교통부 실거래가 API**: 부동산 시세 조회
- **공공주소 API**: 주소 정규화
- **카카오 로그인 API**: 소셜 로그인

## 프로젝트 구조

```
real-estate-analyzer/
├── app.py                  # Flask 애플리케이션 진입점
├── config.py               # 설정 및 외부 서비스 초기화
├── requirements.txt        # Python 의존성
├── Dockerfile              # Docker 컨테이너 설정
├── .EasyOCR/               # 커스텀 파인튜닝 OCR 모델
│   ├── model/              # 모델 파일 저장소
│   │   └── finetuned.pth   # 파인튜닝된 OCR 모델
│   └── user_network/       # 사용자 정의 네트워크
│       ├── finetuned.py    # 모델 설정 파일
│       └── finetuned.yaml  # 모델 구성 파일
├── routes/                 # API 라우트
│   ├── auth_routes.py      # 인증 관련 API
│   └── analysis_routes.py  # 분석 관련 API
├── utils/                  # 유틸리티 모듈
│   ├── image_processor.py  # 이미지 전처리
│   └── text_parser.py      # 텍스트 파싱
├── rule/                   # 비즈니스 로직
│   └── rules.py            # 위험도 판단 규칙
├── estimator/              # 시세 추정
│   └── median_price.py     # 중위가격 계산
├── static/                 # 정적 파일
│   ├── main.js             # 프론트엔드 로직
│   └── style.css           # 스타일시트
└── templates/              # HTML 템플릿
    └── index.html          # 메인 페이지
```

## 설치 및 실행

### 1. 환경 설정
```bash
# 저장소 클론
git clone https://github.com/DeepDiveOCR/ocr-safesign.git
cd ocr-safesign/real-estate-analyzer

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```env
# Google Gemini API를 위한 키
GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"

# 카카오 로그인 기능 구현을 위한 REST API 키
KAKAO_REST_API_KEY="YOUR_KAKAO_REST_API_KEY"

# 카카오 지도 등 JavaScript SDK 사용을 위한 키
KAKAO_JS_KEY="YOUR_KAKAO_JAVASCRIPT_KEY"

# 주소 유효성 검사 등 공공데이터포털 주소 API 인증키
CONFIRM_KEY="YOUR_PUBLIC_DATA_API_KEY"

# 애플리케이션이 실행될 포트 번호
PORT=5000

# 국토교통부 실거래가 등 공공데이터포털 서비스 키
SERVICEKEY="YOUR_DATA_SERVICE_KEY"
```

### 3. Firebase 설정
- Firebase 프로젝트 생성
- 서비스 계정 키 파일을 `firebase-credentials.json`으로 저장
- Firebase 설정을 `static/main.js`에 추가

### 4. 애플리케이션 실행
```bash
python app.py
```

서버가 `http://localhost:5000`에서 실행됩니다.

## 사용 방법

### 1. 로그인
- 카카오 계정으로 로그인 및 회원가입
- 서비스 이용을 위한 필수 인증

### 2. 문서 업로드
- 등기부등본 이미지 업로드
- 임대차 계약서 이미지 업로드
- 드래그 앤 드롭 또는 파일 선택

### 3. 텍스트 추출
- "AI로 텍스트 추출 및 보정" 버튼 클릭
- OCR 처리 및 AI 보정 진행
- 추출된 텍스트 검토 및 수정 가능

### 4. 종합 분석
- "종합 분석 실행" 버튼 클릭
- 실시간 진행 상황 확인
- 위험도 분석 결과 확인

### 5. 결과 확인
- 핵심 정보 검증 결과
- 특약사항 분석
- 종합 위험도 등급
- 권고사항 및 주의사항

## 주요 API 엔드포인트

### 인증
- `POST /kakao-login`: 카카오 로그인 처리

### 분석
- `POST /ocr`: OCR 텍스트 추출
- `POST /process-analysis`: 종합 분석 실행

## 보안 고지사항

- 본 서비스는 법적 효력이 있는 문서가 아닌 참고용 분석 결과를 제공합니다
- 정확한 법적 판단을 위해서는 전문가 상담이 필요합니다
- 업로드된 문서는 분석 후 즉시 삭제됩니다

## Credits

이 프로젝트는 다음 팀원들의 협력으로 개발되었습니다:

- **최정훈** - [@Jeonghoonchoi74](https://github.com/Jeonghoonchoi74)
- **안효서** - [@pokqok](https://github.com/pokqok)
- **박지연** - [@jiyeon22](https://github.com/jiyeon22)
- **이서준** - [@seojun133](https://github.com/seojun133)
- **이재진** - [@LeeJaeJin00](https://github.com/LeeJaeJin00)

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.


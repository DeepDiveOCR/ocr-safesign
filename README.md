# SafeSign - 부동산 계약 분석 시스템

<div align="center">

![SafeSign Logo](https://img.shields.io/badge/SafeSign-부동산계약분석-00D4AA?style=for-the-badge&logo=shield-check&logoColor=white)

**AI 기반 부동산 계약서 분석으로 전세사기 예방**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)](https://flask.palletsprojects.com/)
[![EasyOCR](https://img.shields.io/badge/EasyOCR-1.7.1-orange.svg)](https://github.com/JaidedAI/EasyOCR)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-1.5%20Flash-yellow.svg)](https://ai.google.dev/gemini)
[![Firebase](https://img.shields.io/badge/Firebase-Admin%20SDK-red.svg)](https://firebase.google.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-3.0-38B2AC.svg)](https://tailwindcss.com/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E.svg)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[데모 보기](추가예정) • [이슈 리포트](https://github.com/DeepDiveOCR/ocr-safesign/issues) • [기능 제안](https://github.com/DeepDiveOCR/ocr-safesign/issues)

</div>

---

> ** 전세사기로부터 안전한 계약을 위한 AI 분석 솔루션**  
> 부동산 임대차 계약서와 등기부등본을 AI로 분석하여 전세사기 위험도를 탐지하는 웹 애플리케이션입니다.

<div align="center">

![GitHub stars](https://img.shields.io/github/stars/DeepDiveOCR/ocr-safesign?style=social)
![GitHub forks](https://img.shields.io/github/forks/DeepDiveOCR/ocr-safesign?style=social)
![GitHub issues](https://img.shields.io/github/issues/DeepDiveOCR/ocr-safesign)
![GitHub pull requests](https://img.shields.io/github/issues-pr/DeepDiveOCR/ocr-safesign)
![GitHub contributors](https://img.shields.io/github/contributors/DeepDiveOCR/ocr-safesign)

</div>

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![EasyOCR](https://img.shields.io/badge/EasyOCR-1.7.1-orange.svg)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-1.5%20Flash-yellow.svg)
![Firebase](https://img.shields.io/badge/Firebase-Admin%20SDK-red.svg)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-3.0-38B2AC.svg)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E.svg)
![MIT License](https://img.shields.io/badge/License-MIT-green.svg)

##  주요 기능

<div align="center">

| **문서 인식** | **실시간 분석** | **위험 탐지** | **특약사항 분석** | **사용자 관리** |
|:---:|:---:|:---:|:---:|:---:|
| ![OCR](https://img.shields.io/badge/EasyOCR-한글인식-orange) | ![Progress](https://img.shields.io/badge/Progress-4단계-blue) | ![Risk](https://img.shields.io/badge/Risk-실시간검증-red) | ![Analysis](https://img.shields.io/badge/Analysis-AI분석-green) | ![Auth](https://img.shields.io/badge/Auth-카카오로그인-yellow) |

</div>

### 🔍 **문서 인식 및 텍스트 추출**
- 등기부등본과 임대차 계약서 이미지 업로드
- EasyOCR을 활용한 한글 텍스트 인식
- Gemini AI를 통한 텍스트 보정 및 구조화

### **실시간 진행 상황 표시**
- 4단계 진행 상황 모니터링
  - 문서 인식 중 (25%)
  - 부동산 시세 조회 중 (50%)
  - 문서 분석 중 (75%)
  - 최종 리포트 작성 중 (100%)
- 시각적 Progress Bar와 단계별 상태 표시

### **종합 위험도 분석**
- **소유자-임대인 일치 여부**: 등기부등본 소유주와 계약서 임대인 비교
- **주소 일치 여부**: 계약서 주소와 등기부등본 주소 검증
- **시세 대비 보증금 위험**: 실거래가 API 기반 시세 비교
- **담보 여유 초과 여부**: 근저당권과 보증금 비율 분석

### **특약사항 분석**
- 계약서 특약사항 자동 추출
- 위험도별 분류 (위험/주의/안전)
- 종합 의견 및 권고사항 제공

### **사용자 관리**
- 카카오 로그인 연동
- 분석 기록 저장 및 조회
- Firebase Firestore 기반 데이터 관리

## 기술 스택

<div align="center">

### **Backend & AI**
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3.3-000000?style=for-the-badge&logo=flask&logoColor=white)
![EasyOCR](https://img.shields.io/badge/EasyOCR-1.7.1-FF6B35?style=for-the-badge&logo=pytorch&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Gemini-1.5%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Admin%20SDK-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)
![OpenCV](https://img.shields.io/badge/OpenCV-4.9.0-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)

### **Frontend & UI**
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-3.0-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)

### **External APIs**
![Kakao](https://img.shields.io/badge/Kakao%20Login-FFCD00?style=for-the-badge&logo=kakao&logoColor=black)
![Public Data](https://img.shields.io/badge/Public%20Data%20API-00D4AA?style=for-the-badge&logo=government&logoColor=white)

</div>

| **Category** | **Technology** | **Purpose** |
|:---:|:---|:---|
| **Backend** | Flask, Python | 웹 서버 및 API 개발 |
| **AI/ML** | EasyOCR, Gemini AI | 문서 인식 및 텍스트 분석 |
| **Database** | Firebase Firestore | 사용자 데이터 및 분석 결과 저장 |
| **Frontend** | HTML5, CSS3, JavaScript | 반응형 웹 인터페이스 |
| **Styling** | Tailwind CSS | 모던 UI 디자인 |
| **Auth** | Firebase Auth, Kakao Login | 사용자 인증 |
| **External** | 실거래가 API, 공공주소 API | 부동산 시세 및 주소 검증 |

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

## 배포 가이드

- 본 프로젝트는 로컬 개발 환경뿐 아니라, 클라우드 서버(예: AWS EC2, GCP, Azure VM 등) 또는 Docker 환경에서 운영할 수 있습니다.
- 운영 환경에서는 반드시 환경 변수와 Firebase, Google Gemini, 공공데이터 API 키 등을 안전하게 관리하세요.

### Docker로 배포하기

```bash
# 빌드
docker build -t safesign-app .

# 실행
docker run -d -p 5000:5000 --env-file .env -v $(pwd)/firebase-credentials.json:/app/firebase-credentials.json safesign-app
```

### 클라우드 서버 배포 팁
- Python 3.10+ 및 requirements.txt 설치
- .env, firebase-credentials.json 등 민감 정보는 서버에 직접 업로드
- 방화벽에서 5000 포트 오픈
- Gunicorn, Nginx 등과 연동해 운영 가능

---

### 📋 **사전 요구사항**
- Python 3.10 이상
- Git
- API 키들 (아래 환경 변수 섹션 참조)

###  **환경 설정**
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

###  **환경 변수 설정**
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

###  **Firebase 설정**
-  [Firebase 프로젝트 생성](https://console.firebase.google.com/)
-  서비스 계정 키 파일을 `firebase-credentials.json`으로 저장
-  Firebase 설정을 `static/main.js`에 추가

###  **애플리케이션 실행**
```bash
python app.py
```

서버가 `http://localhost:5000`에서 실행됩니다.

##  사용 방법

<div align="center">

![Workflow](https://img.shields.io/badge/Workflow-5단계-00D4AA?style=for-the-badge)

</div>

###  **1단계: 로그인**
-  카카오 계정으로 로그인 및 회원가입
-  서비스 이용을 위한 필수 인증

###  **2단계: 문서 업로드**
-  등기부등본 이미지 업로드
-  임대차 계약서 이미지 업로드
-  드래그 앤 드롭 또는 파일 선택

###  **3단계: 텍스트 추출**
-  "AI로 텍스트 추출 및 보정" 버튼 클릭
-  OCR 처리 및 AI 보정 진행
-  추출된 텍스트 검토 및 수정 가능

###  **4단계: 종합 분석**
-  "종합 분석 실행" 버튼 클릭
-  실시간 진행 상황 확인
-  위험도 분석 결과 확인

###  **5단계: 결과 확인**
-  핵심 정보 검증 결과
-  특약사항 분석
-  종합 위험도 등급
-  권고사항 및 주의사항

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

| 최정훈 | 안효서 | 박지연 | 이서준 | 이재진 |
|--------|--------|--------|--------|--------|
| [![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Jeonghoonchoi74) | [![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/pokqok) | [![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/jiyeon22) | [![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/seojun133) | [![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/LeeJaeJin00) |

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.


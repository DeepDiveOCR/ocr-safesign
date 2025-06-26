# 1. 베이스 이미지 선택: 가벼운 파이썬 3.11 버전을 사용합니다.
# 이 이미지는 운영체제와 파이썬이 미리 설치된 깨끗한 컴퓨터와 같습니다.
FROM python:3.11-slim

# 2. 시스템 패키지 업데이트 및 필수 라이브러리 설치
#    - apt-get update: 패키지 목록을 최신으로 업데이트합니다.
#    - libgl1-mesa-glx: OpenCV가 GUI 없는 환경에서 이미지를 처리할 때 필요한 라이브러리입니다.
#    - --no-install-recommends: 불필요한 추천 패키지는 설치하지 않아 이미지 용량을 줄입니다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 3. 환경 변수 설정
#    파이썬이 버퍼링 없이 로그를 바로 출력하도록 하여, Firebase App Hosting 로그에서 실시간으로 상황을 볼 수 있게 합니다.
ENV PYTHONUNBUFFERED True

# 4. 작업 디렉토리 설정
#    컨테이너(가상 컴퓨터) 내부에 /app 이라는 폴더를 만들고, 앞으로의 모든 작업은 이 폴더 안에서 이루어지도록 설정합니다.
WORKDIR /app

# 5. 의존성 파일 복사 및 설치
#    먼저 requirements.txt만 복사하여 라이브러리를 설치하면, 코드 변경 시 빌드 캐시를 활용해 속도가 빨라집니다.
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 6. 소스 코드 복사
#    프로젝트의 모든 파일을 컨테이너의 /app 폴더로 복사합니다.
COPY . .

# 7. 실행 명령어
#    gunicorn을 사용해 안정적인 운영 환경에서 Flask 앱을 실행합니다.
#    - --bind :$PORT: App Hosting이 동적으로 할당해주는 포트 번호($PORT)로 서버를 실행합니다.
#    - --workers 1 --threads 8: 1개의 프로세스로 8개의 요청을 동시에 처리하도록 설정하여 효율을 높입니다.
#    - --timeout 0: 작업 시간이 길어질 수 있는 OCR 및 AI 분석 중 연결이 끊기지 않도록 타임아웃을 무제한으로 설정합니다.
#    - app:app: app.py 파일 안에 있는 app 객체를 실행하라는 의미입니다.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app

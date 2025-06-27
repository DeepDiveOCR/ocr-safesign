# 1. 베이스 이미지 선택: 가벼운 파이썬 3.11 버전을 사용합니다.
FROM python:3.11-slim

# 2. 시스템 패키지 업데이트 및 필수 라이브러리 설치 (OpenCV 등)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 3. 환경 변수 설정: 최신 권장 형식(KEY=VALUE)으로 수정합니다.
ENV PYTHONUNBUFFERED=True

# 4. 작업 디렉토리 설정
WORKDIR /app

# 5. 의존성 파일 복사 및 설치
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 6. 소스 코드 복사
COPY . .

# 7. 실행 명령어: 안정적인 운영을 위해 JSON 배열 형식으로 수정합니다.
#    - "0.0.0.0"은 컨테이너 외부의 모든 트래픽을 허용하는 표준 설정입니다.
ENTRYPOINT ["sh", "-c"]
CMD ["gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 app:app"]


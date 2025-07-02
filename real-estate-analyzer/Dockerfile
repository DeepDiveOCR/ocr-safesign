# 1. Python 3.11 기반의 경량 이미지 사용
FROM python:3.11-slim

# 2. 시스템 라이브러리 설치 (OpenCV 실행에 필요)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 3. 환경 변수 설정
ENV PYTHONUNBUFFERED=True

# 4. 작업 디렉토리 설정
WORKDIR /app

# 5. requirements 복사 및 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 소스 코드 전체 복사 (.EasyOCR 포함)
COPY . .

# 7. Gunicorn을 통한 앱 실행
ENTRYPOINT ["sh", "-c"]
CMD ["gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 0 app:app"]

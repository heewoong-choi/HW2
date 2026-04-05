FROM python:3.10-slim

# 1. 시스템 계정 및 디렉토리 설정 (보안 강화: Non-root User 실행)
# 프로젝트 기본 디렉토리를 소유할 appuser를 생성합니다.
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 2. 필수 OS 패키지 최적화 설치 (--no-install-recommends 및 apt-get clean 추가)
# 이미지 크기를 최소한으로 억제합니다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. 파이썬 및 앱 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEEPFACE_HOME=/app/weights

# 4. 파이썬 패키지 먼저 설치 (캐시 활용 극대화)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. 앱 파일 복사 및 가중치용 캐시 폴더 생성 후, 소유권 이전
COPY main.py .
RUN mkdir -p /app/weights && chown -R appuser:appuser /app

# 6. 사용자 전환 (루트 권한 포기 -> 해킹 컨테이너 탈취 공격 방지)
USER appuser

EXPOSE 8000

# 7. 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

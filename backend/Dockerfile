FROM python:3.12-slim

WORKDIR /app

# LSC 동기화(SSH 원격 실행)용 ssh 클라이언트
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# Includes pinned demo-chat HTTP client and Langfuse SDK for offline delivery.
RUN pip install --no-cache-dir -r requirements.txt

# Startup creates only the initial administrator; additional users use the admin API.
COPY app ./app
COPY .env.example ./.env.example
# Keep the runtime directory without packaging local development databases.
RUN mkdir -p ./data

# EXPOSE documents the default; app.serve reads BACKEND_PORT at runtime.
ENV BACKEND_PORT=18000
EXPOSE 18000
CMD ["python", "-m", "app.serve"]

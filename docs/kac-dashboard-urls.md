# 한국공항공사 대시보드와 백엔드 포트 설정

시연 채팅은 [회사·KAC 공통 안내](demo-chat.md)를 따릅니다. 현재는 회사 실제 연결 검증을 우선하며
KAC IP·프록시 적용과 최종 반입은 [향후 패키징 체크리스트](kac-packaging-checklist.md)로 남깁니다.
아래는 기존 KAC 전환 절차와 검증 기록이며 회사의 실행 중인 Nginx를 변경하라는 지시가 아닙니다.
기존 Grafana URL·80번 웹 경로·DB 설정을 보존하고 KAC의 실제 실행 구성을 적용 전에 다시 확인합니다.

한국공항공사 구성(`MONITORING_SCOPE=kac`)은 다음 여섯 관제 화면을 제공합니다.
2026-10-16 Observability·Time Trace·User Trace의 메뉴와 직접 경로를 복구했습니다.
이 복구는 기존 URL·키·Nginx 설정을 변경하지 않으며, 시연 채팅은 `DEMO_CHAT_ENABLED`로 별도 제어합니다.

| 메뉴 | 설정 | 동작 |
|---|---|---|
| LLM → Dashboard | `VLLM_URL` | 단일 Grafana 화면 |
| LLM → Observability | `VLLM_OBSERVABILITY_URL` | 기존 iframe 화면 |
| LLM → Time Trace | `TRACE_URL` | 기존 iframe 화면 |
| LLM → User Trace | `USER_TRACE_URL` | 기존 iframe 화면 |
| GPU | `GPU_URL` | 단일 Grafana 화면 |
| Server | `NODE_URL` | 단일 Grafana 화면 |

LLM Dashboard/GPU/Server에서는 Insight의 서비스별 탭이나 더보기를 표시하지 않습니다. 세부 선택은 Grafana에서 처리합니다.
주소가 비어 있으면 주소 미설정 안내를 표시합니다. 이전 `server`, `target` 쿼리는 화면 선택에 영향을 주지 않고,
Grafana URL에도 전달하지 않습니다. 각 화면은 iframe 하나만 로드합니다.

## 어디를 수정하나

| 파일 | 설정/용도 |
|---|---|
| `deploy/.env` | `BACKEND_PORT`: 서버 포트와 컨테이너 실행 포트를 함께 지정 |
| `deploy/.env.backend` | Grafana URL과 기존 DB/인증 설정 |
| 서버의 Nginx 설정 | `/api/` 연결 대상 포트를 `BACKEND_PORT`와 맞춤 |
| `backend/.env` | Docker 없이 로컬 실행할 때 URL·DB·포트 설정 |

`.env` 파일들은 숨김파일이므로 서버에 반입할 때 빠뜨리지 않습니다.
DB/인증 설정이 들어 있는 `.env.backend` 전체를 예제로 덮어쓰지 않습니다.

## 백엔드 포트

`deploy/.env`:

```dotenv
# 같은 서버의 vLLM 등 다른 프로그램이 쓰지 않는 포트
BACKEND_PORT=18000
```

Compose가 이 값을 포트 매핑과 컨테이너 환경변수에 동시에 반영합니다.
이미지의 `python -m app.serve` 실행 명령이 환경변수를 읽어 같은 포트에서 서버를 시작합니다.

```text
Nginx → 127.0.0.1:18000 → 컨테이너의 18000
```

`18081`로 바꾸면 양쪽 모두 `18081`이 됩니다. 기본값은 `18000`이며 1~65535 범위의 정수만 허용합니다.
`EXPOSE 18000`은 이미지의 기본 포트 설명이며 실제 실행 포트는 `BACKEND_PORT`로 결정됩니다.
Compose 배포에서는 `.env.backend`에 포트 설정을 중복해서 넣지 않습니다.

이 구성은 같은 서버의 Nginx가 백엔드에 연결하는 방식이며, 서버 포트는 `127.0.0.1`에 바인딩합니다.
Nginx를 다른 서버나 다른 컨테이너로 옮기는 경우에는 연결 주소와 네트워크 구성을 별도로 맞춥니다.

## Nginx도 같은 포트로 수정

호스트에 설치된 Nginx의 기존 `server { ... }` 안에 있는 `/api/` 연결 대상을 맞춥니다.
[복사용 location 예제](kac-nginx-api.conf.example)를 참고하세요.

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:18000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

`proxy_pass` 끝에 `/`를 추가하지 않습니다. `/api/...` 경로를 유지해야 합니다.
Nginx는 `deploy/.env`를 자동으로 읽지 않으므로 포트 변경 시 이 부분도 직접 맞춥니다.
기존 정적 파일 경로, `try_files`, 도메인과 TLS 설정은 유지합니다.
설정 경로는 현장 Nginx 구성에 따라 다르며 운영 파일은 이 저장소에서 직접 수정하지 않습니다.

프론트는 상대 경로 `/api`를 사용합니다(`VITE_API_BASE_URL` 비움).
배포 후 포트만 바뀌어도 프론트 파일을 다시 빌드하지 않아도 됩니다.

## Grafana URL

`deploy/.env.backend`의 한국공항공사 주석 아래에서 다음 세 값을 수정합니다.
아래 주소는 예시이며 현장에서 접속 가능한 실제 전체 URL로 교체합니다.

```dotenv
MONITORING_SCOPE=kac
GPU_URL='https://grafana.example.test/d/gpu?orgId=1&kiosk=true'
NODE_URL='https://grafana.example.test/d/server?orgId=1&kiosk=true'
VLLM_URL='https://grafana.example.test/d/llm?orgId=1&kiosk=true'
```

[주석 포함 env 예제](kac-dashboard-urls.env.example)도 함께 제공합니다.
`VLLM_URL`의 이전 `[{"id":...,"name":...,"url":...}]` 목록은 URL 문자열 하나로 바꿔야 합니다.
`[]`도 더 이상 사용하지 않으며, 아직 URL이 없으면 `VLLM_URL=`로 비워 둡니다.
여러 서비스 URL 중 첫 주소를 자동으로 고르지 않습니다. 사용할 Grafana 대시보드 주소를 직접 지정합니다.

세 키 모두 빈 값 또는 HTTP(S) 절대 URL만 허용합니다. JSON 목록, 중복 키, URL 내 사용자명/비밀번호는 허용하지 않습니다.
비밀 토큰도 URL에 넣지 않습니다. Prometheus 주소는 Grafana 데이터 소스에 설정하며 여기에는 Grafana 화면 주소를 넣습니다.

Observability·Time Trace·User Trace는 기존 `VLLM_OBSERVABILITY_URL`, `TRACE_URL`, `USER_TRACE_URL` 값을 그대로 사용합니다.
메뉴 복구를 위해 이 값을 바꾸거나 Langfuse SDK 수집 주소로 대체하지 않습니다. URL이 비어 있으면 해당 화면에서 주소 미설정 안내를 표시합니다.
복구된 직접 경로는 `/ops/vllm-observability`, `/ops/trace`, `/ops/user-trace`이며,
인증된 `/api/v1/config/frontend` 응답에 세 기능의 기존 URL이 포함되는지 확인합니다.

## 최신 백엔드와 빌드된 프론트 반영

적용 대상은 사용자가 이미 빌드한 프론트 `dist`와 최신 백엔드 이미지 `tslurm-backend:2026-10-16-demo-users`입니다.
백엔드는 Ubuntu 24.04 x86_64 호스트의 Docker용 `linux/amd64` 이미지이며 컨테이너 기반 이미지는 기존 `python:3.12-slim`을 유지합니다.
이번 백엔드 재빌드에서는 프론트를 다시 빌드하지 않습니다. 기존 Compose의 backend 이미지 태그를 확인하고,
`deploy/.env`, `.env.backend`, DB 데이터/볼륨과 Nginx 설정은 보존합니다.
아래는 적용 절차이며 현재 작업에서 실제 서버 배포를 수행하지 않았습니다. 전체 KAC 폐쇄망 패키징은 별도 후속 작업입니다.

Ubuntu 24.04 x86_64 서버의 `deploy` 폴더에서:

```bash
sha256sum -c tslurm-backend-2026-10-16-demo-users-linux-amd64.tar.sha256
docker load -i tslurm-backend-2026-10-16-demo-users-linux-amd64.tar
docker compose config --quiet
docker compose up -d --no-deps --no-build --pull never --force-recreate backend
```

이미 실행 중인 DB를 사용하는 백엔드 교체 명령입니다. DB가 아직 없으면 기존 설치 절차로 먼저 준비합니다.
사용자가 빌드한 프론트 `dist`의 내용을 기존 Nginx 정적 파일 경로에 적용합니다.
기존 backend 연결 주소와 포트를 유지하며 이번 이미지 교체를 위해 Nginx 프록시를 변경하지 않습니다.

`BACKEND_PORT=18000` 기준 확인:

```bash
curl -fsS http://127.0.0.1:18000/api/v1/health
```

로그인과 LLM/GPU/Server 화면을 브라우저에서 확인합니다.
실제 Grafana 연결, iframe 로그인/표시 허용, 서버·GPU·LLM 선택은 현장 설정으로 검증합니다.

## 이후 URL 또는 포트만 바꿀 때

새 버전 최초 배포 이후에는 이미지와 프론트를 다시 빌드하지 않습니다.

1. URL은 `.env.backend`, 포트는 `deploy/.env`에서 변경합니다.
2. `docker compose up -d --no-deps --no-build --pull never --force-recreate backend`로 재생성합니다.
3. 포트를 바꿨다면 Nginx 연결 대상도 수정하고 `nginx -t` 성공 후 reload합니다.
4. 브라우저를 새로고침합니다.

`docker compose restart`만으로는 변경된 env_file/포트 매핑이 반영되지 않습니다.

## 로컬 개발과 기존 납품 구성

Docker 없이 개발할 때 `backend/.env`에 `BACKEND_PORT=18000`을 넣고 `backend`에서 `python -m app.serve`로 실행합니다.
프론트 개발 프록시는 `deploy/.env`의 포트를 읽으므로 로컬 백엔드와 같은 값으로 맞춥니다.
`frontend`에서 `npm run dev`를 사용합니다. 이 포트 값은 브라우저 번들에 노출되지 않습니다.

기존 EICN(`profile`)과 1대용 도구(`gpu_llm`)의 메뉴/대시보드 목록 형식은 유지합니다.
`delivery/offline`의 별도 Dockerfile·Nginx·healthcheck는 기존 도구 전용으로 유지하며 KAC 배포에는 사용하지 않습니다.
KAC에서 복구한 Observability·Time Trace·User Trace 외의 비활성 기능에 대한 메뉴/직접 URL/API 접근 차단은 유지합니다.
관리자 로그인과 더미 데이터 제거 상태도 유지합니다.

## 검증 명령

```bash
cd frontend
npm run lint
npm run build
node --test tests/*.test.mjs
```

```bash
cd backend
.venv/bin/python -m compileall -q app
.venv/bin/python -m unittest discover -s tests -v
```

### 2026-10-12 로컬 검증 결과

- 프론트 lint/build 및 테스트 11개 통과. 기존 effect 경고 5개와 번들 크기 경고는 유지됩니다.
- 백엔드 compileall 및 unittest 25개 통과. pytest는 로컬 가상환경에 설치되어 있지 않습니다.
- Compose 포트 매핑과 실행 환경, Vite 개발 프록시가 18000/18081 설정에 맞춰 바뀌는 것을 확인했습니다.
- amd64 이미지의 실제 서버를 격리된 임시 SQLite DB로 실행해 두 포트에서 health·로그인·인증된 설정 API를 확인했습니다.
  이전 8000 포트가 열리지 않는 것도 확인했습니다. 현장 MariaDB/Nginx/Grafana 연결 검증은 별도입니다.
- 새 tar의 linux/amd64 아키텍처, app.serve 실행 명령, 운영 env/로컬 DB 제외, Docker load 성공을 확인했습니다.
- Compose의 기존 `__all` 보간 경고는 유지됩니다. 실제 운영 컨테이너와 Nginx는 변경하지 않았습니다.

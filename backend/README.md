# TSlurmOps FastAPI Backend Scaffold

이 폴더는 현재 React + Vite 프론트(`tslurm_ops`)에 붙일 수 있는 FastAPI 백엔드 시작점입니다.

## 포함 기능

- JWT 로그인 (`/api/v1/auth/login`)
- Swagger 인증용 토큰 발급 엔드포인트 (`/api/v1/auth/token`)
- 로그인 사용자 조회 (`/api/v1/auth/me`)
- 관리자 전용 사용자 조회/생성 (`/api/v1/users`)
- MariaDB 기반 이중 DB 분리 (`insight_admin` / `desk_users`)
- 프론트 설정값 조회 (`/api/v1/config/frontend`)
- 헬스체크 (`/api/v1/health`)
- WebSocket 터미널 스텁 (`/api/v1/ws/term/{target}`)
- TD 자원예약 신청 수신 (`/api/external/td/resource-reservation-requests`)

> 현재 터미널은 **실제 shell/SSH 연결이 아니라 데모 스텁**입니다.
> 프론트 xterm 연결 검증용으로만 사용하고, 실제 운영용 셸 연결은 별도 하드닝이 필요합니다.

## 폴더 구조

```text
.
├─ app/
│  ├─ api/
│  │  ├─ router.py
│  │  └─ v1/endpoints/
│  ├─ core/
│  ├─ db/
│  ├─ dependencies/
│  ├─ models/
│  ├─ schemas/
│  └─ services/
├─ .env.example
├─ requirements.txt
└─ Dockerfile
```

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env       # Windows: copy .env.example .env
uvicorn app.main:app --reload
```

실행 전에 MariaDB에 아래 두 database(schema)를 먼저 준비해야 합니다.

```sql
CREATE DATABASE insight_admin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE desk_users CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

`admins` 테이블은 `insight_admin`에, `users` 테이블은 `desk_users`에 각각 생성됩니다.
TD 자원예약 신청은 `insight_admin`의 `resource_reservation_requests` 테이블에 저장됩니다.

서버가 뜨면 아래를 확인하면 됩니다.

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`

## 기본 관리자 계정

`.env`를 따로 수정하지 않으면 첫 실행 시 아래 계정이 자동 생성됩니다.

- ID: `admin`
- PW: `.env`의 `INITIAL_ADMIN_PASSWORD` 값

운영 환경에서는 반드시 변경하세요.

## MariaDB 환경 변수

`.env.example` 기준으로 아래 두 연결 문자열을 각각 설정합니다.

- `ADMIN_DATABASE_URL=mysql+pymysql://insight_admin_user:password@127.0.0.1:3306/insight_admin?charset=utf8mb4`
- `USER_DATABASE_URL=mysql+pymysql://desk_user_user:password@127.0.0.1:3306/desk_users?charset=utf8mb4`
- `TD_API_KEY=change-me-td-api-key`
- `SLURM_RESERVATION_MOCK=true`
- `SLURM_REST_BASE_URL=http://slurmrestd:6820`
- `SLURM_REST_API_VERSION=v0.0.44`
- `SLURM_REST_USER_NAME=<slurm-user>`
- `SLURM_REST_USER_TOKEN=<slurm-token>`

`/api/v1/auth/login`, `/api/v1/auth/token`, `/api/v1/auth/me` 는 admin DB만 사용합니다.
`/api/v1/auth/register`, `/api/v1/users` 는 user DB만 사용합니다.

## TD 자원예약 신청 수신

TD는 `X-TD-API-KEY` 헤더를 포함해 아래 엔드포인트로 자원예약 신청 JSON을 보냅니다.
업무 필드 검증에 실패해도 원본 요청과 검증 메시지는 DB에 저장되며, Slurm 호출/승인/거절/메일 발송은 이 엔드포인트에서 수행하지 않습니다.

```bash
curl -X POST "http://127.0.0.1:8000/api/external/td/resource-reservation-requests" \
  -H "Content-Type: application/json" \
  -H "X-TD-API-KEY: change-me-td-api-key" \
  -d '{
    "sourceSystem": "TD",
    "externalTicketId": "td-428",
    "idempotencyKey": "td-resource-reservation-td-428",
    "requesterUsername": "user1",
    "notificationEmail": "user1@example.com",
    "title": "GPU 테스트 예약",
    "partitionLabel": "GPU 가속 (GPU - Node 권장)",
    "requestedCpuCores": "",
    "requestedMemoryGb": "",
    "requestedGpuNodes": "2",
    "detail": "GPU 예약 테스트입니다.",
    "schedule": {
      "year": "2026",
      "month": "5",
      "day": "15",
      "hour": "10",
      "minute": "0",
      "durationText": "8h"
    },
    "rawPayload": {}
  }'
```

## 관리자 자원예약 요청 목록 조회

관리자 화면의 `자원 예약 승인/거절` 탭은 아래 API로 TI DB에 저장된 예약 요청을 조회하고 처리합니다.

```bash
curl "http://127.0.0.1:8000/api/admin/resource/reservation-requests" \
  -H "Authorization: Bearer <admin-token>"
```

승인과 재시도는 승인 시점에 Slurm payload를 생성/저장한 뒤 Slurm REST API를 호출합니다.
`SLURM_RESERVATION_MOCK=true`이면 실제 Slurm 호출 없이 mock 성공 응답으로 `SLURM_RESERVED` 처리됩니다.
거절은 Slurm payload를 생성하지 않고 DB row도 삭제하지 않으며 `REJECTED` 상태로 남깁니다.

```bash
curl -X POST "http://127.0.0.1:8000/api/admin/resource/reservation-requests/1/approve" \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"adminMemo":"요청 내용 확인 후 승인"}'

curl -X POST "http://127.0.0.1:8000/api/admin/resource/reservation-requests/1/reject" \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"rejectionReason":"요청 시간이 부적절합니다."}'

curl -X POST "http://127.0.0.1:8000/api/admin/resource/reservation-requests/1/retry-slurm" \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"adminMemo":"Slurm 오류 확인 후 재시도"}'
```

프론트 개발 중 더미 JSON을 사용하려면 `frontend/.env`에 `VITE_USE_DUMMY_RESERVATION_REQUESTS=true`를 설정합니다.

## 프론트 연동 포인트

### 1) 로그인

현재 프론트 `src/pages/Login.tsx` 에서는 더미 로그인만 하고 있으므로, 이후 아래 API로 교체하면 됩니다.

- `POST /api/v1/auth/login`
- 요청 예시:

```json
{
  "username": "admin",
  "password": "admin"
}
```

### 2) 로그인 사용자 조회

- `GET /api/v1/auth/me`
- 헤더: `Authorization: Bearer <token>`

### 3) 대시보드/터미널 설정 조회

- `GET /api/v1/config/frontend`

현재 프론트의 `.env`에 들어있는 Grafana URL을 백엔드가 대신 내려주도록 설계했습니다.

### 4) WebSocket 터미널

- `ws://127.0.0.1:8000/api/v1/ws/term/master?token=<JWT>`

지원 명령어:
- `help`
- `whoami`
- `target`
- `date`
- `clear`
- `exit`

## 권장 다음 단계

1. 프론트 `Login.tsx` 를 `/api/v1/auth/login` 호출로 교체
2. `PrivateRoute.tsx` 를 `/api/v1/auth/me` 기반 검증으로 교체
3. 프론트 `.env` 의 Grafana URL을 백엔드 `/api/v1/config/frontend` 소비 방식으로 전환
4. 실제 운영용 터미널이 필요하면 SSH/PTY 브리지 구조를 별도 설계
5. 운영 스키마 변경이 잦아지면 `create_all()` 대신 Alembic 마이그레이션 도입

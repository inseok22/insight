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
- 환경변수로 활성화하는 공통 시연 채팅 (`/api/v1/chat/*`), vLLM 스트리밍과 Langfuse 계측

회사·한국공항공사 채팅은 같은 코드와 이미지를 사용하며 연결 정보는 각 환경의 `.env.backend`에서 지정합니다.
[공통 채팅 설정 및 회사 실연동 확인](../docs/demo-chat.md)을 참고하세요.
공항공사 전용 `/grafana/`·`/langfuse/` 프록시와 Compose 마운트 검증은
[최종 반입 전 체크리스트](../docs/kac-packaging-checklist.md)로 분리하며 회사 운영 설정에 적용하지 않습니다.

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
python -m app.serve        # backend/.env의 BACKEND_PORT 사용 (기본 18000)
```

실행 전에 MariaDB에 아래 두 database(schema)를 먼저 준비해야 합니다.

```sql
CREATE DATABASE insight_admin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE desk_users CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

`admins` 테이블은 `insight_admin`에, `users` 테이블은 `desk_users`에 각각 생성됩니다.
TD 자원예약 신청은 `insight_admin`의 `resource_reservation_requests` 테이블에 저장됩니다.

서버가 뜨면 아래를 확인하면 됩니다.

- Swagger UI: `http://127.0.0.1:18000/docs`
- Health: `http://127.0.0.1:18000/api/v1/health`

로컬 포트는 `backend/.env`의 `BACKEND_PORT`에서 바꿉니다. 개발 프록시를 사용하는 경우
`deploy/.env`의 `BACKEND_PORT`도 같은 값으로 맞춥니다. Compose 배포에서는 `deploy/.env` 한 곳의 값이
컨테이너 실행 포트와 서버 포트 매핑 모두에 적용됩니다. Nginx의 `/api` 연결 포트도 맞춰야 합니다.
[한국공항공사 배포 설정](../docs/kac-dashboard-urls.md)을 참고하세요.

## 기본 관리자 계정

`.env`를 따로 수정하지 않으면 첫 실행 시 아래 계정이 자동 생성됩니다.

- ID: `admin`
- PW: `admin` (제공 환경파일은 `INITIAL_ADMIN_PASSWORD_HASH`에 해시로 설정)

운영 환경에서는 반드시 변경하세요.

Insight 관리자의 신규 비밀번호는 PBKDF2-HMAC-SHA256으로 저장합니다. 반복 횟수는 600,000회이며 비밀번호마다 무작위 salt를 생성합니다.
[OWASP 비밀번호 저장 권고](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#pbkdf2)의 PBKDF2-HMAC-SHA256 작업량을 적용합니다.
저장 형식은 `pbkdf2_sha256$600000$<32자리 hex salt>$<32바이트 digest의 표준 Base64>`입니다. salt는 hex 문자열 자체를 UTF-8로 인코딩해 사용합니다.

폐쇄망 초기 관리자 설정 `INITIAL_ADMIN_PASSWORD_HASH`는 새 형식과 기존 `{SSHA}`를 허용합니다.
환경파일에 직접 입력할 때는 `INITIAL_ADMIN_PASSWORD_HASH='<생성한 전체 해시>'`처럼 작은따옴표로 감싸 `$` 문자가 Compose 변수로 치환되지 않게 합니다. 설치 도구는 이를 자동 처리합니다.
기존 SSHA/Argon2 관리자 계정은 정상 비밀번호로 활성 계정 로그인이 성공할 때 새 형식으로 갱신하며 사용자 ID와 비밀번호는 유지합니다.
이전 해시만으로 전체 계정을 변환할 수 없으므로 로그인 또는 비밀번호 재설정이 필요합니다. 기존 관리자 레코드를 환경변수 변경으로 덮어쓰지는 않습니다.
이전 백엔드로 롤백하면 새 형식의 계정을 검증하지 못할 수 있으므로 데이터와 코드의 호환성을 함께 확인해야 합니다.
이 변경은 Insight 관리자 계정에 한정하며 Desk/LDAP 비밀번호와 MariaDB 접속 계정의 인증 방식은 유지합니다.

### URL로 사용자 추가

로그인한 상태에서 `/ops/admin-users/new`에 직접 접속합니다. 사이드바·사용자 메뉴에는 링크가 없습니다.
아이디(영문·숫자로 시작, `._-` 허용, 1~50자), 이름(선택, 100자 이내), 비밀번호(8~128자), 비밀번호 확인을 입력하면 바로 로그인 가능한 계정이 생성됩니다.
`POST /api/v1/admin/users`는 활성 관리자 인증을 요구하고 `insight_admin.admins`에 비밀번호 해시만 저장합니다. 중복 아이디는 409로 응답하며 기존 계정을 덮어쓰지 않습니다.
현재 모든 로그인 계정은 동일한 관리자 권한이므로, 새 계정도 이 URL과 API를 사용할 수 있습니다. Desk 가입신청과는 별개이며 공개 가입신청은 계속 비활성입니다.
상단 사용자 메뉴는 로그인 응답의 `user.username`을 표시합니다. 로그아웃·인증 만료 시 저장된 로그인 정보를 정리합니다.

### 초기 계정만 생성

2026-10-17부터 서버 시작 시 초기 관리자 `admin/admin`만 생성합니다. `user1`, `user2` 자동 생성 호출은 제거했습니다.
이전 환경파일의 `SEED_DEMO_ACCOUNTS=true`도 시작 시 데모 계정을 생성하지 않습니다. 제공 환경파일은 `false`입니다.
초기 비밀번호는 제공 환경파일에 PBKDF2-HMAC-SHA256 해시로 설정합니다. 추가 계정은 `/ops/admin-users/new`에서 생성합니다.
이미 DB에 있는 계정은 삭제하지 않으며 기존 `admin`의 비밀번호도 초기 설정으로 덮어쓰지 않습니다.
시연 채팅 메뉴/API 활성화는 `DEMO_CHAT_ENABLED`로 별도 제어합니다.

## MariaDB 환경 변수

`.env.example` 기준으로 아래 두 연결 문자열을 각각 설정합니다.

- `ADMIN_DATABASE_URL=mysql+pymysql://insight_admin_user:password@127.0.0.1:3306/insight_admin?charset=utf8mb4`
- `USER_DATABASE_URL=mysql+pymysql://desk_user_user:password@127.0.0.1:3306/desk_users?charset=utf8mb4`
- `TD_API_KEY=change-me-td-api-key`
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
curl -X POST "http://127.0.0.1:18000/api/external/td/resource-reservation-requests" \
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
curl "http://127.0.0.1:18000/api/admin/resource/reservation-requests" \
  -H "Authorization: Bearer <admin-token>"
```

승인과 재시도는 승인 시점에 Slurm payload를 생성/저장한 뒤 Slurm REST API를 호출합니다.
Slurm 예약은 실제 REST API로만 처리합니다. 연결 계정/토큰이 없으면 연동 미설정 오류를 반환합니다.
거절은 Slurm payload를 생성하지 않고 DB row도 삭제하지 않으며 `REJECTED` 상태로 남깁니다.

```bash
curl -X POST "http://127.0.0.1:18000/api/admin/resource/reservation-requests/1/approve" \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"adminMemo":"요청 내용 확인 후 승인"}'

curl -X POST "http://127.0.0.1:18000/api/admin/resource/reservation-requests/1/reject" \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"rejectionReason":"요청 시간이 부적절합니다."}'

curl -X POST "http://127.0.0.1:18000/api/admin/resource/reservation-requests/1/retry-slurm" \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"adminMemo":"Slurm 오류 확인 후 재시도"}'
```

예약 화면은 인증된 백엔드 API만 사용합니다. 한국공항공사 구성에서는 예약 메뉴와 API를 비활성화합니다.

## 프론트 연동 포인트

### 1) 로그인

현재 프론트 `src/pages/Login.tsx`는 아래 인증 API를 호출하여 로그인합니다.

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

- `ws://127.0.0.1:18000/api/v1/ws/term/master?token=<JWT>`

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

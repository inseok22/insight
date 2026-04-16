# TSlurmOps FastAPI Backend Scaffold

이 폴더는 현재 React + Vite 프론트(`tslurm_ops`)에 붙일 수 있는 FastAPI 백엔드 시작점입니다.

## 포함 기능

- JWT 로그인 (`/api/v1/auth/login`)
- Swagger 인증용 토큰 발급 엔드포인트 (`/api/v1/auth/token`)
- 로그인 사용자 조회 (`/api/v1/auth/me`)
- 관리자 전용 사용자 조회/생성 (`/api/v1/users`)
- 프론트 설정값 조회 (`/api/v1/config/frontend`)
- 헬스체크 (`/api/v1/health`)
- WebSocket 터미널 스텁 (`/api/v1/ws/term/{target}`)

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
├─ data/
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

서버가 뜨면 아래를 확인하면 됩니다.

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`

## 기본 관리자 계정

`.env`를 따로 수정하지 않으면 첫 실행 시 아래 계정이 자동 생성됩니다.

- ID: `admin`
- PW: `admin`

운영 환경에서는 반드시 변경하세요.

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
5. DB가 커지면 `create_all()` 대신 Alembic 마이그레이션 도입

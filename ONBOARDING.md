# ONBOARDING — TSlurm Insight 관제 콘솔

> 신규 합류자(개발 팀장 포함)를 위한 온보딩 가이드입니다.
> 프로젝트 "해설"은 [README.md](README.md), 작업 규칙·납품 전략은 [AGENTS.md](AGENTS.md)에 있습니다.
> 이 문서는 **"어디서부터 손대고, 무엇을 조심해야 하는가"** 에 집중합니다.

---

## 1. 한눈에 보기

**TSlurm 클러스터를 운영하는 관리자용 웹 콘솔**입니다. 핵심은 세 가지입니다.

1. **관제 화면 통합** — Grafana 등 외부 모니터링 페이지를 `VITE_*_URL` 기반 iframe으로 한 화면에 모음 (Dashboard / Node / Job / GPU / Power / K8s / SNMP)
2. **회원가입 신청 승인** — 일반 사용자가 `/register`로 신청 → 관리자가 승인/거절
3. **자원예약 승인** — 외부 TD(TSlurmDesk) 시스템이 예약을 보내옴 → 관리자가 승인하면 Slurm에 예약 생성

사용자는 두 갈래입니다.

| 사용자 | 흐름 |
|---|---|
| 일반 신청자 | `/register`에서 가입 신청 → `desk_users.users`에 `pending` 저장 (Insight에 로그인하지 않음) |
| 관리자 | `/login` → `/ops/*`에서 관제 화면 조회 + 가입/자원예약 승인 |

### 아키텍처

```
[브라우저]
  React 19 / Vite / TypeScript / Ant Design 5   (frontend/)
        │  fetch (VITE_API_BASE_URL)
        ▼
  FastAPI / SQLAlchemy / Pydantic               (backend/)
        │
        ├── MariaDB  insight_admin   ── admins                          (관리자 계정)
        │                            └─ resource_reservation_requests   (자원예약)
        └── MariaDB  desk_users      ── users                           (가입신청)

  외부 연동: TD 시스템 ──POST──▶ /api/external/td/...   (자원예약 신청 수신)
            Slurm    ◀──POST── slurm_service           (예약 생성, 기본 MOCK)
```

---

## 2. 5분 만에 로컬 띄우기

### 사전 준비: MariaDB 두 개의 DB

```sql
CREATE DATABASE insight_admin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE desk_users    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

> Docker가 편하면 [deploy/docker-compose.yml](deploy/docker-compose.yml)로 MariaDB + 백엔드를 한 번에 띄울 수 있습니다.
> ([deploy/mariadb/init/01-init.sql](deploy/mariadb/init/01-init.sql)이 DB·계정·권한을 자동 생성)

### 백엔드 ([backend/](backend/))

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # ADMIN_DATABASE_URL / USER_DATABASE_URL 등 수정
uvicorn app.main:app --reload
```

- 첫 실행 시 [init_db.py](backend/app/db/init_db.py)가 테이블을 만들고 초기 관리자(`admin` / `.env`의 `INITIAL_ADMIN_PASSWORD`)를 생성합니다.
- 확인: Swagger `http://127.0.0.1:8000/docs`, Health `http://127.0.0.1:8000/api/v1/health`

### 프론트엔드 ([frontend/](frontend/))

```bash
cd frontend
npm install
cp .env .env.local          # VITE_API_BASE_URL, VITE_*_URL(iframe), VITE_WS_BASE_URL 설정
npm run dev                 # http://localhost:5173
```

- 로그인: `admin` / 위에서 정한 비밀번호
- iframe URL이나 자원예약 백엔드가 없으면 더미로 볼 수 있습니다: `VITE_USE_DUMMY_RESERVATIONS=true`, `VITE_USE_DUMMY_RESERVATION_REQUESTS=true`

---

## 3. 저장소 지도 — 어디서 무엇을 찾나

```
backend/app/
  main.py              앱 시작점. 라우터 3개 등록(api_router + admin_resource + td_external)
  core/config.py       모든 환경변수 정의 (DB URL, JWT, TD/Slurm 키, iframe URL)
  core/security.py     비밀번호 해시(Argon2), JWT 발급/검증
  db/session.py        admin DB / user DB 엔진·세션 분리 ★
  db/init_db.py        create_all + 초기 관리자 생성
  dependencies/auth.py Bearer 토큰 → 현재 관리자
  models/              admin.py / user.py / resource_reservation.py (SQLAlchemy)
  schemas/             Pydantic 요청·응답
  services/            비즈니스 로직 (auth / user / admin / resource_reservation / slurm / terminal)
  api/v1/endpoints/    공개+관리자 REST (auth, users, config, health, terminals)
  api/admin/resource.py    관리자 자원예약 승인/거절/재시도 API
  api/external/td.py       외부 TD 자원예약 수신 API (API 키 인증)

frontend/src/
  App.tsx              라우팅(/login, /register, /ops/*). /ops는 PrivateRoute로 보호
  pages/Layout.tsx     관리자 셸: 메뉴, 가입신청 알림 폴링(30초)
  pages/Login.tsx, Register.tsx
  pages/sub_pages/             관제 화면(iframe)들 + Settings
  pages/sub_pages/settings/    UserApprovalPage(가입승인), ResourceReservation*(자원예약)
  api/                 백엔드 호출 모듈
  config/terminals.ts  API_BASE_URL / WS_BASE_URL

deploy/                docker-compose, MariaDB init SQL, 백엔드 이미지 tar, 운영 .env
```

---

## 4. 핵심 워크플로우 두 개

### A. 가입신청 승인

```
Register.tsx ─POST /api/v1/auth/register─▶ user_service.create_user()
   → desk_users.users 저장 (approval_status=pending, is_active=False)

UserApprovalPage ─GET /api/v1/users?approval_status=pending─▶ 목록
   ├─ PATCH /api/v1/users/{id}/approval {"status":"approved"} → approved 표시 (is_active는 그대로 False)
   └─ PATCH ... {"status":"rejected"}                        → 레코드 삭제 ⚠️
```

### B. 자원예약 승인 (신규 기능)

```
[외부 TD] ─POST /api/external/td/resource-reservation-requests─▶ (X-TD-API-KEY 인증)
   → 검증 통과: PENDING_APPROVAL  /  검증 실패: VALIDATION_FAILED
   → insight_admin.resource_reservation_requests 저장 (idempotencyKey로 중복 방지)

[관리자] api/admin/resource.py
   approve  (PENDING_APPROVAL만, 검증ERROR 불가) → APPLYING_TO_SLURM → Slurm 반영
                                                      ├ 성공 → SLURM_RESERVED
                                                      └ 실패 → SLURM_APPLY_FAILED
   reject   (PENDING_APPROVAL/VALIDATION_FAILED/SLURM_APPLY_FAILED) → REJECTED (사유 보존)
   retry    (SLURM_APPLY_FAILED만) → APPLYING_TO_SLURM → ...
```

상태값 정의와 전이는 [resource_reservation_service.py](backend/app/services/resource_reservation_service.py#L28-L35)에 있습니다.

---

## 5. ⚠️ 반드시 알아야 할 설계 결정과 함정

신규 합류자가 며칠 헤맬 수 있는 지점입니다. **먼저 읽으세요.**

1. **DB가 두 개로 물리 분리** — 관리자(`insight_admin`)와 가입신청(`desk_users`)은 엔진·세션부터 다릅니다([session.py](backend/app/db/session.py)). 자원예약은 `insight_admin` 쪽입니다. 모델이 `AdminBase`/`UserBase` 중 무엇을 상속하는지 항상 확인하세요.

2. **"승인 ≠ 자동 생성"** — 가입 승인해도 `is_active`는 `False`로 남습니다. 실제 Desk/OpenLDAP 등록은 **수동 전제**입니다. (자동 프로비저닝은 별도 요구가 없으면 구현하지 않음 — [AGENTS.md](AGENTS.md) 작업 원칙 3)

3. **거절 정책이 두 기능에서 정반대** ★
   - 가입신청 거절 → **레코드 삭제** (이력 없음, `rejection_reason` 컬럼 있지만 안 씀)
   - 자원예약 거절 → **`REJECTED` 상태 + 사유 보존 + 감사 로그**
   - 헷갈리기 쉬우니 어느 기능을 만지는지 의식하세요.

4. **Slurm은 기본 MOCK** — `SLURM_RESERVATION_MOCK=true`(기본)면 실제 Slurm을 호출하지 않고 성공으로 처리합니다([slurm_service.py](backend/app/services/slurm_service.py#L26)). 실연동하려면 `false` + `SLURM_REST_*` 설정 필요.

5. **인증 검증이 약함** — 프론트 [PrivateRoute](frontend/src/components/PrivateRoute.tsx)는 `localStorage.token` **존재 여부만** 확인하고 `/auth/me` 검증은 하지 않습니다.

6. **CORS 설정 버그 의심** — [main.py](backend/app/main.py)가 `allow_origins=settings.cors_origins`(콤마 문자열)를 그대로 넘깁니다. 리스트 파싱용 `cors_origins_list`가 있는데 미사용입니다. CORS 이슈가 보이면 여기부터.

7. **터미널은 데모 스텁** — 백엔드 `WS /api/v1/ws/term/{target}`는 실제 셸이 아니고, 프론트 터미널 설정과도 아직 직접 연결되지 않습니다.

8. **README는 2026.04.29 기준** — 그 이후 추가된 자원예약 기능은 README에 없습니다(이 문서가 보충). 코드가 정답입니다.

---

## 6. 코드 읽는 순서 (처음 1~2시간)

1. [README.md](README.md) — 전체 해설 (특히 11번 핵심 포인트)
2. [backend/app/main.py](backend/app/main.py) → [core/config.py](backend/app/core/config.py) → [db/session.py](backend/app/db/session.py)
3. [models/user.py](backend/app/models/user.py) → [api/v1/endpoints/auth.py](backend/app/api/v1/endpoints/auth.py) → [endpoints/users.py](backend/app/api/v1/endpoints/users.py)
4. [models/resource_reservation.py](backend/app/models/resource_reservation.py) → [services/resource_reservation_service.py](backend/app/services/resource_reservation_service.py) → [api/admin/resource.py](backend/app/api/admin/resource.py) → [api/external/td.py](backend/app/api/external/td.py)
5. 프론트: [App.tsx](frontend/src/App.tsx) → [pages/Layout.tsx](frontend/src/pages/Layout.tsx) → [Register.tsx](frontend/src/pages/Register.tsx) → [settings/UserApprovalPage.tsx](frontend/src/pages/sub_pages/settings/UserApprovalPage.tsx) → [settings/ResourceReservationPage.tsx](frontend/src/pages/sub_pages/settings/ResourceReservationPage.tsx)
6. `git log --oneline`으로 최근 작업 흐름 훑기

---

## 7. 작업 규칙 & 검증

상세 원칙은 [AGENTS.md](AGENTS.md). 요약하면:

- **구현 전 계획 우선** — API 계약 / DB 스키마 / 인증·인가 / 주요 UI 흐름 변경은 범위·단계·영향을 먼저 공유
- **Small Diff** — 한 번에 크게 바꾸지 않기
- **보안 기본값** — 비밀번호·민감정보는 저장/로그/응답/화면에서 평문 금지. 프론트 `VITE_*`는 브라우저에 노출됨을 전제

변경 후 검증:

```bash
# frontend
cd frontend && npm run lint && npm run build

# backend
cd backend && python -m compileall app && pytest

# deploy
cd deploy && docker compose config
```

---

## 8. 향후 방향 (합류 맥락)

이 프로젝트의 다음 단계는 **edition별 납품**입니다([AGENTS.md](AGENTS.md) Edition 전략).

- `basic` / `snmp-only` / `k8s-only` / `full` 같은 edition을 **브랜치가 아니라** feature flag + values + 패키지 manifest로 구분
- 공통 이미지 단일 빌드, 단일 Helm chart(`values-<edition>.yaml`)
- 폐쇄망 납품(이미지 tar + Helm chart + install script) 고려
- 다음 작업 1순위: 레포 전체 **기능 전수조사 → inventory 문서 → feature key 확정**

---

## 9. 첫 작업까지 체크리스트

- [ ] MariaDB 두 DB 생성, 백엔드 `.env` 설정
- [ ] 백엔드 `uvicorn` 기동, `/docs`에서 API 확인
- [ ] 프론트 `npm run dev`, `admin`으로 로그인
- [ ] `/register`로 가입 신청 → 관리자 화면에서 승인/거절 직접 해보기
- [ ] (선택) `VITE_USE_DUMMY_RESERVATIONS=true`로 자원예약 화면 둘러보기
- [ ] 5번 "함정" 다시 정독
- [ ] 작은 작업 하나로 첫 PR (lint/build/pytest 통과 확인)

---

_최종 갱신: 2026-05-22 · 코드와 어긋나면 코드가 정답입니다._

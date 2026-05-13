**1. 프로젝트 한 줄 요약**
TSlurm Insight 관리자 웹앱으로, 외부 모니터링 화면을 iframe으로 통합하고 Desk 회원가입 신청을 공개로 받아 관리자가 승인/거절하는 React + FastAPI + MariaDB 프로젝트입니다.

**2. 프로젝트 목적과 기능**
사용자 관점 기능은 크게 두 갈래입니다.

| 사용자 | 주요 흐름 |
|---|---|
| 일반 신청자 | `/register`에서 아이디, 비밀번호, 이름, 생년월일, 소속, 이메일 입력 → `/api/v1/auth/register` 호출 → `desk_users.users`에 `pending` 신청 생성 |
| 관리자 | `/login`에서 Insight 관리자 로그인 → `/ops/*` 진입 → Dashboard/Node/Job/GPU/Power/K8s/SNMP 외부 화면 조회 → `/ops/settings`에서 Desk 가입신청 조회/승인/거절 |

중요한 설계는 “Insight 관리자 계정”과 “Desk 가입신청 사용자”가 분리되어 있다는 점입니다. 관리자는 `insight_admin.admins`에 있고, 가입신청 데이터는 `desk_users.users`에 있습니다.

**3. 디렉터리 구조 설명**
| 경로 | 역할 |
|---|---|
| [frontend](/Users/choi/Documents/insight-inseok/frontend) | React/Vite 기반 관리자 UI와 공개 가입신청 페이지 |
| [frontend/src/pages](/Users/choi/Documents/insight-inseok/frontend/src/pages) | 로그인, 가입신청, 관리자 레이아웃, 하위 페이지 |
| [frontend/src/pages/sub_pages](/Users/choi/Documents/insight-inseok/frontend/src/pages/sub_pages) | Dashboard/Node/Job/GPU/Power/K8s/SNMP/Terminal/Settings 화면 |
| [backend](/Users/choi/Documents/insight-inseok/backend) | FastAPI 백엔드 |
| [backend/app/api/v1/endpoints](/Users/choi/Documents/insight-inseok/backend/app/api/v1/endpoints) | 실제 REST/WebSocket 엔드포인트 |
| [backend/app/models](/Users/choi/Documents/insight-inseok/backend/app/models) | SQLAlchemy ORM 모델 |
| [backend/app/schemas](/Users/choi/Documents/insight-inseok/backend/app/schemas) | Pydantic 요청/응답 스키마 |
| [backend/app/services](/Users/choi/Documents/insight-inseok/backend/app/services) | 인증, 관리자, 사용자 승인 비즈니스 로직 |
| [deploy](/Users/choi/Documents/insight-inseok/deploy) | Docker Compose, MariaDB 초기화 SQL, 백엔드 이미지 tar, 운영 env 파일 |
| [backend/data](/Users/choi/Documents/insight-inseok/backend/data) | SQLite DB 파일들. 현재 코드의 기본 운영 경로는 MariaDB라 과거/로컬 산출물로 보입니다. |

실행 흐름은 `frontend fetch -> backend /api/v1 -> SQLAlchemy 세션 -> MariaDB`입니다. 프론트 정적 파일은 `frontend/dist`로 빌드되고, 백엔드는 Docker 컨테이너에서 `uvicorn app.main:app`로 실행되도록 되어 있습니다.

**4. 프론트엔드 분석**
주요 스택은 [frontend/package.json](/Users/choi/Documents/insight-inseok/frontend/package.json:1) 기준 React 19, Vite 7, TypeScript, Ant Design 5, React Router 7, xterm입니다.

| 라이브러리 | 역할 |
|---|---|
| `react`, `react-dom` | 화면 컴포넌트 렌더링 |
| `vite` | 개발 서버와 정적 빌드 |
| `typescript` | 정적 타입 검사 |
| `antd` | Form, Button, Layout, Table, Modal, Message 등 UI |
| `@ant-design/icons` | 메뉴/폼 아이콘 |
| `react-router-dom` | `/login`, `/register`, `/ops/*` 라우팅 |
| `xterm`, addons | 브라우저 터미널 UI |

라우팅은 [frontend/src/App.tsx](/Users/choi/Documents/insight-inseok/frontend/src/App.tsx:1)에 있습니다. `/`는 `/login`, `/register`는 공개 가입신청, `/ops` 하위는 [PrivateRoute](/Users/choi/Documents/insight-inseok/frontend/src/components/PrivateRoute.tsx:1)로 보호됩니다. 단, `PrivateRoute`는 `localStorage.token` 존재만 확인하고 `/auth/me` 검증은 하지 않습니다.

로그인은 [Login.tsx](/Users/choi/Documents/insight-inseok/frontend/src/pages/Login.tsx:1)에서 `POST /api/v1/auth/login`을 호출하고, 성공 시 `token`, `token_type`, `user`를 localStorage에 저장합니다. 가입신청은 [Register.tsx](/Users/choi/Documents/insight-inseok/frontend/src/pages/Register.tsx:1)에서 `POST /api/v1/auth/register`를 호출합니다. 비밀번호 확인값은 프론트에서 비교만 하고 서버에는 보내지 않습니다.

관리자 레이아웃은 [Layout.tsx](/Users/choi/Documents/insight-inseok/frontend/src/pages/Layout.tsx:1)입니다. 좌측 메뉴, 상단 Breadcrumb, 사용자 드롭다운, 가입신청 알림 Popover가 있습니다. 알림은 30초마다 `/api/v1/users?approval_status=pending`을 폴링합니다. 가입신청 관리는 [Settings.tsx](/Users/choi/Documents/insight-inseok/frontend/src/pages/sub_pages/Settings.tsx:1)에서 대기 신청 목록 조회, 상세 Modal, 승인/거절 PATCH를 수행합니다.

Dashboard/Node/Job/GPU/Power/K8s/SNMP 페이지는 각각 `VITE_*_URL` 환경변수의 외부 URL을 iframe으로 보여주는 구조입니다. 임베드가 차단되면 새 탭 열기 버튼을 표시합니다.

주의할 점은 `Layout.tsx`가 `localStorage.userName`을 읽지만 로그인은 `user` JSON만 저장한다는 점, `App.tsx`에 중복 `index` route와 중복 wildcard route가 있다는 점, 터미널 프론트 설정은 [terminals.ts](/Users/choi/Documents/insight-inseok/frontend/src/config/terminals.ts:1)에 하드코딩된 `ws://192.168.1.100:3001/term`을 사용해 백엔드 WebSocket 스텁과 아직 직접 연결되지 않는다는 점입니다.

**5. 백엔드 분석**
주요 스택은 [backend/requirements.txt](/Users/choi/Documents/insight-inseok/backend/requirements.txt:1) 기준 FastAPI, Uvicorn, SQLAlchemy, PyMySQL, Pydantic Settings, PyJWT, pwdlib Argon2, python-multipart입니다.

| 파일 | 역할 |
|---|---|
| [main.py](/Users/choi/Documents/insight-inseok/backend/app/main.py:1) | FastAPI 앱 생성, CORS, lifespan에서 DB 초기화 |
| [core/config.py](/Users/choi/Documents/insight-inseok/backend/app/core/config.py:1) | env 기반 설정 로딩 |
| [db/session.py](/Users/choi/Documents/insight-inseok/backend/app/db/session.py:1) | admin/user DB 엔진과 세션 분리 |
| [db/init_db.py](/Users/choi/Documents/insight-inseok/backend/app/db/init_db.py:1) | `create_all()` 및 초기 관리자 생성 |
| [core/security.py](/Users/choi/Documents/insight-inseok/backend/app/core/security.py:1) | 비밀번호 해시, JWT 발급/검증 |
| [dependencies/auth.py](/Users/choi/Documents/insight-inseok/backend/app/dependencies/auth.py:1) | Bearer 토큰에서 현재 관리자 추출 |

API 구조는 [router.py](/Users/choi/Documents/insight-inseok/backend/app/api/router.py:1)에서 `health`, `auth`, `users`, `config`, `terminals`를 `/api/v1` 아래에 붙입니다.

| API | 권한 | 역할 |
|---|---|---|
| `POST /api/v1/auth/login` | 공개 | 관리자 로그인. admin DB 조회 |
| `POST /api/v1/auth/token` | 공개 | Swagger OAuth2 form 로그인용 |
| `POST /api/v1/auth/register` | 공개 | Desk 가입신청 생성. user DB 저장 |
| `GET /api/v1/auth/me` | 관리자 | 현재 관리자 정보 |
| `GET /api/v1/users` | 관리자 | 가입신청/사용자 목록, 상태/검색 필터 |
| `GET /api/v1/users/{id}` | 관리자 | 가입신청 상세 |
| `PATCH /api/v1/users/{id}/approval` | 관리자 | 승인/거절 |
| `GET /api/v1/config/frontend` | 관리자 | 대시보드 URL/터미널 설정 반환 의도 |
| `GET /api/v1/health` | 공개 | 헬스체크 |
| `WS /api/v1/ws/term/{target}` | 토큰 필요 | 실제 shell이 아닌 데모 터미널 스텁 |

인증은 관리자 전용입니다. 일반 가입신청 사용자는 Insight에 로그인하지 않습니다. `auth_service.build_token_response()`가 관리자 username을 `sub`로 하는 JWT를 만들고, 이후 관리자 API는 `Authorization: Bearer <token>`을 요구합니다.

**6. 데이터베이스 구조 분석**
DB는 두 개로 나뉩니다.

| DB | 테이블 | 역할 |
|---|---|---|
| `insight_admin` | `admins` | Insight 관리자 로그인 계정 |
| `desk_users` | `users` | Desk 가입신청 데이터 |

`admins` 모델은 [models/admin.py](/Users/choi/Documents/insight-inseok/backend/app/models/admin.py:1)에 있고 컬럼은 `id`, `username`, `password_hash`, `full_name`, `is_active`, `created_at`, `updated_at`입니다. `role`은 DB 컬럼이 아니라 property로 항상 `"admin"`을 반환합니다.

`users` 모델은 [models/user.py](/Users/choi/Documents/insight-inseok/backend/app/models/user.py:1)에 있습니다. 주요 컬럼은 `username`, `password_hash`, `full_name`, `email`, `birth_date`, `affiliation`, `is_active`, `approval_status`, `reviewed_at`, `reviewed_by`, `rejection_reason`, timestamps입니다.

가입신청 생성 흐름은 `Register.tsx -> POST /auth/register -> user_service.create_user()`입니다. 비밀번호는 [security.py](/Users/choi/Documents/insight-inseok/backend/app/core/security.py:1)의 `pwdlib.PasswordHash.recommended()`로 해시되어 `password_hash`에 저장됩니다. 생성 시 `approval_status=pending`, `is_active=False`입니다.

승인 흐름은 `Settings.tsx -> PATCH /users/{id}/approval {"status":"approved"} -> approve_user()`입니다. 상태는 `approved`, `reviewed_at`, `reviewed_by`가 기록되지만 `is_active`는 계속 `False`입니다. 즉 “승인”은 Insight/DB상 처리 완료 표시이고, 실제 Desk/OpenLDAP 등록은 수동으로 하라는 설계입니다.

거절 흐름은 `{"status":"rejected"}` 요청 시 `reject_user()`가 레코드를 삭제합니다. 따라서 `REJECTED` enum과 `rejection_reason` 컬럼은 존재하지만 현재 거절 이력으로 저장되지는 않습니다. 이 부분은 유지보수 시 가장 헷갈리기 쉽습니다.

초기 관리자는 [admin_service.ensure_initial_admin](/Users/choi/Documents/insight-inseok/backend/app/services/admin_service.py:1)이 앱 시작 시 `INITIAL_ADMIN_*` 환경변수를 읽어 없을 때만 생성합니다.

**7. 배포/운영 구조 분석**
배포 핵심은 [deploy/docker-compose.yml](/Users/choi/Documents/insight-inseok/deploy/docker-compose.yml:1)입니다.

| 서비스 | 구조 |
|---|---|
| `mariadb` | `mariadb:11.4`, volume `mariadb_data`, init SQL 마운트, healthcheck |
| `backend` | `../backend`에서 Docker build, `.env.backend` 주입, MariaDB healthy 이후 시작, `127.0.0.1:8000:8000` 바인딩 |

[deploy/mariadb/init/01-init.sql](/Users/choi/Documents/insight-inseok/deploy/mariadb/init/01-init.sql:1)은 `insight_admin`, `desk_users` DB와 각각의 DB 사용자를 생성하고 권한을 줍니다. 운영 env 파일은 키 기준으로 `SECRET_KEY`, DB URL, CORS, 초기 관리자, iframe URL들을 담습니다. 값은 민감정보라 코드/문서에 노출하지 않는 것이 맞습니다.

프론트는 Docker Compose에 포함되어 있지 않고, `npm run build` 결과물인 `frontend/dist`를 Nginx 같은 정적 서버로 배포하는 형태로 보입니다. 백엔드가 `127.0.0.1:8000`에만 열려 있으므로 실제 외부 공개는 Nginx reverse proxy가 `/api`를 백엔드로 넘기고 정적 파일을 서빙하는 구성이 자연스럽습니다. 다만 Nginx 설정 파일은 저장소에 없습니다.

**8. 사용 기술 스택 및 라이브러리 설명**
| 영역 | 기술 | 이 프로젝트에서의 역할 |
|---|---|---|
| Frontend | React | 화면 컴포넌트 기반 UI |
| Frontend | Vite | 빠른 개발 서버와 정적 빌드 |
| Frontend | TypeScript | API 응답/폼 데이터 타입 안정성 |
| Frontend | Ant Design | 관리자 콘솔에 필요한 Form/Table/Layout/Modal 제공 |
| Frontend | React Router | 공개 페이지와 관리자 페이지 라우팅 |
| Frontend | xterm | 웹 터미널 UI 실험/스텁 연결 |
| Backend | FastAPI | REST API, Swagger, WebSocket |
| Backend | SQLAlchemy | `admins`, `users` ORM과 DB 세션 |
| Backend | Pydantic | 요청 검증, 응답 직렬화, env 설정 |
| Backend | PyJWT | 관리자 Bearer 토큰 |
| Backend | pwdlib Argon2 | 비밀번호 해시 저장 |
| Backend | PyMySQL | SQLAlchemy에서 MariaDB 접속 |
| DB | MariaDB | 관리자 DB와 Desk 가입신청 DB 저장 |
| Deploy | Docker Compose | MariaDB와 백엔드 컨테이너 운영 |
| Deploy | Nginx 추정 | 프론트 정적 배포 및 API reverse proxy 역할 |

**9. 처음 이해할 때 읽어야 할 핵심 파일 순서**
1. [backend/README.md](/Users/choi/Documents/insight-inseok/backend/README.md:1) - 백엔드 의도와 API 개요
2. [frontend/package.json](/Users/choi/Documents/insight-inseok/frontend/package.json:1) - 프론트 스택 파악
3. [backend/requirements.txt](/Users/choi/Documents/insight-inseok/backend/requirements.txt:1) - 백엔드 스택 파악
4. [backend/app/main.py](/Users/choi/Documents/insight-inseok/backend/app/main.py:1) - 앱 시작점
5. [backend/app/core/config.py](/Users/choi/Documents/insight-inseok/backend/app/core/config.py:1) - 환경변수와 DB URL
6. [backend/app/db/session.py](/Users/choi/Documents/insight-inseok/backend/app/db/session.py:1) - admin/user DB 분리
7. [backend/app/models/user.py](/Users/choi/Documents/insight-inseok/backend/app/models/user.py:1) - 가입신청 데이터 모델
8. [backend/app/api/v1/endpoints/auth.py](/Users/choi/Documents/insight-inseok/backend/app/api/v1/endpoints/auth.py:1) - 로그인/가입신청 API
9. [backend/app/api/v1/endpoints/users.py](/Users/choi/Documents/insight-inseok/backend/app/api/v1/endpoints/users.py:1) - 관리자 승인 API
10. [frontend/src/App.tsx](/Users/choi/Documents/insight-inseok/frontend/src/App.tsx:1) - 라우팅
11. [frontend/src/pages/Register.tsx](/Users/choi/Documents/insight-inseok/frontend/src/pages/Register.tsx:1) - 공개 신청 화면
12. [frontend/src/pages/sub_pages/Settings.tsx](/Users/choi/Documents/insight-inseok/frontend/src/pages/sub_pages/Settings.tsx:1) - 관리자 승인 화면

**10. 이 프로젝트를 이해하기 위해 공부하면 좋은 주제**
1. React + TypeScript 기본: 컴포넌트, props/state, hooks, form 흐름을 알아야 프론트 화면을 읽을 수 있습니다.
2. Vite 환경변수와 빌드: `VITE_*`가 iframe URL/API URL로 쓰이므로 배포별 설정 이해가 중요합니다.
3. React Router: `/login`, `/register`, `/ops/*`, nested route, 보호 라우팅 구조를 이해해야 합니다.
4. Ant Design: Form validation, Table, Modal, Message, Layout이 UI 대부분을 차지합니다.
5. FastAPI: router, dependency injection, response_model, HTTPException, WebSocket 구조가 핵심입니다.
6. Pydantic/Pydantic Settings: 요청 검증과 `.env` 설정 로딩을 이해해야 합니다.
7. SQLAlchemy ORM: 모델, 세션, `select`, `create_all`, enum 매핑을 알아야 DB 흐름이 보입니다.
8. JWT 인증: 로그인 후 토큰 저장, Bearer 인증, 만료/검증 구조를 이해해야 합니다.
9. 비밀번호 해시/Argon2: 평문 비밀번호 금지 원칙과 `password_hash` 저장 방식을 이해해야 합니다.
10. MariaDB/SQL 기초: DB/schema 분리, 테이블, 인덱스, 권한 부여 구조가 운영에 직접 연결됩니다.
11. Docker Compose: MariaDB healthcheck, env_file, volume, backend build/port binding을 이해해야 배포를 다룰 수 있습니다.
12. Nginx reverse proxy: 프론트 정적 서빙과 `/api` 프록시가 저장소 밖 운영 구조로 보이므로 실무 연결에 필요합니다.

**11. 최종 요약 및 핵심 포인트**
이 프로젝트의 중심은 “TSlurm Insight 관리자 콘솔 + Desk 가입신청 승인 워크플로우”입니다. 프론트는 React/AntD로 관리자 UI를 만들고, 백엔드는 FastAPI/SQLAlchemy로 관리자 인증과 가입신청 데이터를 처리합니다.

가장 중요한 이해 포인트는 세 가지입니다. 첫째, 관리자 계정과 Desk 가입신청 계정은 DB부터 분리되어 있습니다. 둘째, 승인 처리는 OpenLDAP 자동 연동이 아니라 수동 등록 완료를 전제로 한 상태 변경입니다. 셋째, 거절은 `rejected` 상태 저장이 아니라 레코드 삭제로 구현되어 있어 감사 이력 요구가 생기면 설계를 바꿔야 합니다.

주의 포인트로는 `PrivateRoute`의 토큰 존재 여부만 보는 방식, 프론트 터미널 설정과 백엔드 터미널 스텁의 불일치, `config`/CORS 설정에서 문자열 리스트 파싱이 완전히 반영되지 않은 부분, Nginx 설정 부재가 있습니다. 유지보수는 가입신청 승인 정책과 배포 설정을 먼저 명확히 잡고 진행하는 게 좋습니다.


2026.04.29 기준
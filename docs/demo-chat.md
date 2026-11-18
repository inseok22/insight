# 회사·한국공항공사 공통 시연 채팅

기존 T-LLM Observability의 로그인과 FastAPI 서버를 사용해 실제 모델에 질문하고 Langfuse에서 사용자·대화·질문별 기록을 확인하는 공통 시연 기능입니다. 회사와 한국공항공사는 같은 코드와 이미지에 환경별 연결 설정을 적용합니다. DB 스키마를 바꾸거나 별도 채팅 서비스를 설치하지 않습니다.

현재 우선순위는 회사의 실제 vLLM·Langfuse 연결 검증입니다. 회사에서 실행 중인 Nginx와 기존 모니터링 구성을 유지합니다. 한국공항공사 IP·프록시 설정 적용과 최종 폐쇄망 패키징은 이후 작업이며 [KAC 패키징 체크리스트](kac-packaging-checklist.md)에 별도로 정리합니다.

## 배포 경로와 범위

```text
브라우저의 기존 회사 웹 주소
  → 기존 Nginx /api/v1/chat/
  → 기존 FastAPI 백엔드
  → 회사의 VLLM_API_BASE_URL

FastAPI → LANGFUSE_BASE_URL (Langfuse SDK 수집)
브라우저 iframe → VLLM_OBSERVABILITY_URL (기존 화면 주소)
```

모델 선택 화면, 영구 대화 DB, 파일 업로드, RAG·검색·에이전트는 포함하지 않습니다. 연결 주소·모델·키는 `.env.backend`에서 변경하며 프론트 번들에 넣지 않습니다. 회사 연결 테스트에 한국공항공사 주소를 사용하지 않습니다.

## `.env.backend` 설정

`deploy/.env.backend.example`는 **추가할 연결 설정 블록**입니다. 기존 `deploy/.env.backend`의 DB·인증·Grafana 설정을 유지하면서 필요한 키만 병합합니다. 전체 파일을 예제로 덮어쓰지 않고, 같은 키가 이미 있으면 기존 선언을 수정합니다. 실제 자격증명은 예제 파일·소스·로그에 남기지 않습니다.

| 항목 | 의미와 초기값 |
|---|---|
| `DEMO_CHAT_ENABLED` | 기본 `false`. `true`이면 시연 채팅 메뉴·화면·API 활성화 |
| `SEED_DEMO_ACCOUNTS` | 이전 환경파일 호환용. 현재 서버 시작 시 값과 무관하게 데모 계정 생성 안 함 |
| `VLLM_API_BASE_URL` | 환경별 실제 OpenAI 호환 API 루트. 형식 예시 `http://vllm.example.test:8001/v1` |
| `VLLM_MODEL` | 실제 모델 ID. 비우면 서버에서 `/v1/models` 조회; 여러 모델이면 ID를 명시 |
| `VLLM_API_KEY` | 선택 항목. vLLM 인증이 필요한 경우만 설정 |
| `VLLM_TIMEOUT_SECONDS` | 요청 제한 시간(초), 기본 `120` |
| `LANGFUSE_BASE_URL` | 백엔드가 접근할 Langfuse SDK 수집 루트. 예시 `http://langfuse.example.test:3000` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse 프로젝트 public key |
| `LANGFUSE_SECRET_KEY` | 같은 프로젝트의 secret key |
| `LANGFUSE_TRACING_ENABLED` | 기본 `false`. URL/키 설정 후 `true`로 수집 활성화 |

`LANGFUSE_BASE_URL`에는 프로젝트 화면 주소나 `/api/public/ingestion` 등을 붙이지 않습니다. 기존 브라우저용 `VLLM_OBSERVABILITY_URL`과 서로 다른 설정이며, iframe 주소를 바꿔도 SDK 주소가 자동 변경되지 않습니다.

`LANGFUSE_TRACING_ENABLED=true`여도 수집 URL·public key·secret key 중 누락된 값이 있으면 일반 경고만 남기고 수집을 비활성화합니다. 실제 설정값이나 키를 경고에 출력하지 않으며 채팅은 계속 사용할 수 있습니다. 수집이 필요한 시연에서는 세 항목을 모두 채우고 연결한 Langfuse에서 Trace 도착을 확인합니다.

Python SDK는 `langfuse==5.2.0`, HTTP 클라이언트는 `httpx==0.28.1`로 고정합니다. Langfuse 공식 마이그레이션 문서에 따르면 Python SDK v5는 **Python 3.11 이상**과 **Langfuse Cloud 또는 자체 호스팅 서버 4.59.0 이상**이 필요하며, 서버 v3와 그 이전 v4는 지원하지 않습니다. 연동 대상 서버는 4.76.0 기준입니다. 이 문서의 아래쪽에 남아 있는 회사 서버 `3.224.0` health 기록은 2026-10-15 시점 값이므로, 그 서버가 4.59.0 이상으로 올라갔는지 확인한 뒤 수집을 켭니다. SDK v5는 span 묶음을 gzip으로 전송하므로 중간 프록시가 gzip 본문을 거부하면 `LANGFUSE_OTEL_COMPRESSION=none`을 설정합니다. KAC 서버 버전은 아직 미확인입니다. [v3→v4](https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4), [v4→v5](https://langfuse.com/docs/observability/sdk/upgrade-path/python-v4-to-v5)

이 저장소의 Compose는 `backend.env_file`로 `.env.backend`를 컨테이너에 전달합니다. 채팅 설정을 Compose `environment`에 중복 기재하지 않아 파일의 값이 그대로 사용됩니다. 백엔드 포트만 기존 방식대로 `deploy/.env`의 `BACKEND_PORT`를 사용합니다. 로컬 실행은 `backend/.env`에 같은 키를 사용합니다.

새 코드·의존성이 포함된 백엔드와 프론트의 **최초 반영 이후**, 주소·모델·키·타임아웃·활성화 여부를 바꿀 때는 이미지/프론트를 재빌드할 필요가 없습니다. 아래는 이 저장소의 Compose로 실행 중인 backend에 환경 변경을 반영하는 명령입니다. 회사의 실제 Compose 파일·프로젝트·서비스가 일치하는지 먼저 확인하고 해당 디렉터리에서 사용합니다. 문서 작성 과정에서 운영 컨테이너를 재생성하지 않았습니다.

```bash
docker compose config --quiet
docker compose up -d --no-deps --no-build --pull never --force-recreate backend
```

`docker compose restart`만으로는 변경된 `env_file`이 적용되지 않습니다. 재생성 후 브라우저를 새로고침합니다. 이 명령은 기존 DB 컨테이너와 볼륨을 재생성하지 않습니다. 시연 종료 후 `DEMO_CHAT_ENABLED=false`로 바꾸고 같은 명령을 실행하면 메뉴와 API가 함께 비활성화됩니다. 수집만 중지하려면 `LANGFUSE_TRACING_ENABLED=false`로 바꿉니다.

## 데모 계정과 백엔드 이미지

2026-10-17 `admin-only` 이미지부터 신규 DB의 초기 계정은 **admin/admin 하나**입니다. 서버 시작 시 `user1`, `user2`를 생성하는 호출을 제거했습니다. 이전 이미지의 데모 계정 생성 관련 기록은 아래에 보존합니다.

제공 환경파일은 `SEED_DEMO_ACCOUNTS=false`이며 이전 파일에 `true`가 남아 있어도 새 이미지에서는 데모 계정을 자동 생성하지 않습니다. 이미 생성된 계정의 로그인이나 관리자 권한은 유지됩니다. 채팅 메뉴/API의 활성화는 `DEMO_CHAT_ENABLED`로 별도 제어합니다.

백엔드 빌드 대상은 **Ubuntu 24.04 x86_64 호스트의 Docker에서 실행하는 `linux/amd64` 이미지**입니다. 컨테이너 기반 이미지는 기존 `python:3.12-slim`을 유지합니다. 아래 `demo-users`는 이전 빌드 기록이며, 사용자 추가·계정별 Trace 변경을 적용하려면 다음 절의 새 프론트와 백엔드를 함께 배포합니다.

2026-10-16 이전 빌드 `tslurm-backend:2026-10-16-demo-users`는 `linux/amd64` 이미지입니다. 반입 파일은 `deploy/tslurm-backend-2026-10-16-demo-users-linux-amd64.tar`(79,442,944바이트)이며 같은 경로에 `.tar.sha256` 체크섬과 `.build-info.json` 검증 기록을 제공합니다. 채팅·Langfuse 계측, 복구된 LLM 기능 설정, 관리자 PBKDF2-HMAC-SHA256 전환, 선택적 데모 계정 생성을 포함합니다.

- 네이티브 백엔드 컴파일, 테스트 82개·subtest 142개 및 폐쇄망 설치 도구 테스트 9개 통과.
- 빌드 이미지 내부에서 채팅·인증·계정·실행 포트 테스트 60개 통과. 스트리밍·중지·오류·Trace 관계는 모의 모델 및 메모리 exporter로 검증.
- 이미지의 코드·설정 예제 53개 파일이 현재 작업 파일과 일치하고 `pip check` 및 컴파일 통과. 실제 `.env`와 로컬 DB는 미포함.
- 네트워크가 차단된 컨테이너의 임시 SQLite DB로 실제 API 프로세스를 실행해 두 계정 로그인, 서로 다른 ID, 재시작 시 ID 유지, 새 대화 ID 변경, 세션 소유권, 정상 종료 확인.
- tar의 `linux/amd64` 아키텍처·태그·실행 명령과 SHA-256 체크섬 검증 완료.

실제 Ubuntu 서버와 현장 DB에서 실행하거나 vLLM·Langfuse 외부 연동을 검증한 결과는 아닙니다. 전체 KAC 폐쇄망 패키징과 Nginx 적용은 이후 작업으로 유지합니다. `docker compose config --quiet` 구문 검사는 통과했으나 기존 환경파일의 `$__all`에 대한 Compose 변수 치환 경고 4건은 남아 있습니다. 해당 값은 이번 빌드에서 변경하지 않았으며 실제 배포 시 Grafana 대상 URL이 의도대로 전달되는지 확인합니다.

아래는 이전 이미지의 반입 명령입니다. 현재 설치는 아래 `admin-only` 이미지 절을 따릅니다. 기존 `.env.backend`의 `SEED_DEMO_ACCOUNTS`는 `false`로 두고 DB/인증/관제 설정을 예제 파일로 덮어쓰지 않습니다.

```bash
sha256sum -c tslurm-backend-2026-10-16-demo-users-linux-amd64.tar.sha256
docker load -i tslurm-backend-2026-10-16-demo-users-linux-amd64.tar
docker compose up -d --no-deps --no-build --pull never --force-recreate backend
```

이 작업에서 현재 로컬 DB에 계정을 생성하거나 운영 backend를 재생성하지 않았습니다. 배포 후 backend가 시작되면 없는 계정만 생성됩니다.

## 사용자 추가와 계정별 Trace 반영 (2026-10-16)

사용자 추가·계정별 Trace를 처음 포함한 이미지는 `tslurm-backend:2026-10-16-user-management`입니다. 최신 재빌드는 아래 2026-10-17 절을 따릅니다.
프론트 산출물은 `frontend/dist/`, 백엔드 반입 파일은 `deploy/tslurm-backend-2026-10-16-user-management-linux-amd64.tar`입니다.
동일 경로의 `.tar.sha256`과 `.build-info.json`으로 파일 무결성과 빌드 기록을 확인합니다.

- 상단 사용자 메뉴에는 로그인 계정의 `username`을 표시하고 로그아웃 시 로그인 정보를 정리합니다.
- 활성 관리자가 `/ops/admin-users/new`에 직접 접속해 계정을 추가합니다. 메뉴에는 링크가 없습니다. 새 계정도 기존 관리자와 같은 권한입니다.
- 생성 API는 `POST /api/v1/admin/users`이며 기존 `admins` 테이블을 사용합니다. 비밀번호는 PBKDF2 해시로 저장하고 생성·오류 응답에 평문이나 해시를 포함하지 않습니다.
- 새 질문부터 Langfuse의 Trace 이름과 `user_id`가 서버가 인증한 `username`으로 기록됩니다. 기존 기록은 변경하지 않습니다.
- DB 스키마·환경파일 변경은 필요 없습니다. 실제 운영 배포와 외부 vLLM/Langfuse 수집 확인은 별도입니다.

반입 서버의 기존 Compose에서 backend 이미지 태그를 위 태그로 맞춘 뒤 `deploy/`에서 실행합니다.

```bash
sha256sum -c tslurm-backend-2026-10-16-user-management-linux-amd64.tar.sha256
docker load -i tslurm-backend-2026-10-16-user-management-linux-amd64.tar
docker compose up -d --no-deps --no-build --pull never --force-recreate backend
```

새 `frontend/dist/` 내용도 기존 Nginx 정적 파일 경로에 반영하고 브라우저를 새로고침합니다.
직접 URL 접속에는 기존 React SPA의 `index.html` fallback이 필요합니다. Nginx 경로·프록시 설정은 이번 작업에서 변경하지 않았습니다.
백엔드 재생성 시 메모리 채팅 이력은 초기화됩니다. 계정 DB와 이미 수집된 Trace는 유지됩니다.

검증: 백엔드 pytest 89개·subtest 158개, 프론트 테스트 25개, 이미지 내부 관련 unittest 67개 통과.
프론트 lint/build 성공(기존 lint 경고 5개 및 번들 크기 경고). 임시 SQLite와 모의 모델을 이용한 브라우저에서
미로그인 경로 차단, 비밀번호 확인, 계정 생성, 새 계정 로그인·상단 아이디·채팅 응답을 확인했습니다.
Langfuse 사용자/Trace 이름과 A/B 동시 세션 분리는 실제 SDK의 메모리 exporter로 검증했습니다.

## Ubuntu 24.04용 백엔드 재빌드 (2026-10-17)

기존 재빌드는 `tslurm-backend:2026-10-17`입니다. 초기 계정을 하나로 제한한 최신 버전은 다음 절의 `admin-only` 이미지입니다.
Ubuntu 24.04 **x86_64 호스트의 Docker**에서 실행할 `linux/amd64` 이미지입니다. 컨테이너는 기존 `python:3.12-slim`을 유지하며 프론트는 다시 빌드하지 않았습니다.
반입 파일은 `deploy/tslurm-backend-2026-10-17-linux-amd64.tar`, 무결성 확인은 같은 경로의 `.tar.sha256`, 빌드·검증 기록은 `.build-info.json`입니다.
사용자 추가 API·계정별 Trace 변경을 포함한 현재 백엔드 작업 파일로 빌드했고, 이전 이미지와 tar는 보존했습니다.

대상 서버의 기존 Compose에서 backend 이미지 태그를 `tslurm-backend:2026-10-17`로 변경하고 `deploy/`에서 실행합니다.

```bash
sha256sum -c tslurm-backend-2026-10-17-linux-amd64.tar.sha256
docker load -i tslurm-backend-2026-10-17-linux-amd64.tar
docker compose up -d --no-deps --no-build --pull never --force-recreate backend
```

검증: 로컬 백엔드 pytest 89개·subtest 158개와 `compileall`, 이미지 내부 관련 unittest 67개와 `pip check`·`compileall` 통과.
이미지 내부 앱 소스 52개 파일이 현재 코드와 일치하고 실제 `.env`·로컬 DB는 포함하지 않았습니다.
네트워크를 차단한 컨테이너에서 임시 SQLite DB로 실제 API 프로세스를 실행해 health, 계정 생성·로그인, 인증 차단,
세션 소유권, 재시작 후 계정 보존과 정상 종료를 확인했습니다. tar의 아키텍처·실행 명령·태그와 SHA-256도 검사했습니다.
Compose 검사는 통과했으며 기존 `$__all` 변수 치환 경고 4건은 그대로입니다.
실제 Ubuntu 서버 배포, 현장 MariaDB 및 외부 vLLM/Langfuse 연동 검증은 수행하지 않았습니다.

## 초기 계정 admin/admin 하나로 변경 (2026-10-17)

최신 이미지는 `tslurm-backend:2026-10-17-admin-only-r2`이며 저장소 Compose도 이 태그를 사용합니다. 현재 작업 파일로 `--no-cache --platform linux/amd64` 재빌드했습니다.
Ubuntu 24.04 x86_64 호스트의 Docker 실행용 `linux/amd64` 이미지입니다.
반입 파일은 `deploy/tslurm-backend-2026-10-17-admin-only-r2-linux-amd64.tar`와 같은 경로의 `.tar.sha256`, `.build-info.json`입니다.

새 DB에서는 `admin/admin`만 생성합니다. 로컬 `backend/.env`, `deploy/.env.backend`와 백엔드 예제 환경파일의 초기 비밀번호를
`INITIAL_ADMIN_PASSWORD_HASH`에 해시로 설정하고 `SEED_DEMO_ACCOUNTS=false`로 맞췄습니다.
서버 시작 시 데모 계정 생성 호출도 제거하여 이전 파일의 `SEED_DEMO_ACCOUNTS=true`로도 `user1`, `user2`가 생성되지 않습니다.
추가 사용자는 `/ops/admin-users/new`에서 만듭니다. 기존 계정 삭제나 기존 `admin` 비밀번호 재설정은 수행하지 않습니다.

```bash
sha256sum -c tslurm-backend-2026-10-17-admin-only-r2-linux-amd64.tar.sha256
docker load -i tslurm-backend-2026-10-17-admin-only-r2-linux-amd64.tar
docker compose up -d --no-deps --no-build --pull never --force-recreate backend
```

실제 서버에서는 기존 Compose의 backend 태그를 위 태그로 맞춥니다. 기존 DB가 있으면 초기 설정은 기존 계정·비밀번호를 덮어쓰지 않습니다.
이번 작업에서는 운영 DB나 실행 중인 backend를 변경하지 않았습니다.

재빌드 검증: 이미지 내부 관련 unittest 69개, 의존성·컴파일·소스 일치 검사 통과.
네트워크를 차단한 임시 컨테이너에서 이전 데모 설정을 `true`로 주어도 신규 DB에 `admin` 하나만 생성되고 요청한 초기 비밀번호로 로그인되는 것을 확인했습니다.
수동 추가 계정과 기존 비밀번호는 재시작 후 유지되며 tar 아키텍처·태그·실행 명령과 SHA-256을 검증했습니다.

## 메모리 세션과 worker 제한

세션 ID는 서버가 발급하고 인증된 `Admin.id`에 귀속합니다. 후속 질문·생성 중지 등 세션 접근마다 소유자를 검사합니다. Langfuse의 `user_id`는 각 질문을 보낼 때 서버가 인증한 내부 식별자 `Admin.id`(문자열)로 기록하며 로그인 `username`은 전송하지 않습니다. Trace 이름은 `chat.request`로 고정합니다. 브라우저가 보낸 임의의 `user_id`나 `username`은 허용하지 않습니다. 대화 이력 전문은 `vllm.generate`의 입력에만 저장하고 `history.prepare`·`prompt.build`에는 메시지 건수와 글자 수만 기록합니다. SDK v5 전환 이전의 `username` 기록은 변경하지 않습니다.

대화 이력은 FastAPI **프로세스 하나의 메모리**에만 있습니다. `app.serve`는 worker 1개로 실행하고, Compose도 backend replica 1개를 사용합니다. 별도 `uvicorn --workers`, 여러 backend 컨테이너, 분산 로드밸런싱으로 늘리지 않습니다. 프로세스가 나뉘면 요청을 받은 프로세스에 해당 대화가 없어 후속 질문·중지가 이어지지 않습니다.

세션은 2시간 유휴 후 만료하며 전체 200개로 제한합니다. 보관 이력은 최근 완료된 질문·답변 최대 20쌍, 최대 128,000문자 범위입니다. 질문은 최대 16,000문자, 한 답변은 최대 64,000문자로 제한합니다. 이 값은 모델의 토큰 수가 아니라 시연 서버 메모리 사용 제한입니다.

서버 재시작·컨테이너 재생성·세션 만료 뒤에는 새 대화를 시작해야 합니다. 완료된 대화의 문맥만 후속 질문에 사용하며, 취소·실패한 부분 답변은 완료된 턴으로 저장하지 않습니다. 새 대화는 새로운 `session_id`를 발급합니다. 대화 검색·삭제·내보내기나 서버 재시작 후 복원은 제공하지 않습니다.

이미 Langfuse에 전송된 Trace는 Langfuse 저장소에 남으며 채팅 메모리 삭제와 별개입니다. 애플리케이션은 시연 종료 시 Trace를 삭제하지 않습니다. 실제 보존 기간은 현장의 Langfuse 프로젝트 보존 설정·저장소·백업 정책을 따르므로 시연 결과 확인 기간에 맞춰 점검합니다. 강제 프로세스 종료나 수집 서버 장애 때 아직 전송되지 않은 항목까지 보존된다고 보장하지 않습니다.

## Trace 구조와 오류·취소

질문 한 번마다 새 Trace를 만들고 실제 실행 단계만 자식 관측 항목으로 기록합니다.

```text
대화 session_id
├─ 질문 1 Trace / 요청 루트 Span
│  ├─ 대화 이력 준비 Span
│  ├─ 프롬프트 구성 Span
│  └─ vLLM 호출 Generation
└─ 질문 2 Trace / 요청 루트 Span (같은 session_id)
   ├─ 대화 이력 준비 Span
   ├─ 프롬프트 구성 Span
   └─ vLLM 호출 Generation
```

모델명이 미설정이고 아직 조회 결과가 없어서 실제 `/v1/models` 조회를 수행하면 `model.resolve` Span도 기록합니다. 명시한 `VLLM_MODEL`이나 프로세스에 캐시된 실제 모델 ID를 사용할 때는 이 Span을 만들지 않습니다.

입력·출력, 실제 모델명, 시작·종료 시각, 성공·오류·취소 상태를 기록합니다. vLLM이 제공한 토큰 사용량만 수집하며 제공하지 않은 토큰 수나 비용을 임의 계산하지 않습니다. 모델 내부 추론 과정을 별도 Span으로 만들어 보이지 않습니다. 생성 중지·브라우저 연결 종료·모델 오류에서는 vLLM 스트림과 열린 관측 항목을 정리합니다. Langfuse 전송 장애는 답변 생성을 중단시키지 않습니다.

시연 질문과 모델 답변은 Langfuse에 저장될 수 있으므로 인증 토큰·API 키·비밀번호를 질문에 넣지 않습니다. 시스템의 인증 헤더·API 키·비밀번호는 관측 입력이나 프론트 응답으로 전달하지 않습니다.

## 회사 Nginx와 스트리밍 확인

회사에서 실행 중인 Nginx의 서버 블록·upstream·일반 `/api/` 경로·기존 모니터링 프록시를 유지합니다. 이번 프론트는 동일 출처 `/api/v1/chat/`을 사용하므로 **백엔드의 `API_V1_PREFIX=/api/v1`을 유지해야 합니다.** API 접두사 변경은 지원 범위에 포함하지 않으며 Nginx 경로만 변경해서는 동작하지 않습니다.

회사에서 토큰이 점진적으로 표시되는지 먼저 확인합니다. 필요한 경우 실제 Nginx 설정을 확인한 뒤 [채팅 전용 location 참고 예제](nginx-chat.conf.example)와 비교합니다. 이 예제는 기존 `/api/`나 다른 프록시를 대체하는 전체 설정이 아닙니다. 예제의 loopback 18000은 회사 upstream을 확인한 값이 아니므로 그대로 적용하지 않습니다. 컨테이너 Nginx의 `127.0.0.1`은 해당 컨테이너 자신입니다.

채팅 경로에 HTTP/1.1, 응답/요청 버퍼링 해제, 캐시·gzip 해제, 충분한 응답/전송 timeout이 필요한지 확인합니다. 별도 location을 추가해야 한다면 기존 API의 인증/접근 제어·프록시 헤더·upstream 연결 조건을 함께 유지해야 합니다. `/api/v1/chat/...` 전체 URI가 FastAPI에 전달되어야 하므로 `proxy_pass`의 URI 및 마지막 `/`에 따른 경로 변경도 검토합니다. 예제에서는 URI가 없는 upstream을 사용해 전체 경로를 보존합니다.

이번 작업에서는 회사 Nginx에 한국공항공사 `/grafana/`·`/langfuse/` 경로나 IP를 적용하지 않습니다. 실제 설정 변경과 구문 검사·reload는 변경 대상이 확인된 후 별도 수행합니다.

## 회사 실제 연결 테스트 준비

2026-10-15 현재 설정 상태: 사용자가 직접 입력하도록 로컬 `deploy/.env.backend`의 채팅 연결 주소·모델·키는 모두 비워 두었습니다. 사용자 요청으로 `DEMO_CHAT_ENABLED=true`, `LANGFUSE_TRACING_ENABLED=true`로 설정했으며 요청 제한 시간은 기본값 `120`초입니다. 실제 연결값이 없으면 모델 호출과 Trace 수집은 아직 사용할 수 없습니다. 기존 DB·인증·모니터링 값은 유지합니다. 회사 실제 연동은 값 입력 후 진행하며 지금은 추가 연결 요청이나 배포를 수행하지 않습니다.

| 항목 | 확인 상태 |
|---|---|
| SDK 수집 주소 | 빈 값. 사용할 회사/현장 주소를 사용자가 직접 입력 |
| 수집 활성화 | 로컬 `LANGFUSE_TRACING_ENABLED=true`. 주소와 두 실제 키를 입력하고 backend에 반영해야 수집 가능 |
| Langfuse health | 앞선 읽기 전용 `GET /api/public/health`에서 회사 서버의 HTTP 200, `status=OK`, 버전 `3.224.0` 확인. 현재 연결 설정이 채워졌다는 의미는 아님 |
| 프로젝트 키와 실제 수집 | 설명용 자리표시자는 저장하지 않음. 두 키는 빈 값이며 인증된 SDK 수집·Trace 저장/조회는 아직 검증하지 않음 |
| 회사 vLLM | API 루트·모델·키는 빈 값. 실제 값과 인증 필요 여부를 직접 확인해 입력 |
| 회사 배포 실행 환경 | 서버 접근 정보와 실행 중인 backend/Compose 위치 미확인. 운영 Nginx reload·컨테이너 재배포 미실행 |

health 성공은 서버 접근성과 버전 확인 결과입니다. 프로젝트 키 인증이나 사용자별 Trace 수집 성공을 의미하지 않습니다. 사용자가 환경파일에 실제 연결값을 입력한 뒤 아래 절차를 진행합니다.

1. 회사 웹 주소, 실행 중인 backend 서비스와 env 파일 위치, backend에서 접근 가능한 vLLM API 루트를 확인합니다. 실제 모델명은 `VLLM_MODEL` 또는 `/v1/models` 응답으로 확정합니다.
2. 회사 Langfuse의 SDK 수집 루트·프로젝트 키·서버 버전을 확인합니다. 브라우저 iframe URL은 별도로 유지하며 키를 문서나 채팅에 붙여 넣지 않습니다.
3. 회사 환경파일의 기존 DB·인증·대시보드 값을 보존하고 채팅 연결 키만 설정합니다. `DEMO_CHAT_ENABLED=true`, `LANGFUSE_TRACING_ENABLED=true`와 필요한 연결 값을 적용합니다.
4. 기존 배포 방식으로 새 기능을 반영한 후 회사 Nginx를 통한 스트리밍과 아래 A/B 시나리오를 확인합니다. 실행 중인 회사 Nginx를 KAC 예제로 교체하지 않습니다.
5. 모의 테스트와 실제 회사 수집 결과를 구분해 남깁니다. Langfuse에서 입력/출력·모델·사용자·세션·부모 관계·완료 상태를 직접 확인하기 전에는 실제 연결 성공으로 기록하지 않습니다.

백엔드 Dockerfile은 `requirements.txt`의 고정된 Langfuse SDK와 HTTP 클라이언트를 설치합니다. 이번 데모 계정용 백엔드 tar에는 해당 의존성이 포함되며 이미지 내부 버전도 확인했습니다. 전체 KAC 납품 묶음과 현장 Compose·프록시 적용은 [향후 패키징 체크리스트](kac-packaging-checklist.md) 범위로 남깁니다.

## 검증: 로컬 모의 응답과 회사 실제 연동 구분

로컬 테스트는 실제 vLLM/Langfuse에 접속하지 않는 모의 vLLM 스트림과 관측 수집기를 사용합니다. 이것으로 사용자·세션 소유권, Trace 부모 관계, 후속 문맥, 완료·오류·중지 시 정리, 수집 장애 시 채팅 지속 여부를 검사합니다. 실제 수집 서버의 저장/표시, 모델 응답 품질, 회사 Nginx의 청크 전달은 실제 회사 환경에서 확인해야 합니다.

2026-10-15 구현 시점의 로컬 모의 검증 기록(회사 실제 연동 결과 아님):

- 백엔드 `python -m compileall app`, `pytest`: 49개 테스트와 106개 subtest 통과. 신규 채팅 테스트는 24개입니다.
- 실제 `langfuse==5.2.0` SDK와 메모리 OTLP exporter로 A/B 사용자, 세션 재사용/변경, 질문별 Trace, 부모 관계, 시각, 실제 제공 usage, 오류·취소를 검사했습니다. 외부 Langfuse 서버에는 전송하지 않았습니다.
- 프론트 `npm run build`, `npm run lint`, Node 테스트 22개 통과. lint에는 기존 iframe 정리 코드의 경고 5개가 남아 있습니다.
- 임시 로컬 서버와 headless Chrome에서 모의 로그인 → 채팅 메뉴 → 스트리밍 2턴 → 생성 중지 → 모델 오류 → 새 대화 흐름을 검증했습니다. 같은 세션 유지/새 세션 발급을 확인했고 브라우저 런타임 오류는 없었습니다.
- 실제 환경파일 대신 임시 예제 값을 사용한 `docker compose config --quiet` 및 `git diff --check` 통과. 운영 환경파일과 DB 볼륨은 수정하지 않았습니다.
- 백엔드 이미지 빌드·반입, Nginx 실행 검사, 실제 vLLM/Langfuse 연동은 이번 로컬 검증에 포함되지 않았습니다.

공통 버전 정리 후에는 회사 `profile`과 현장 `kac`에서 기존 기능 구성을 유지하면서 채팅 인증·소유권·설정된 연결값 사용을 검증하는 회귀 테스트를 추가했습니다. 채팅·제품 프로필·KAC 관련 테스트 43개와 subtest 83개가 통과했습니다. 실제 연결값을 비워 두는 작업은 로컬 `.env.backend`의 새 채팅 항목에만 적용했으며 운영 서버 재시작이나 Nginx 변경은 수행하지 않았습니다.

| 회사 실제 연결 시나리오 | 확인 결과 |
|---|---|
| 기존 관리자 A/B 계정으로 각각 로그인 후 질문 | Langfuse의 Trace 이름은 `chat.request`, `user_id`는 각각 서버에서 인증한 내부 계정 ID; 브라우저 입력으로 결정되지 않음 |
| A의 첫 대화에서 두 번 질문 | 같은 `session_id` 아래 서로 다른 Trace 2개; 두 번째 답변은 첫 번째 완료 턴 문맥 포함 |
| A가 새 대화 후 질문 | `user_id` 유지, `session_id` 변경 |
| 각 Trace 열기 | 실제 이력 준비/프롬프트 단계 Span과 vLLM Generation이 같은 Trace의 루트에 연결 |
| B가 A의 세션으로 요청 | 해당 세션을 이용한 생성·중지 거부; 다른 사용자의 이력 노출·재사용 없음 |
| 답변 생성 중 중지·탭 닫기 | 스트림 정리, 취소 상태·종료 시각 기록; 중지 후 다음 질문 가능 |
| 모델 오류 또는 요청 시간 초과 | 오류 안내와 관측 오류 상태; 이어지는 새 요청 가능 |
| 수집 서버 일시 장애 | 채팅은 지속; 미수집 기록은 성공으로 보고하지 않음 |
| vLLM usage 제공 여부 확인 | 제공된 실제 토큰 값만 표시; 없으면 임의 수치 없음 |
| `DEMO_CHAT_ENABLED=false` 적용 | 새로고침 후 메뉴 비표시, 직접 채팅 경로·API 차단 |
| 기존 기능 회귀 확인 | 로그인, 기존 가입/승인 경로의 활성·비활성 상태, 회사에서 활성화된 모니터링 화면과 기존 프록시 유지 |
| backend 재생성 후 Langfuse 조회 | 메모리 대화는 소실, 이미 전송된 Trace는 계속 조회 가능 |

회사 실제 테스트에서는 vLLM `/v1/models`의 실제 ID, SDK 호환 Langfuse 버전, 키의 프로젝트 일치, backend 컨테이너에서 두 연결 주소 접근 가능 여부, Nginx 응답 버퍼링 해제, 서버 시계 동기화를 함께 확인합니다. 실제 연동 전에는 모의 테스트 결과만 검증 완료로 보고합니다.

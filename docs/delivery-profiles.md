# HPC / LLM 납품 설정

현재 기본 납품은 `PRODUCT_PROFILE=llm`, 제품명은 **T-LLM Observability**다.
코드 주석이나 제품별 브랜치 없이 백엔드 환경 설정으로 제품을 선택한다.
프론트 빌드는 사용자가 진행한다. 이번 작업은 배포 실행, 이미지 생성, Helm 또는 폐쇄망 패키징을 포함하지 않는다.

## 기능 인벤토리와 납품 구성

관제 화면은 `frontend/src/pages/sub_pages/`의 iframe 컴포넌트다.
경로·메뉴 순서·컴포넌트는 `frontend/src/config/monitoring.tsx`, 활성 기능과 제품명은
`backend/app/core/product.py`에 정의한다. 아래 경로는 `/ops/` 기준이다.

| 기능 키 | 경로 / 화면 파일 | 백엔드 환경변수 | HPC | LLM |
|---|---|---|---|---|
| hpc_dashboard | dashboard / Dashboard.tsx | OVERVIEW_URL | 미완성, 비활성 | 비활성 |
| kubernetes | k8s / k8s.tsx | K8S_URL | 활성 | 활성 |
| gpu | gpu / GPU.tsx | GPU_URL | 활성 | 활성 |
| server | server / Node.tsx | NODE_URL | 활성 | 활성 |
| job | job / Job.tsx | JOB_URL | 활성 | 비활성 |
| power | power / Power.tsx | POWER_URL | 활성 | 비활성 |
| network | network / Snmp.tsx | SNMP_URL | 활성 | 활성 |
| vllm | vllm / vLLM.tsx | VLLM_URL | 비활성 | 활성 |
| vllm_observability | vllm-observability / VllmObservability.tsx | VLLM_OBSERVABILITY_URL | 비활성 | 활성 |
| trace | trace / Trace.tsx | TRACE_URL | 비활성 | 활성 |
| user_trace | user-trace / UserTrace.tsx | USER_TRACE_URL | 비활성 | 활성 |

- HPC: TSlurm Insight, 첫 화면 `/ops/k8s`. 메뉴 Kubernetes → GPU → Server → Job → Power → Network.
- LLM: T-LLM Observability, 첫 화면 `/ops/vllm`. LLM 그룹(Dashboard, Observability, Time Trace, User Trace) → Kubernetes → GPU → Server → Network.
- 가입·인증·승인·알림은 기존 동작 유지. `/register`, `/api/v1/auth/*`, `/api/v1/users*`가 근거다.
- 자원 예약은 두 프로필에서 기존 동작 유지. `RESOURCE_RESERVATIONS_ENABLED=false`로 비활성화하면 사용자 메뉴, `/ops/resource-reservations`, `/api/admin/resource/*`, `/api/external/td/resource-reservation-requests`를 차단한다. 관리자 라우터와 TD 외부 라우터에 같은 기능 guard를 적용했다. Slurm 연동은 `backend/app/services/slurm_service.py`에 있다.
- 터미널은 두 프로필에서 기존 직접 경로 및 stub 동작 유지, 사이드 메뉴는 기존대로 숨김. `TERMINAL_ENABLED=false`로 화면과 `/api/v1/terminals/targets`, `/api/v1/ws/term/{target_key}`를 차단한다. 실제 SSH 터미널 구현은 이번 범위가 아니다.
- 사용자 승인 시 기존 LSC SSH 동기화 코드가 존재한다(`backend/app/api/v1/endpoints/users.py`, `services/lsc_sync.py`). 제품 프로필로 변경하지 않는다. 납품 환경에서 기존 `LSC_SYNC_*` 설정을 별도로 확인한다.
- DB는 `insight_admin`과 `desk_users`; 초기 SQL은 `deploy/mariadb/init/01-init.sql`, 애플리케이션 모델은 `backend/app/models/`에 있다. DB 스키마 변경 없음.
- 배포 근거: `deploy/docker-compose.yml`의 `backend`, `mariadb`, `backend/Dockerfile`. 관제 수집기·LLM 추론 서버·외부 대시보드 배포 정의나 Helm chart는 확인되지 않았다. 별도 Log/APM/Report 화면도 확인되지 않았으며 Trace를 임의로 해당 제품으로 분류하지 않았다.

## 적용 방법

1. 새 백엔드 코드를 배포한다. 기존 이미지에는 새 config API가 없으므로 **프론트만 업데이트하면 안 된다**.
2. 로컬 실행은 `backend/.env`, Compose 실행은 `deploy/.env.backend`에 설정한다.

   ```dotenv
   PRODUCT_PROFILE=llm
   RESOURCE_RESERVATIONS_ENABLED=true
   TERMINAL_ENABLED=true
   ```

3. 같은 파일에 위 표의 관제 URL을 설정한다. 현재 작업 환경은 기존 `frontend/.env`의 관제 URL을 두 백엔드 env 파일로 복사해 두었다. 이 env 파일들은 Git 추적 대상이 아니므로 다른 서버에는 별도로 전달해야 한다. 민감한 값은 문서나 커밋에 넣지 않는다.
4. 사용자가 프론트를 빌드하고 배포한다. API는 기본적으로 같은 origin의 `/api` 프록시를 사용한다. `VITE_API_BASE_URL` / `VITE_WS_BASE_URL`은 기존 연결 방식대로 빌드 설정에 남아 있다.
5. 백엔드 환경변수 변경을 적용한다. Compose의 `env_file` 변경은 단순 restart로 반영되지 않으므로 컨테이너를 재생성해야 한다. 현재 로컬 Compose 빌드 방식의 예시는 아래와 같다(이번 작업에서 실행하지 않음).

   ```bash
   cd deploy
   docker compose up -d --build --force-recreate backend
   ```

   폐쇄망에서는 별도 환경에서 빌드한 공통 이미지를 반입하고 해당 이미지로 재생성한다. 기존 Dockerfile은 apt/pip 네트워크 접근이 필요하므로 폐쇄망에서 직접 빌드하는 방식은 납품 절차로 확정하지 않는다.

6. 브라우저를 새로고침한다. 이미 열린 세션은 설정을 다시 읽도록 새로고침해야 한다.

이후 HPC 납품은 `PRODUCT_PROFILE=hpc`와 고객사 URL을 설정하고 백엔드를 재시작/재생성하면 된다. 프론트의 API 연결 주소가 같다면 프론트 재빌드는 필요 없다. 지원하지 않는 프로필 값은 서버 설정 검증에서 실패한다.

## 설정 API와 차단 동작

- `GET /api/v1/config/product`: 인증 전 제품명·축약명·첫 화면·기능 이름만 공개. 관제 URL과 DB/인증 정보는 포함하지 않는다.
- `GET /api/v1/config/frontend`: 활성 관리자 인증 후 위 정보와 활성 관제 URL·터미널 목록 제공. 기존 dashboards/terminals 필드는 유지하고 제품 필드를 추가했다.
- 설정 로딩 실패 시 재시도 화면을 표시한다. 임의 프로필이나 과거 VITE 관제 URL로 되돌아가지 않는다.
- 비활성 화면은 직접 URL을 입력해도 iframe을 마운트하지 않고 403 안내를 표시한다. 클라이언트 화면 차단은 외부 대시보드 자체의 인증을 대체하지 않는다.
- 비활성 기능의 관제 URL은 config API에서 null로 반환한다. 외부 iframe 서비스의 직접 접근은 해당 서비스/프록시에서 별도로 통제해야 한다.
- URL이 누락된 활성 화면은 주소 미설정 안내를 표시한다.
- `frontend/.env`의 관제 `VITE_*_URL`은 이전 설정 참고용이며 더 이상 화면에서 읽지 않는다.

## 검증

프론트 빌드 없이:

```bash
cd frontend
npm run lint
./node_modules/.bin/tsc --noEmit -p tsconfig.app.json
```

백엔드(테스트 도구 httpx 필요):

```bash
cd backend
.venv/bin/python -m compileall -q app
.venv/bin/python -m unittest discover -s tests -v
```

`tests/test_product_profiles.py`는 실제 DB·외부 서버를 호출하지 않고 두 프로필, 비활성 URL 제외, 인증, 예약 API 전체 및 터미널 HTTP/WS 차단을 검사한다. pytest가 있는 환경에서는 동일 파일을 pytest로 실행해도 된다.

수동 납품 확인: 두 프로필의 제품명/메뉴/첫 화면, 비활성 경로 직접 접근, 활성 iframe 연결, `/register`와 기존 가입 승인 흐름을 확인한다. 실제 외부 관제 연결과 운영 환경의 로그인은 별도 검증이 필요하다.

후속 TODO: 운영 부가 기능 포함 정책 확정, 단일 Helm values 설계, 폐쇄망 패키지 manifest 및 설치 절차. 라이선스·Helm·납품 패키징은 아직 구현하지 않는다.

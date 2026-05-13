# AGENTS.md

## 목적
이 저장소는 **TSlurm Insight 관제 시스템**입니다. 앞으로 여러 납품 edition을 만들 수 있도록, Codex가 작업할 때 따라야 할 공통 지침을 정의합니다.

`basic`, `snmp-only`, `k8s-only`, `snmp-k8s`, `full` 같은 이름은 현재 단계의 예시일 뿐입니다. 최종 edition 이름과 구성은 레포 전체 기능 인벤토리 조사 후 확정합니다.

아직 실제 납품 패키징 구현은 시작하지 않습니다. 구조 변경은 작은 diff로 단계적으로 진행하고, API/DB/배포/화면 흐름에 영향이 있는 변경 전에는 반드시 계획을 먼저 설명합니다.

## 현재 레포 구조 요약
- `frontend/`: React + Vite + TypeScript + Ant Design 기반 관리자 UI입니다.
  - `/login`, `/register`, `/ops/*` 라우팅을 가집니다.
  - 현재 확인되는 Dashboard, Node, Job, GPU, Power, Kubernetes, SNMP 화면은 `VITE_*_URL` 기반 iframe 페이지입니다.
  - 위 화면 목록은 현재 파일에서 확인되는 후보이며, 전체 기능 목록으로 확정하지 않습니다.
  - 메뉴는 `frontend/src/pages/Layout.tsx`, 라우팅은 `frontend/src/App.tsx`가 중심입니다.
- `backend/`: FastAPI + SQLAlchemy 기반 API 서버입니다.
  - 관리자 인증, Desk 가입신청, 사용자 승인, frontend config, health, terminal stub API가 있습니다.
  - 관리자 DB(`insight_admin`)와 Desk 사용자 DB(`desk_users`)를 분리합니다.
  - 비밀번호는 해시로 저장해야 하며 평문 저장/로그/응답을 금지합니다.
- `deploy/`: 현재 Docker Compose, MariaDB init SQL, 백엔드 이미지 tar 등 운영/납품 관련 파일이 있습니다.
  - 현재 Kubernetes Helm chart 구조는 아직 없습니다.
  - 폐쇄망 납품 패키지 구조는 아직 목표 상태로만 취급합니다.
- `docs/`: 사이트/iframe 구조 분석 문서가 있습니다.

## Edition 전략 원칙
1. **기능 전수조사를 먼저 한다.**
   - 납품 edition을 정의하기 전에 반드시 레포 전체에서 관제 기능/모듈 후보를 전수조사한다.
   - 조사 대상은 frontend route/menu, iframe URL, `VITE_*` 환경변수, backend router/API, deploy service, Dockerfile, compose service, DB init SQL, docs 문서이다.
   - SNMP, Kubernetes, Log, APM, Report는 예시일 뿐이며, 실제 기능 목록은 코드와 배포 파일에서 발견한 근거를 기준으로 작성한다.
   - 근거 없이 기능을 제외하거나 포함하지 않는다.
   - 기능 후보별로 발견 근거(파일 경로, route/API/env/service 이름)를 기록한 뒤 edition 구성을 논의한다.

2. **납품 edition별로 브랜치를 나누지 않는다.**
   - `basic`, `snmp-only`, `k8s-only`, `snmp-k8s`, `full` 같은 edition 이름은 예시이며, 최종 이름은 기능 인벤토리 조사 후 확정한다.
   - edition은 코드 브랜치가 아니라 설정, values, license/config, 패키지 manifest로 구분한다.
   - edition별 hotfix가 생기지 않도록 공통 코드 경로를 유지한다.

3. **공통 이미지는 동일하게 빌드한다.**
   - frontend/backend/exporter/agent 등 이미지는 edition별로 따로 빌드하지 않는 방향을 기본값으로 삼는다.
   - 납품 패키지에서 필요한 컴포넌트만 선택하고, 런타임 설정으로 기능을 켜고 끈다.

4. **Kubernetes 배포는 Helm chart 하나를 유지한다.**
   - chart를 edition별로 복제하지 않는다.
   - `values.yaml`, `values-<edition>.yaml` 같은 values 조합으로 `enabled/disabled`를 제어한다.
   - chart가 아직 없으므로, 도입 시 먼저 디렉터리 구조와 values schema 계획을 제안한다.

5. **기능은 feature flag 또는 license/config로 제어한다.**
   - 기능 전수조사로 확인된 관제 기능/모듈은 UI 라우트, 메뉴, 백엔드 API, 배포 컴포넌트가 같은 feature key를 기준으로 동작해야 한다.
   - 예시 feature key는 `snmp`, `kubernetes`, `log`, `apm`, `report`처럼 둘 수 있지만, 실제 key는 코드/문서/deploy 근거를 확인한 뒤 정한다.
   - config와 license의 최종 책임 범위가 확실하지 않으면 대규모 구현 대신 TODO 또는 설계 제안으로 남긴다.

6. **UI 메뉴만 숨기는 것으로 끝내지 않는다.**
   - edition에서 비활성화된 기능은 프론트 메뉴/라우트뿐 아니라 백엔드 API 접근도 막아야 한다.
   - 백엔드에서는 dependency, middleware, router guard, service-level check 중 기존 구조에 맞는 방식을 선택한다.
   - 권한/feature 차단 실패는 보안 이슈로 취급한다.

7. **폐쇄망 납품 패키지를 고려한다.**
   - 목표 패키지 구성은 Docker image tar, Helm chart, edition values, install script, README/checklist를 한 묶음으로 제공하는 것이다.
   - 외부 registry, public package registry, 인터넷 접근이 없는 환경을 전제로 검증 방법을 설계한다.
   - 아직 구현하지 않은 패키징 구조는 `TODO`나 제안 문서로 먼저 남긴다.

## 작업 원칙
1. **구현 전 계획 우선**
   - API 계약, DB 스키마, Helm values, Docker image, 인증/인가 흐름, 주요 UI 흐름에 영향을 주는 변경은 작업 전에 범위/단계/영향/검증 계획을 공유한다.

2. **Small Diff 우선**
   - 한 번에 edition 체계를 전부 만들지 않는다.
   - 예: feature key 정의 -> backend guard -> frontend menu/route guard -> values 설계 -> packaging script 순서처럼 검증 가능한 단위로 나눈다.

3. **기존 동작 보존**
   - Desk 로그인 페이지 하단 가입신청 버튼 및 `/register` 공개 신청 흐름을 edition 작업 중 깨뜨리지 않는다.
   - OpenLDAP 자동 프로비저닝/동기화는 별도 요구가 없는 한 구현하지 않는다.
   - 현재 가입신청 승인은 관리자 수동 등록/처리 흐름을 전제로 한다.

4. **추측 기반 대규모 변경 금지**
   - 실제 운영 요구, license 포맷, Helm chart 배치, image naming, 폐쇄망 설치 방식이 확실하지 않으면 코드부터 크게 바꾸지 않는다.
   - 불확실한 부분은 `TODO`, 문서 제안, 작은 spike 형태로 남긴다.

5. **보안 기본값 유지**
   - 비밀번호와 민감정보는 저장/로그/응답/화면 표시에서 평문 금지.
   - edition 비활성 기능은 직접 URL/API 호출도 차단.
   - frontend 환경변수는 브라우저에 노출될 수 있음을 전제로 설계.

## Edition 모델 예시
아래는 구현 확정안이 아니라 대화에서 나온 예시입니다. 최종 edition 이름과 활성 기능은 기능 전수조사 결과를 근거로 다시 작성합니다.

| Edition | 활성 기능 예시 |
|---|---|
| `basic` | Dashboard, Node, Job, GPU, Power, 사용자/관리자 기본 기능 |
| `snmp-only` | basic + SNMP |
| `k8s-only` | basic + Kubernetes |
| `snmp-k8s` | basic + SNMP + Kubernetes |
| `full` | basic + SNMP + Kubernetes + Log + APM + Report |

SNMP와 Kubernetes도 단순 예시 기능으로 취급합니다. Log, APM, Report를 포함한 모든 기능 후보는 코드, 문서, 배포 파일의 근거를 찾아 존재 여부와 edition 포함 여부를 판단합니다.

## 검증 명령어
변경 후 가능한 범위에서 실행하고 결과를 요약합니다.

### Frontend
```bash
cd frontend
npm run lint
npm run build
```

### Backend
```bash
cd backend
python -m compileall app
pytest
```

테스트가 없거나 의존성이 없는 환경이면 실행 실패 이유를 요약하고, 대신 수행한 정적 확인 또는 파일 검토 결과를 남깁니다.

### Deploy
```bash
cd deploy
docker compose config
```

Helm chart가 추가된 이후에는 다음 검증을 우선 고려합니다.

```bash
helm lint <chart-path>
helm template <release-name> <chart-path> -f <values-file>
```

## 다음 작업 시 우선 제안할 순서
1. 레포 전체에서 기능 후보를 전수조사하고, 파일/route/API/env/service 근거와 함께 inventory 문서를 만든다.
2. inventory를 기준으로 edition 이름, feature key, 포함/제외 기준을 확정한다.
3. backend config/license 모델과 feature guard 위치를 설계한다.
4. frontend 메뉴/라우트가 backend feature config를 소비하도록 설계한다.
5. 단일 Helm chart 디렉터리와 values schema 초안을 만든다.
6. 폐쇄망 납품 패키지 manifest와 install script 요구사항을 문서화한다.
7. 각 단계를 작은 diff로 구현하고 검증 결과를 공유한다.

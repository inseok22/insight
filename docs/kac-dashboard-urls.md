# 한국공항공사 대시보드 설정

한국공항공사 구성(`MONITORING_SCOPE=kac`)은 다음 세 메뉴만 표시합니다.

| 메뉴 | 화면 | 설정 |
|---|---|---|
| LLM → Dashboard | 서비스별 탭, 선택한 서비스의 Grafana 화면 | `VLLM_URL` 서비스 목록 |
| GPU | 여러 서버/GPU를 보는 단일 Grafana 화면 | `GPU_URL` 전체 URL 1개 |
| Server | 여러 서버를 보는 단일 Grafana 화면 | `NODE_URL` 전체 URL 1개 |

서버/GPU 선택은 Grafana 내부에서 처리합니다. Insight에는 서버 1·2·3 메뉴나 GPU 0~7 탭을 만들지 않습니다.
LLM 탭은 등록 순서대로 표시하며 개수 제한이 없습니다. 한 줄의 가용 너비를 초과하면 **더보기(⋯)** 메뉴가
나타납니다. 기준은 10개 같은 고정 개수가 아니라 화면 너비와 서비스명 길이입니다.
더보기에서 선택한 탭은 보이는 영역으로 이동하며, 선택한 서비스의 iframe 하나만 로드합니다.

## 수정 위치와 반영

- Compose 배포: `deploy/.env.backend`
- 로컬 백엔드 실행: `backend/.env`
- 주석 포함 입력 템플릿: [kac-dashboard-urls.env.example](kac-dashboard-urls.env.example)

각 파일의 **한국공항공사: 아래 세 URL 설정을 현장에서 수정** 주석 아래를 수정합니다.
DB/로그인 설정이 있으므로 env 파일 전체를 템플릿으로 덮어쓰지 않습니다.
`MONITORING_SCOPE`, `GPU_URL`, `NODE_URL`, `VLLM_URL`은 각각 한 번만 선언합니다.
이전 `DASHBOARD_SERVERS`는 삭제하며 더 이상 읽지 않습니다.

이번 구조 변경을 적용할 때 프론트와 백엔드를 함께 새로 빌드·배포합니다.
이후 서비스 이름/URL/목록 변경은 폐쇄망에서도 프론트 재빌드 없이 가능합니다.
이름이나 주소를 입력하는 관리 UI는 없으며, env 수정 후 백엔드 설정 반영과 브라우저 새로고침이 필요합니다.

로컬 실행은 백엔드 프로세스를 재시작합니다. Compose에서는 반입한 이미지가 로드된 상태에서 실행합니다.

```bash
cd deploy
docker compose up -d --no-deps --no-build --pull never --force-recreate backend
```

`docker compose restart`만으로는 변경한 env_file 값이 반영되지 않으므로 컨테이너를 재생성합니다.

## 입력 예시

아래 주소는 설명용입니다. Grafana에서 복사한 현장 대시보드 전체 URL로 바꿉니다.
Prometheus 주소는 Grafana의 데이터 소스에 설정하며 아래 URL에 넣지 않습니다.

```dotenv
MONITORING_SCOPE=kac

# GPU 통합 Grafana 대시보드 전체 URL
GPU_URL='https://grafana.example.test/d/gpu?orgId=1&kiosk=true'

# Server 통합 Grafana 대시보드 전체 URL
NODE_URL='https://grafana.example.test/d/server?orgId=1&kiosk=true'

# LLM 서비스별 Grafana 대시보드 URL
VLLM_URL='[
  {
    "id": "airport-guide",
    "name": "공항 안내 LLM",
    "url": "https://grafana.example.test/d/airport-guide?orgId=1&kiosk=true"
  },
  {
    "id": "document-search",
    "name": "문서 검색 LLM",
    "url": "https://grafana.example.test/d/document-search?orgId=1&kiosk=true"
  }
]'
```

- **LLM 이름 변경:** `name`만 바꿉니다. 예: `공항 안내 LLM` → `고객 응대 LLM`.
- **LLM 추가/삭제:** 목록에 객체를 추가/삭제합니다. 서비스 12개, 20개도 같은 형식입니다.
- **LLM 주소 변경:** 해당 객체의 `url`을 수정합니다. 같은 Grafana 대시보드라도 서비스 필터가 다른 전체 URL을 사용할 수 있습니다.
- **ID 유지:** 목록 내에서 고유한 `id`를 사용합니다. 이름만 바꿀 때 ID를 유지하면 기존 탭 링크도 유지됩니다.
- **주소 미정:** `"url": ""`이면 이름/탭만 등록하고 주소 미설정 안내를 표시합니다.
- **서비스 미등록:** `VLLM_URL='[]'`이면 LLM 미등록 안내를 표시합니다.
- **GPU/Server 주소 미정:** 빈 값이면 주소 미설정 안내를 표시합니다. 이 두 키에는 JSON 배열을 넣지 않습니다.

LLM JSON의 시작/끝 작은따옴표는 유지합니다. JSON 내부에는 `#` 주석이나 마지막 쉼표를 넣지 않습니다.
표시명에 작은따옴표가 필요하면 JSON 유니코드 이스케이프 `\u0027`을 사용합니다.
URL은 HTTP(S) 절대주소이며 사용자명/비밀번호를 포함할 수 없습니다. 비밀 토큰도 넣지 않습니다.
Grafana 변수명과 값은 실제 대시보드에 맞춥니다. 서비스 이름은 Grafana의 모델/서버 이름을 변경하지 않습니다.

## API와 기존 구성

인증된 `GET /api/v1/config/frontend`는 `dashboard_layout=services`를 반환합니다.
GPU/Server는 `dashboards.gpu_url`, `dashboards.node_url`에서,
LLM 목록은 `dashboard_targets.vllm_url`에서 읽습니다. 서버별 `dashboard_groups`는 제거했습니다.
공개 `/config/product`에는 이름/주소/서비스 목록을 노출하지 않습니다.

LLM 선택은 `target` 쿼리에 저장되어 새로고침/직접 링크에서도 유지됩니다.
존재하지 않거나 삭제한 서비스의 ID는 첫 서비스로 돌아갑니다. 예전 `server` 쿼리는 서버 선택에 사용하지 않고,
탭을 변경할 때 제거합니다. Insight의 쿼리를 Grafana URL에 자동으로 덧붙이지 않습니다.

기존 EICN(`MONITORING_SCOPE=profile`)과 1대용 도구(`gpu_llm`)의 메뉴/설정 형식은 유지합니다.
`delivery/offline` 도구는 `gpu_llm`용 설정을 생성하므로 한국공항공사 구성에 그대로 사용하지 않습니다.

한국공항공사는 기존 `vllm`, `gpu`, `server` feature key를 사용합니다.
Observability, Time Trace, User Trace, HPC Dashboard, Kubernetes, Network, Job, Power, 예약 및 터미널은
메뉴/직접 경로/관련 API/WebSocket에서 계속 차단합니다. 가입신청/승인/알림 비활성화와 관리자 로그인은 유지합니다.

## 검증

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

실제 Grafana 연결, iframe 로그인/표시 허용, Grafana 내부 서버/GPU/서비스 필터는 현장 설정 후 확인합니다.
Insight URL 설정만으로 Grafana/Prometheus 설치나 데이터 수집 설정이 만들어지지는 않습니다.
운영용 더미 JSON/가상 예약 처리는 제거된 상태를 유지하며 테스트의 mock은 유지합니다.

### 2026-10-07 로컬 확인 결과

- 프론트 lint/build, 메뉴·렌더링 테스트 12개 통과. 기존 effect 경고 5개와 번들 크기 경고는 남아 있습니다.
- 백엔드 compileall, unittest 22개 통과. pytest는 가상환경에 설치되지 않아 실행하지 못했습니다.
- Compose 설정 검증 통과. 이번 설정과 무관한 기존 URL의 `__all` 보간 경고는 남아 있습니다.
- 실제 컴포넌트를 임시 테스트 서버에서 확인: 12번째 LLM 선택/단일 iframe/이전 server 쿼리 제거 정상.
- 서비스 3개로 너비를 변경해 더보기 숨김/표시 전환 확인. GPU와 Server는 각각 iframe 1개, 탭 0개 확인.
- 내장 브라우저의 MutationObserver 진단 로그는 앱 스크립트가 없는 정적 iframe 페이지에서도 재현되어 구분했습니다.
- 실제 env 두 파일과 예제 파일 로딩 확인. DB/인증 등 다른 설정값은 보존했으며 관제 URL은 미설정 상태입니다.
- 운영 소스와 프론트 빌드에 mocks/dummy 자산이 없는 것을 확인했습니다. 테스트 데이터는 임시 폴더에만 사용했습니다.
- 운영 컨테이너 재생성, 백엔드 Docker 이미지 빌드, 현장 Grafana 연결 및 배포는 수행하지 않았습니다.

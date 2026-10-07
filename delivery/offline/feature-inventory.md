# 이번 반입 범위의 저장소 기능 조사

2026-09-30 작업 트리 기준. 기존 미커밋 EICN 변경을 포함하며 실제 운영 서버와 같다는 의미는 아닙니다.
공통 근거: `frontend/src/config/monitoring.tsx`, `frontend/src/App.tsx`, `frontend/src/pages/Layout.tsx`,
`backend/app/core/product.py`, `backend/app/api/v1/endpoints/config.py`.

| 기능 키 | /ops 하위 경로 / 페이지 파일 | URL 설정 | 이번 범위 |
|---|---|---|---|
| gpu | gpu / GPU.tsx | GPU_URL | 포함: DCGM 1대, 8장 |
| vllm | vllm / vLLM.tsx | VLLM_URL | 포함: LLM Dashboard |
| server | server / Node.tsx | NODE_URL | 제외: 사용자 요청 범위 밖 |
| vllm_observability | vllm-observability / VllmObservability.tsx | VLLM_OBSERVABILITY_URL | 제외 |
| trace | trace / Trace.tsx | TRACE_URL | 제외 |
| user_trace | user-trace / UserTrace.tsx | USER_TRACE_URL | 제외 |
| hpc_dashboard | dashboard / Dashboard.tsx | OVERVIEW_URL | 기존 미완성/비활성 |
| kubernetes | k8s / k8s.tsx | K8S_URL | 제외 |
| network | network / Snmp.tsx | SNMP_URL | 제외 |
| job | job / Job.tsx | JOB_URL | 제외 |
| power | power / Power.tsx | POWER_URL | 제외 |

`frontend/.env`의 `VITE_*_URL`은 과거 설정이며 현재 관제 화면은 backend config를 읽습니다.
`VITE_API_BASE_URL`, `VITE_WS_BASE_URL`은 빌드 설정으로 남아 있으므로 폐쇄망 웹 이미지는 동일 origin을 사용하도록 빈 값으로 빌드합니다.
예약 화면의 더미 JSON 및 가상 처리는 제거되었습니다. 예약 화면은 실제 백엔드 API만 사용하며 이번 구성에서는 비활성입니다.

| API/지원 기능 | 근거 | 이번 범위 |
|---|---|---|
| 관리자 로그인/토큰/me | backend/app/api/v1/endpoints/auth.py | 포함 |
| 공개 가입신청, 사용자 승인 | auth.py, users.py, api/router.py, App.tsx | 현재 작업 트리에서 등록 해제 상태, 이번 변경 없음 |
| 제품/인증된 URL 설정 | endpoints/config.py | 포함, 두 feature만 공개 |
| health | endpoints/health.py | 포함 |
| 터미널 HTTP/WS stub | endpoints/terminals.py, services/terminal_service.py | 차단 |
| 자원예약 조회/승인/거절/재시도 | api/admin/resource.py | 기존 feature guard로 차단 |
| Desk 외부 예약 신청 | api/external/td.py | 기존 feature guard로 차단 |
| LSC SSH 동기화 | services/lsc_sync.py, endpoints/users.py | 비활성, 자동 LDAP 프로비저닝 추가 없음 |
| Slurm 연계 | services/slurm_service.py | 비활성 |

기존 배포 파일 `deploy/docker-compose.yml`에는 backend/mariadb만 있습니다. 해당 디렉터리 전체는 기존 `.gitignore`에서 제외됩니다.
`deploy/mariadb/init/01-init.sql`은 insight_admin/desk_users DB와 DB 사용자 초기화입니다. 비밀값은 새 패키지로 복사하지 않습니다.
`backend/Dockerfile`은 apt/pip 네트워크 빌드를 사용합니다. 기존 backend tar 3개는 버전/내용을 보증할 수 없어 재사용하지 않습니다.
기존 frontend Dockerfile, Prometheus/Grafana/DCGM 배포, Helm chart, 실제 dashboard JSON은 발견되지 않았습니다.
README/ONBOARDING의 VITE URL 설명 일부는 현재 config 구현 이전 내용입니다. `docs/delivery-profiles.md`, `docs/eicn-dashboard-urls.md`도 검토했습니다.
독립 Log/APM/Report 모듈 근거는 발견되지 않았습니다. Trace를 임의로 해당 기능으로 분류하지 않습니다.

이번 `delivery/offline/`은 사용자 요청에 따라 추가하는 Docker Compose 반입 경로입니다.
새 edition 이름이나 edition별 이미지/브랜치, Helm chart는 만들지 않습니다.
최종 활성 기능은 기존 `gpu`, `vllm` 키이며 `MONITORING_SCOPE=gpu_llm`으로 제어합니다.

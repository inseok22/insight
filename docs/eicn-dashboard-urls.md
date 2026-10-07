# EICN 대시보드 URL 입력 안내

기존 목록과 추가된 Gemma4를 포함해 총 14개 Grafana 대시보드 주소를 입력합니다.
템플릿: `docs/eicn-dashboard-urls.env.example`.
템플릿의 주소는 실제 주소가 아닌 자리표시자입니다. Grafana에서 각 대시보드를 열고
해당 서버·GPU·모델이 선택된 전체 URL(필요한 쿼리 파라미터 포함)로 교체하세요.

| 설정 키 | 고정 ID | Grafana 대시보드 이름 | 화면 위치 |
|---|---|---|---|
| VLLM_URL | bmt-vllm-base | vLLM - bmt-vllm-base | LLM → Dashboard → bmt-vllm-base 탭 |
| VLLM_URL | bmt-vllm-ft | vLLM - bmt-vllm-ft | LLM → Dashboard → bmt-vllm-ft 탭 |
| VLLM_URL | sllm-service-gemma4 | vLLM - eicn-rag-llm-gemma4 (URL 기준) | LLM → Dashboard → eicn-rag-llm-gemma4 탭 |
| GPU_URL | ai-dev-gpu0 | DCGM - ai-dev - GPU 0 | GPU → ai-dev → GPU 0 탭 |
| GPU_URL | ai-dev-gpu1 | DCGM - ai-dev - GPU 1 | GPU → ai-dev → GPU 1 탭 |
| GPU_URL | sllm-service-gpu0 | DCGM - sLLM-SERVICE - GPU 0 | GPU → sLLM-SERVICE → GPU 0 탭 |
| GPU_URL | sllm-service-gpu1 | DCGM - sLLM-SERVICE - GPU 1 | GPU → sLLM-SERVICE → GPU 1 탭 |
| GPU_URL | ta-eicn-gpu0 | DCGM - ta.eicn.co.kr - GPU 0 | GPU → ta.eicn.co.kr → GPU 0 탭 |
| GPU_URL | ta-eicn-gpu1 | DCGM - ta.eicn.co.kr - GPU 1 | GPU → ta.eicn.co.kr → GPU 1 탭 |
| GPU_URL | ta-eicn-gpu2 | DCGM - ta.eicn.co.kr - GPU 2 | GPU → ta.eicn.co.kr → GPU 2 탭 |
| NODE_URL | ai-dev | Node - ai-dev | Server → ai-dev |
| NODE_URL | direct-project-1 | Node - DIRECT-PROJECT-1 | Server → DIRECT-PROJECT-1 |
| NODE_URL | sllm-service | Node - sLLM-SERVICE | Server → sLLM-SERVICE |
| NODE_URL | ta-eicn | Node - ta.eicn.co.kr | Server → ta.eicn.co.kr |

## 입력 및 적용

1. 템플릿에서 14개 `url`만 실제 주소로 교체합니다. `id`는 메뉴·탭 연결 기준이므로 유지합니다.
2. Compose 실행은 `deploy/.env.backend`, 로컬 실행은 `backend/.env`에
   `GPU_URL`, `NODE_URL`, `VLLM_URL` 세 줄을 덮어씁니다. 같은 키를 중복 추가하지 않습니다.
   템플릿은 URL 세 줄만 제공하므로 DB·인증 등을 포함한 기존 env 파일 전체를 교체하지 않습니다.
3. 이 변경이 포함된 프론트는 최초 한 번 빌드·배포해야 합니다.
   이후 URL만 바꾸면 프론트 재빌드는 필요 없습니다.
4. 로컬은 백엔드를 재시작합니다. Compose는 env_file 변경을 반영하도록 재생성합니다.

   ```bash
   cd deploy
   docker compose up -d --no-deps --force-recreate backend
   ```

5. 브라우저를 새로고침합니다. 새 탭을 추가한 경우 프론트도 새로 빌드·배포해야 합니다.

## 선택 동작

- 왼쪽 GPU 서버 선택 후 상단에서 GPU 번호를 전환합니다. Server는 왼쪽 서버 선택만 제공합니다.
- LLM Dashboard는 상단에서 세 모델을 전환합니다. 다른 LLM 메뉴는 기존대로 유지합니다.
- 선택값은 주소의 `server`, `target` 쿼리에 저장되어 새로고침·뒤로 가기·링크 공유 시 복원됩니다.
  예: `/ops/gpu?server=ta-eicn&target=ta-eicn-gpu2`.
- 서버 진입 시 첫 GPU, 기본 페이지 진입 시 첫 서버/모델을 선택합니다.
  잘못된 선택값은 첫 유효 항목으로 표시합니다.
- URL 미설정 항목은 안내만 표시하고 iframe 요청을 보내지 않습니다.
- GPU·Server·LLM Dashboard는 고정 ID 목록에 있는 3개 GPU 서버, 4개 Server, 3개 LLM 탭만 표시합니다.
  기존 단일 URL이나 임의 ID는 추가 메뉴·탭으로 표시하지 않습니다.
  Observability·Time Trace·User Trace는 기존 메뉴와 URL을 유지합니다.
- 고정 항목 표시명·순서는 `frontend/src/config/dashboardNavigation.ts`의 EICN 목록을 따릅니다.
  URL은 기존 인증된 config API의 `{id, name, url}` 형식을 그대로 사용합니다.
- 외부 Grafana 로그인 및 iframe 허용 설정은 실제 납품 환경에서 확인해야 합니다.
  URL에는 비밀번호나 비밀 토큰을 포함하지 마세요.

## 로컬 검증

`frontend`에서 `npm run lint`, `npm run build`, `node --test tests/dashboardNavigation.test.mjs`를 실행합니다.
메뉴 선택 테스트는 14개 템플릿 URL 매핑, 서버/GPU 직접 링크 복원, 잘못된 선택값,
미설정 항목, 기존 URL·추가 ID의 메뉴 제외를 확인합니다. 실제 Grafana 연결은 실주소 입력 후 확인합니다.

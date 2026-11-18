# 한국공항공사 향후 패키징 체크리스트

**이 문서는 향후 작업 목록입니다. KAC IP·Nginx 프록시·Compose 마운트 적용과 최종 폐쇄망 패키징은 실행하지 않았습니다.** 현재는 [공통 채팅 코드](demo-chat.md)의 회사 vLLM·Langfuse 실제 연결 검증을 우선합니다. 회사에서 실행 중인 Nginx를 이 문서나 KAC 예제로 교체하지 않습니다.

## 확인된 저장소 근거와 미확인 현장 정보

| 저장소 근거 | 실제로 확인되는 내용 | 이 근거로 확정할 수 없는 내용 |
|---|---|---|
| [deploy/docker-compose.yml](../deploy/docker-compose.yml) | MariaDB와 backend 서비스, backend의 `.env.backend` 전달과 loopback 포트 연결 | KAC 현장의 Nginx 실행 방식·설정 파일·마운트 경로 |
| [기존 KAC 대시보드 문서](kac-dashboard-urls.md), [KAC API 예제](kac-nginx-api.conf.example) | 호스트 Nginx의 `/api/`를 loopback backend로 연결하는 이전 절차와 예제 | 현재 운영 서버가 같은 설정으로 실행 중이라는 사실 |
| [delivery/offline/nginx.conf](../delivery/offline/nginx.conf) | 별도 `gpu_llm` 참조 구성의 `/api/` → `backend:8000`, `/grafana/` → `grafana:3000`; URI 없는 `proxy_pass`; `Host`, `X-Forwarded-Proto` 헤더 | KAC의 실제 upstream·포트·WebSocket·인증 헤더 설정 |
| [delivery/offline/Dockerfile.web](../delivery/offline/Dockerfile.web) | 위 Nginx 파일을 이미지의 `/etc/nginx/conf.d/default.conf`로 `COPY` | KAC 호스트의 bind mount 원본 경로; 해당 경로를 현재 마운트한다는 사실 |
| [delivery/offline/offline.py](../delivery/offline/offline.py)의 `render` | 참조 web 서비스는 Nginx 설정 bind mount 없이 생성; Grafana는 `GF_SERVER_ROOT_URL=<웹 주소>/grafana/`, `GF_SERVER_SERVE_FROM_SUB_PATH=true` 및 자체 데이터/provisioning 볼륨 사용 | 최종 KAC Compose의 Nginx 볼륨 계약이나 운영 Grafana 설정 |
| 위 offline Nginx/Compose 참조 | `/langfuse/` location과 Langfuse 서비스는 정의되어 있지 않음 | 현장에 해당 프록시가 없다는 사실 또는 Langfuse가 subpath를 지원한다는 사실 |

`delivery/offline`은 별도 `gpu_llm` 도구의 기존 참조입니다. 이를 KAC 라이브 설정으로 간주하지 않습니다. KAC의 실제 Nginx가 호스트 서비스인지 컨테이너인지, 사용하는 Compose와 include 파일이 무엇인지 먼저 확인해야 합니다.

## 환경과 데이터 분리

- [ ] 회사 실제 연결 테스트 결과와 사용한 코드/의존성 버전을 정리한 뒤 같은 공통 버전으로 KAC 반입 대상을 정한다. 고객사별 브랜치나 이미지를 별도로 구현하지 않는다.
- [ ] KAC 연결값은 KAC의 `.env.backend`에서만 설정한다. 회사 env 파일·키·DB를 KAC 예제나 이미지에 복사하지 않는다.
- [ ] 요청된 KAC 목표 웹 경로는 `http://172.25.4.131/`의 기존 80번이며 vLLM 초기 후보는 `http://172.10.4.151:8001/v1`이다. 현장 담당자가 실제 경로와 접근성을 재확인하기 전에는 적용된 값으로 기록하지 않는다.
- [ ] GPU 1호기만 대상으로 확정한다. GPU 2호기 서비스·연결·수집 설정은 추가하지 않는다.
- [ ] `VLLM_MODEL`은 실제 `/v1/models` 응답 또는 운영 설정에서 확인한다. 모델을 새로 내려받거나 이름을 임의로 만들지 않는다.
- [ ] Langfuse SDK 수집 루트·프로젝트 키·브라우저 iframe URL을 구분한다. 이미 수집된 Trace와 프로젝트 데이터의 보존 설정을 확인한다.
- [ ] 기존 MariaDB/Grafana/Langfuse 데이터와 Compose 프로젝트·볼륨 이름을 기록하고 유지한다. DB init 재실행, 볼륨 삭제, 기존 환경파일 전체 덮어쓰기를 포함하지 않는다.
- [ ] 메모리 대화는 backend 1개·worker 1개에서 실행한다. 컨테이너 교체 시 대화 이력만 소실되며 Langfuse에 저장된 Trace는 유지되는지 확인한다.

## Nginx `/api/`와 채팅

- [ ] 실제 Nginx의 `nginx -T` 출력에서 server, include, listen, upstream, 일반 `/api/`, 인증/접근제어·프록시 헤더를 확인한다. 출력에 자격증명이 있으면 공유 전에 제거한다.
- [ ] 일반 API의 URI 전달 규칙을 유지한다. 채팅 프론트는 `/api/v1/chat/`을 사용하므로 `API_V1_PREFIX=/api/v1`과 일치시킨다.
- [ ] URI 없는 `proxy_pass http://<upstream>;`는 원래 `/api/...` 경로를 유지한다. `/` 또는 다른 URI를 붙여 접두사를 제거하는 변경을 하지 않도록 현재 경로 계약을 검사한다.
- [ ] [공통 채팅 예제](nginx-chat.conf.example)의 버퍼링·캐시·gzip·timeout 항목을 실제 upstream과 비교한다. 예제의 loopback 주소를 컨테이너 Nginx에 그대로 적용하지 않는다.
- [ ] 회사 설정을 그대로 덮어쓰거나 KAC API 예제를 전체 Nginx 설정으로 사용하지 않는다. 기존 정적 파일, TLS, 다른 location과 API 접근제어를 보존한다.

## `/grafana/` 프록시

- [ ] 실제 `/grafana/` location 존재 여부, upstream과 URI 보존/제거 방식을 확인하고 기존 동작을 유지한다. offline 참조는 `/grafana/`를 유지한 채 `grafana:3000`으로 전달한다.
- [ ] Grafana의 공개 `root_url`과 `serve_from_sub_path`가 최종 공개 `/grafana/` 경로와 일치하는지 확인한다. 저장소 참조는 두 값 모두 subpath 사용에 맞추지만 현장 적용 여부는 미확인이다.
- [ ] 로그인 redirect·정적 자원·쿠키 경로·iframe 표시를 확인한다. backend SDK 설정과 Grafana 화면 URL을 혼용하지 않는다.
- [ ] 현재 현장에 필요한 `Host`, 전달 프로토콜, 원본 주소, 인증 헤더 및 Grafana Live/WebSocket 처리가 있다면 보존한다. 저장소의 offline 예제에는 WebSocket upgrade 설정이 없으므로 이것만으로 현장 WebSocket 계약을 추정하지 않는다.

## `/langfuse/` 프록시

- [ ] KAC에 `/langfuse/`가 이미 있거나 새로 필요하다는 요구를 먼저 확인한다. 저장소에는 검증된 기존 Langfuse subpath 프록시가 없다.
- [ ] 자체 호스팅 Langfuse의 정확한 버전과 배포 방식에서 subpath를 지원하는지 확인한다. `/langfuse/` 프록시를 추가하는 것만으로 로그인·정적 자원·API·redirect가 정상 동작한다고 가정하지 않는다.
- [ ] 사용할 공개 URL, 애플리케이션 base path/인증 callback, 쿠키 경로, iframe 정책 및 proxy prefix 유지/제거 규칙을 해당 버전 기준으로 검증한다. 확인 전에는 실행 가능한 최종 location을 만들어 적용하지 않는다.
- [ ] SDK의 `LANGFUSE_BASE_URL`은 backend에서 접근 가능한 수집 루트로 별도 검증한다. 브라우저 `/langfuse/` iframe 경로를 SDK 설정에 자동 복사하지 않는다. 실제 OTLP 수집 경로와 공개 프록시를 통한 동작은 각각 테스트한다.
- [ ] 수집 후 사용자·세션·Trace·Span/Generation과 화면 반영 지연을 확인한다. Langfuse v4 환경이면 [공통 문서의 SDK 호환성 조건](demo-chat.md)을 추가 확인한다.

## Compose Nginx 설정 파일과 마운트

- [ ] 현장 Nginx가 컨테이너라면 실제 서비스명·이미지·Compose 프로젝트와 설정의 제공 방식(image `COPY`, bind mount, Docker config 등)을 확인한다. 호스트 Nginx라면 존재하지 않는 Compose Nginx 마운트를 새로 가정하지 않는다.
- [ ] bind mount를 사용한다면 확인된 호스트 원본 파일의 절대 경로와 컨테이너 목적 경로를 기록한다. 위 Dockerfile의 `/etc/nginx/conf.d/default.conf`는 이미지 내 COPY 목적지이며 현장 마운트 경로의 증거가 아니다.
- [ ] 컨테이너 생성 전에 원본이 실제 파일로 존재하는지, 파일·상위 디렉터리 권한으로 읽을 수 있는지 확인한다. 없는 원본이 디렉터리로 생성되어 잘못 마운트되지 않도록 검증한다.
- [ ] 읽기 전용 마운트 등 필요한 권한을 검토하고 기존 include 구조·전체 디렉터리를 가리는 마운트·중복 location을 확인한다. 기존 데이터 볼륨은 유지한다.
- [ ] Compose `config --quiet`로 구조를 검사하고, 실제 Nginx 컨테이너 안의 `nginx -T`로 예상 파일이 읽혔는지 확인한다. 호스트 파일 확인만으로 컨테이너 적용 완료로 판정하지 않는다.
- [ ] 대상이 확정된 뒤 해당 호스트/컨테이너에서 `nginx -t`를 실행한다. 검사 성공 후에만 그 실행 방식에 맞는 reload를 수행하고, `/api/`·채팅·Grafana·Langfuse·정적 화면을 확인한다. 이 단계는 아직 수행하지 않았다.

## 최종 폐쇄망 반입 시점

- [ ] 실제 회사 연동이 끝난 공통 소스·고정 SDK/HTTP 클라이언트·프론트와 대상 CPU 아키텍처를 확정한다.
- [ ] 필요한 의존성을 포함한 새 이미지를 준비 환경에서 빌드하고 검증한 뒤 이미지 tar·식별자·체크섬을 기록한다. 기존 tar에 새 채팅 기능이 포함되었다고 간주하지 않는다.
- [ ] 현장 비밀값이 없는 Compose/env 예제·확인된 Nginx 파일/마운트·설치 및 복구 절차·검증표를 준비한다. Langfuse 자체 서비스의 추가 반입 필요 여부는 현장 인프라 확인 후 결정한다.
- [ ] 기존 env 및 볼륨을 보존하면서 반입한 이미지만 로드하고 인터넷 접근 없이 동작하는지 검사한다. 외부 registry·pip·npm 접근이 발생하지 않는지 확인한다.
- [ ] 실제 KAC에서 A/B 사용자, 같은 대화 2개 Trace, 새 대화, 실제 Span/Generation, 스트리밍 중지·오류·기존 모니터링 회귀를 다시 확인하고 회사 결과와 분리해 기록한다.

현재 완료된 것은 코드와 모의 검증 및 문서 정리입니다. 회사 실제 연결 성공, KAC 프록시 적용, 최종 반입물 생성은 각각 별도 결과가 있어야 완료로 표시합니다.

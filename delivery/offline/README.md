# DCGM 1대 / 8 GPU + LLM Dashboard 폐쇄망 반입 도구

**현재 상태: 패키징 소스와 설정 생성 도구. 실행 가능한 이미지 tar 및 호스트 설치 파일은 아직 생성·검증하지 않았습니다.**
Ubuntu 상세 버전·CPU 아키텍처·GPU 모델/드라이버·LLM 메트릭 규격이 미확정입니다.
`images.example.json`은 예시이며 DCGM 버전은 의도적으로 비워 두었습니다. 미확정 상태에서는 bundle이 실패합니다.
이 문서의 명령은 소스 디렉터리 또는 생성된 반입 묶음 디렉터리에서 실행합니다.

## 설치 구성

GPU가 8장 장착된 Ubuntu 서버 **한 대에 관제도 함께 설치**하는 구성을 구현합니다.
관제 서버가 별도라면 이 구성을 그대로 설치하지 말고 DCGM 수집부 배치를 먼저 분리해야 합니다.
기존 추론 서비스의 실행·모델 다운로드·교체는 하지 않습니다.

| 구성 | 역할 | 현장 노출 |
|---|---|---|
| web | Insight 정적 화면 + API/Grafana 프록시 | 지정한 내부 IP:8080 |
| backend | 관리자 인증, `gpu`, `vllm` 설정 | Docker 내부 |
| mariadb | Insight 관리 DB 및 기존 앱 초기화에 필요한 desk_users DB | Docker 내부 |
| grafana | DCGM / 기본 LLM 대시보드 자동 등록 | 웹의 /grafana/, 호스트 127.0.0.1:13000 |
| prometheus | DCGM와 기존 LLM 메트릭 수집, 15일 보존 | 호스트 127.0.0.1:19090 |
| dcgm | 로컬 NVIDIA GPU 8장 수집 | Docker 내부 9400 |

GPU 화면은 서버 하나와 GPU 0~7 탭, LLM은 Dashboard 하나만 제공합니다.
다른 관제 화면은 feature guard가 차단하고 URL을 config 응답에서 제외합니다. 터미널 HTTP/WS도 차단합니다.
기존 EICN 기본 동작은 `MONITORING_SCOPE=profile`로 유지하며 이번 패키지만 `gpu_llm`을 사용합니다.
이미지에는 현장 IP나 고객사 env를 넣지 않습니다. 동일 앱 이미지를 런타임 설정으로 제어합니다.

## 출발 전 반드시 확정할 것

현장 IP는 몰라도 됩니다. **OS/아키텍처/드라이버/LLM 메트릭 규격까지 몰라도 된다는 뜻은 아닙니다.**
현장 담당자에게 아래 명령의 결과를 요청하세요. Docker 또는 드라이버가 없으면 해당 오류도 기록합니다.

```bash
cat /etc/os-release
uname -m
uname -r
nvidia-smi
nvidia-smi -L
docker version
docker compose version
nvidia-ctk --version
```

- Ubuntu 버전과 커널에 맞는 Docker Engine, Compose 플러그인, containerd와 전체 deb 의존성.
- NVIDIA 드라이버가 없다면 GPU/커널에 맞는 드라이버, 커널 헤더와 전체 의존성. Secure Boot/MOK 등록 및 재부팅 필요 여부.
- NVIDIA Container Toolkit과 전체 의존성. 이미 드라이버/런타임이 있으면 버전 호환성 확인.
- Python 3와 필요한 OS 기본 패키지. 현장 실행 도구는 Python 표준 라이브러리만 사용합니다.
- **위 OS 설치 파일은 현재 bundle에 포함되지 않습니다.** 동일 OS·아키텍처의 깨끗한 시험 서버에서 의존성을 수집하고 네트워크를 끊은 설치 검증이 필요합니다. 범용 deb 묶음으로 간주하지 않습니다.
- LLM 메트릭이 노출되는 포트·경로·인증 여부, 엔진 종류/버전. `8000/metrics`는 편의상 둔 추정값입니다. 호스트 IP에서 도달 가능해야 하며 컨테이너 내부 loopback 전용 주소는 사용할 수 없습니다.
- 현재 LLM 대시보드는 `vllm:*` 메트릭을 사용하는 새 기본 화면입니다. 엔진이 다른 경우 exporter/쿼리 조정이 필요합니다. 기존 Grafana 화면을 그대로 반입하려면 원본 JSON, 데이터소스, 플러그인과 연계 수집 설정이 추가로 필요합니다.
- GPU 인덱스 0~7의 물리 GPU 8장을 전제로 합니다. MIG 구성과 GPU 종류별 미지원 DCGM 필드는 별도 검증합니다.

## 인터넷 연결된 준비 PC에서 이미지 묶음 만들기

```bash
cp images.example.json images.json
# images.json에서 현장 CPU platform과 검증할 버전/태그를 확정합니다.
# 특히 dcgm 자리표시자는 GPU 드라이버와 호환되는 NVIDIA exporter 이미지로 교체합니다.
python3 offline.py --manifest images.json bundle --output output/gpu-llm
```

준비 PC에는 실행 중인 Docker 엔진과 buildx가 필요합니다. 다른 CPU용 빌드는 에뮬레이션 또는 해당 CPU의 빌더가 필요합니다.
이미지 빌드는 frontend/backend 공통 코드로 수행하며 서버 IP, `.env`, 기존 DB, `node_modules`는 빌드 컨텍스트에 복사하지 않습니다.
서드파티 이미지를 pull한 뒤 대상 CPU와 이미지 ID를 확인하고, 6개 이미지를 하나의 tar로 저장합니다.
태그뿐 아니라 실제 이미지 ID를 기록해 현장에서 다른 이미지가 섞이면 기동을 거부합니다.

```text
output/gpu-llm/
  offline.py
  README.md
  images.json       # 아키텍처, 이미지 참조, 실제 이미지 ID
  images.tar        # 앱/DB/Grafana/Prometheus/DCGM 전체 이미지
  SHA256.json       # 반입 파일 체크섬
```

실패한 출력 디렉터리는 `INCOMPLETE`로 표시합니다. 실패 디렉터리를 반입하지 말고 새 출력 경로로 재시도합니다.
이 이미지 묶음과 확정된 OS 설치 파일/체크리스트를 함께 반입해야 전체 설치 준비가 끝납니다.
현재 빌드는 npm lockfile을 사용하지만 Python 및 기반 이미지의 전이 의존성까지 잠근 재현 빌드는 아닙니다. 최종 납품물은 생성한 tar/이미지 ID로 고정합니다.

## 현장에서 실행

먼저 반입한 OS 설치 파일로 Docker/Compose/NVIDIA 런타임을 준비합니다. 드라이버 변경과 Docker 재시작은 기존 LLM 서비스 중단을 일으킬 수 있으므로 현장 운영 절차에 따라 수행합니다.
`nvidia-smi`에서 8장이 보이고 Docker가 NVIDIA GPU를 사용할 수 있어야 합니다.

```bash
python3 offline.py load
python3 offline.py configure --host 10.0.0.10
python3 offline.py up
# 최소 두 번의 scrape가 끝난 뒤 실행합니다. 초기에는 30~60초 정도 필요합니다.
python3 offline.py check
```

`10.0.0.10`은 예시이며 **그 Ubuntu 서버에 실제 할당된 내부 IPv4**로 바꿉니다. 웹은 그 IP의 8080 포트에 바인딩합니다.
LLM이 같은 서버의 8000 포트 `/metrics`라면 IP만으로 설정됩니다. 다르면 다음처럼 포트·경로까지 설정합니다.

```bash
python3 offline.py configure --host 10.0.0.10 --llm-url http://10.0.0.20:9000/metrics
python3 offline.py up
```

`configure`는 IP·URL을 검증하고 설정 파일을 생성합니다. 쉘로 설정값을 실행하지 않습니다.
`up`은 `--no-build --pull never`로만 실행합니다. 공개 registry, apt, pip, npm에 접근하지 않습니다.
Grafana의 원격 플러그인 사전 설치와 업데이트 확인도 끕니다. 기동 자체와 수집 성공은 구분하며 `check` 실패를 무시하지 않습니다.

초기 실행 시 Insight와 Grafana의 admin 비밀번호를 각각 입력합니다. 비밀번호는 커맨드라인 인수/출력/파일에 평문으로 남기지 않습니다.
Insight는 기존 SSHA 방식과 호환되는 salted hash만 설정에 저장하고 Grafana는 CLI 표준입력으로 초기 비밀번호를 설정합니다.
Grafana 초기 비밀번호 변경에 성공해야 웹 프록시를 기동합니다. Grafana 익명 접근은 허용하지 않으므로 최초 iframe에서 별도 Grafana 로그인이 필요합니다.
Insight 로그인 후 `/grafana/login`에서 Grafana에 로그인하면 같은 브라우저의 iframe에서도 세션을 사용합니다.

`runtime/`에는 현장에서 생성한 DB 연결 자격증명과 JWT 키가 권한 600 파일로 저장됩니다. 사용자 비밀번호와 달리 서비스 간 인증에 필요한 복원 가능한 비밀값입니다. 디렉터리 전체를 반입 템플릿·Git·로그에 복사하지 않습니다.
DB, Grafana 계정, 시계열 데이터는 Compose의 명명된 볼륨에 보존합니다. `docker compose down -v`는 데이터 삭제이므로 실행하지 않습니다.
현재 HTTP 구성입니다. 고객사 HTTPS 정책이 있으면 현장 인증서·TLS 프록시를 별도로 준비해야 합니다.

## IP 변경과 재기동

```bash
python3 offline.py configure --host 10.0.0.11
python3 offline.py up
python3 offline.py check
```

DB 계정/JWT/Insight 초기 해시와 데이터 볼륨을 유지하고 컨테이너를 재생성합니다.
LLM 주소가 이전 관제 서버 IP와 같았다면 LLM 주소의 IP도 함께 갱신합니다. 별도 서버 주소는 유지합니다.
컨테이너 재생성 중 관제 화면이 잠시 중단됩니다. 열린 브라우저는 새 IP로 접속/새로고침합니다.
`grafana-initialized`와 데이터 볼륨은 한 세트로 보존합니다. Grafana 볼륨을 수동 삭제했다면 표시 파일도 제거하고 새 비밀번호로 초기화해야 합니다.

## 반입 승인 기준

- 외부 네트워크 차단 상태에서 이미지 로드, 최초 부팅, 재부팅 후 자동 기동 확인.
- 로그인, GPU 0~7 탭 모두 해당 GPU 데이터 확인. UUID 8개와 GPU 인덱스 대응 확인.
- Prometheus target 2개 UP, LLM 지표 이름과 대시보드 값 확인. 추론 요청이 없으면 지연 히스토그램 등이 아직 없을 수 있으므로 승인된 테스트 요청 후 확인.
- Server/Observability/Trace 등 비활성 직접 경로 차단과 터미널 HTTP/WS 차단 확인.
- IP 변경 후 재빌드 없이 화면/수집 복구, DB 계정과 기존 수집 데이터 보존 확인.
- 실제 디스크 용량과 GPU 메트릭 지원, Docker 런타임 호환성 확인.
- `check` 성공만으로 브라우저 iframe/인증 및 실제 GPU 부하 검증까지 완료된 것으로 간주하지 않습니다.

## 구현 근거

레포 기능 전수조사: [feature-inventory.md](feature-inventory.md).
DCGM 구성은 [NVIDIA 설치 문서](https://docs.nvidia.com/datacenter/dcgm/latest/installation/install-dcgm-exporter.html),
LLM 기본 패널은 [vLLM 메트릭 문서](https://docs.vllm.ai/en/latest/design/metrics/)를 기준으로 작성했습니다.
특정 LLM 엔진/버전의 현장 호환성을 확인한 결과는 아닙니다.

## 현재 작업 환경 검증 기록

2026-09-30 로컬 검증:

- Frontend lint 통과(기존 iframe effect 경고 5개), build 통과(번들 크기 경고), 메뉴 테스트 6개 통과.
- Backend compileall 및 unittest 15개 통과. pytest는 로컬 가상환경에 없어 unittest로 대체.
- Offline 도구 테스트 6개 통과: IP 재설정/자격증명 유지, 8 GPU URL 생성, 입력 검증, 체크섬 변조 탐지, pull/build 금지, 실제 Compose 파서 검증.
- 기존 deploy Compose config 통과. 기존 비추적 env의 `__all` 보간 경고는 해당 파일을 수정하지 않고 남김.
- Docker 엔진 미실행으로 실제 이미지 빌드/컨테이너 기동 미검증. 실물 GPU와 폐쇄망 인수 테스트 미실시.

현장 담당자는 저장소의 `host-report.sh`를 GPU 서버에서 다음처럼 실행해 결과를 전달할 수 있습니다.

```bash
sh host-report.sh
```

이 스크립트는 OS/CPU/GPU/드라이버/도구 버전만 읽고 설치나 시스템 설정 변경을 하지 않습니다.
LLM 엔진과 메트릭 주소는 이 호스트 정보만으로 확정할 수 없으므로 별도 확인이 필요합니다.

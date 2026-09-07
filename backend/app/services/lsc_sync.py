"""LSC(OpenLDAP 동기화) 원격 실행 서비스.

승인 처리 직후 SSH로 원격 서버의 동기화 스크립트를 실행한다.
DB 승인과는 분리되어 있어, 실패해도 승인 자체는 유지되고 경고만 반환된다.
"""

import logging
import subprocess
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LscSyncResult:
    ok: bool
    detail: str


def run_lsc_sync() -> LscSyncResult:
    """원격 서버에 SSH로 접속해 LSC 동기화 스크립트를 순차 실행한다.

    설정된 명령(lsc_sync_command)을 원격 셸에서 그대로 실행하므로,
    기본값은 `lsc-sync-now.sh && make_home.sh` 순차 실행이다.
    """
    settings = get_settings()

    if not settings.lsc_sync_enabled:
        logger.info("LSC 동기화 비활성화 상태(LSC_SYNC_ENABLED=false), 건너뜀")
        return LscSyncResult(ok=True, detail="동기화 비활성화 상태로 건너뜀")

    cmd = [
        "ssh",
        "-p",
        str(settings.lsc_ssh_port),
        "-o",
        "BatchMode=yes",  # 비밀번호 프롬프트 금지 (키 인증만)
        "-o",
        "StrictHostKeyChecking=no",  # 컨테이너 known_hosts가 읽기전용/비어있어도 접속
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        f"ConnectTimeout={min(settings.lsc_ssh_timeout, 30)}",
    ]
    if settings.lsc_ssh_key_path:
        cmd += ["-i", settings.lsc_ssh_key_path]
    cmd += [
        f"{settings.lsc_ssh_user}@{settings.lsc_ssh_host}",
        settings.lsc_sync_command,
    ]

    target = f"{settings.lsc_ssh_user}@{settings.lsc_ssh_host}:{settings.lsc_ssh_port}"
    logger.info("LSC 동기화 실행: %s -> %s", target, settings.lsc_sync_command)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.lsc_ssh_timeout,
            check=False,
        )
    except FileNotFoundError:
        logger.exception("ssh 실행 파일을 찾을 수 없음")
        return LscSyncResult(ok=False, detail="서버에 ssh 클라이언트가 설치되어 있지 않습니다.")
    except subprocess.TimeoutExpired:
        logger.error("LSC 동기화 타임아웃(%ss): %s", settings.lsc_ssh_timeout, target)
        return LscSyncResult(
            ok=False,
            detail=f"동기화가 {settings.lsc_ssh_timeout}초 내에 완료되지 않았습니다.",
        )

    if proc.returncode == 0:
        logger.info("LSC 동기화 성공: %s", target)
        return LscSyncResult(ok=True, detail="LSC 동기화가 완료되었습니다.")

    err = (proc.stderr or proc.stdout or "").strip()
    snippet = err[-300:] if err else f"종료 코드 {proc.returncode}"
    logger.error("LSC 동기화 실패(rc=%s): %s", proc.returncode, err)
    return LscSyncResult(ok=False, detail=snippet)

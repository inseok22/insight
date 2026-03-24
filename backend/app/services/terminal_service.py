from datetime import datetime

HELP_TEXT = (
    "사용 가능한 명령어:\r\n"
    "  help   - 명령어 목록\r\n"
    "  whoami - 현재 로그인 사용자\r\n"
    "  target - 현재 타겟 노드\r\n"
    "  date   - 서버 시간\r\n"
    "  clear  - 화면 지우기\r\n"
    "  exit   - 연결 종료\r\n"
)

PROMPT = "$ "


def initial_banner(target: str, username: str) -> str:
    return (
        "\x1b[32mTSlurmOps WebSocket terminal (demo)\x1b[0m\r\n"
        f"Connected target: {target}\r\n"
        f"User: {username}\r\n"
        "이 엔드포인트는 실제 shell/SSH 연결 전의 스텁입니다.\r\n"
        "help 를 입력해 사용 가능한 명령어를 확인하세요.\r\n\r\n"
        f"{PROMPT}"
    )


def handle_command(command: str, target: str, username: str) -> tuple[str, bool]:
    normalized = command.strip()

    if not normalized:
        return (PROMPT, False)
    if normalized == "help":
        return (f"\r\n{HELP_TEXT}{PROMPT}", False)
    if normalized == "whoami":
        return (f"\r\n{username}\r\n{PROMPT}", False)
    if normalized == "target":
        return (f"\r\n{target}\r\n{PROMPT}", False)
    if normalized == "date":
        return (f"\r\n{datetime.now().isoformat(sep=' ', timespec='seconds')}\r\n{PROMPT}", False)
    if normalized == "clear":
        return ("\x1b[2J\x1b[H" + PROMPT, False)
    if normalized == "exit":
        return ("\r\n세션을 종료합니다.\r\n", True)

    return (f"\r\n알 수 없는 명령어: {normalized}\r\n{PROMPT}", False)

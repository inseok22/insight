"""Single-process, temporary demo conversations. No database persistence."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import time
from uuid import uuid4

from fastapi import HTTPException
import httpx

from app.core.config import Settings
from app.services.chat_telemetry import ChatTelemetry, Observation

SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_SESSIONS = 200
MAX_HISTORY_TURNS = 20
MAX_HISTORY_CHARS = 128000
MAX_OUTPUT_CHARS = 64000


class ModelError(Exception):
    """Only predefined safe messages cross the client/telemetry boundary."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(code)


@dataclass
class ChatRun:
    request_id: str
    message: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=32))
    task: asyncio.Task | None = None
    cancel_requested: bool = False
    disconnected: bool = False
    started: bool = False
    root: Observation | None = None


@dataclass
class Conversation:
    id: str
    owner_id: int
    messages: list[dict] = field(default_factory=list)
    touched: float = field(default_factory=time.monotonic)
    active: ChatRun | None = None


def encode_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ChatService:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None, telemetry=None):
        self.settings = settings
        # Redirects could disclose the optional API key to another host.
        self.client = client if client is not None else httpx.AsyncClient(follow_redirects=False, trust_env=False)
        self.telemetry = telemetry if telemetry is not None else ChatTelemetry(settings)
        self.sessions: dict[str, Conversation] = {}
        self.discovered_model: str | None = None

    def create_session(self, owner_id: int) -> Conversation:
        now = time.monotonic()
        self.sessions = {key: session for key, session in self.sessions.items()
                         if session.active or now - session.touched < SESSION_TTL_SECONDS}
        if len(self.sessions) >= MAX_SESSIONS:
            raise HTTPException(429, "시연 대화 수가 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.")
        session = Conversation(id=str(uuid4()), owner_id=owner_id)
        self.sessions[session.id] = session
        return session

    def owned_session(self, session_id: str, owner_id: int) -> Conversation:
        session = self.sessions.get(session_id)
        if (session is None or session.owner_id != owner_id
                or (session.active is None and time.monotonic() - session.touched >= SESSION_TTL_SECONDS)):
            raise HTTPException(404, "대화가 없거나 만료되었습니다. 새 대화를 시작해 주세요.")
        session.touched = time.monotonic()
        return session

    def begin(self, session: Conversation, request_id: str, message: str) -> ChatRun:
        # No await between check and assignment: atomic within the one worker loop.
        if session.active is not None:
            raise HTTPException(409, "이 대화에서 응답을 생성 중입니다. 완료하거나 중지해 주세요.")
        run = ChatRun(request_id=request_id, message=message)
        # The internal account id, not the login name, identifies the user in traces.
        run.root = self.telemetry.start(user_id=str(session.owner_id), session_id=session.id, message=message)
        session.active = run
        run.task = asyncio.create_task(self._produce(session, run))
        return run

    def stop(self, session: Conversation, request_id: str) -> str:
        run = session.active
        if run is None or run.request_id != request_id:
            return "idle"
        if not run.cancel_requested:
            run.cancel_requested = True
            # An unstarted coroutine cannot run its finally block if cancelled.
            # Let it start, observe the flag, and close the request trace itself.
            if run.task and run.started and not run.task.cancelling():
                run.task.cancel()
        return "cancelling"

    async def disconnect(self, session: Conversation, run: ChatRun):
        run.disconnected = True
        # Unblock a terminal event already waiting behind undelivered deltas.
        # Never cancel a producer twice: a second cancellation could interrupt
        # the upstream HTTP stream's asynchronous connection cleanup.
        while not run.queue.empty():
            run.queue.get_nowait()
        if run.task is not None and not run.task.done():
            already_cancelled = run.cancel_requested
            run.cancel_requested = True
            if run.started and not already_cancelled and not run.task.cancelling():
                run.task.cancel()
        if run.task is not None:
            await asyncio.gather(run.task, return_exceptions=True)
        # Also handles cancellation before the producer was ever scheduled.
        if session.active is run:
            session.active = None
            session.touched = time.monotonic()

    async def events(self, run: ChatRun):
        while True:
            try:
                event, data = await asyncio.wait_for(run.queue.get(), timeout=10)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield encode_event(event, data)
            if event == "done":
                break

    async def _emit(self, run, event, data):
        if not run.disconnected:
            await run.queue.put((event, data))

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.settings.vllm_api_key}"} if self.settings.vllm_api_key else {}

    def url(self, path):
        if not self.settings.vllm_api_base_url:
            raise ModelError("not_configured", "백엔드의 VLLM_API_BASE_URL을 설정해 주세요.")
        return f"{self.settings.vllm_api_base_url}/{path}"

    async def _model(self, root, run):
        if self.settings.vllm_model.strip():
            return self.settings.vllm_model.strip()
        if self.discovered_model:
            return self.discovered_model
        span = root.child("model.resolve", input={"source": "/models"})
        try:
            response = await self.client.get(self.url("models"), headers=self.headers,
                                             timeout=self.settings.vllm_timeout_seconds)
            response.raise_for_status()
            data = response.json().get("data", [])
            ids = list(dict.fromkeys(item["id"] for item in data
                                     if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()))
            if len(ids) != 1:
                raise ModelError("model_selection", "모델이 없거나 여러 개입니다. VLLM_MODEL에 실제 모델명을 설정해 주세요.")
            self.discovered_model = ids[0]
            span.finish("completed", output={"model": ids[0]})
            return ids[0]
        except asyncio.CancelledError:
            span.finish("cancelled" if run.cancel_requested else "error",
                        error_code=None if run.cancel_requested else "timeout")
            raise
        except Exception:
            span.finish("error", error_code="model_discovery_failed")
            raise

    async def _packets(self, response):
        """Parse SSE frames, including comments and split/multiline data fields."""
        data = []
        size = 0
        async for line in response.aiter_lines():
            if not line:
                if data:
                    yield "\n".join(data)
                data = []
                size = 0
            elif line.startswith("data:"):
                value = line[5:].removeprefix(" ")
                size += len(value)
                if size > 1024 * 1024:
                    raise ModelError("invalid_stream", "모델 응답 형식을 처리할 수 없습니다.")
                data.append(value)
        if data:
            yield "\n".join(data)

    @staticmethod
    def _usage(value):
        if not isinstance(value, dict):
            return {}
        return {target: value[source] for source, target in (
            ("prompt_tokens", "input"), ("completion_tokens", "output"), ("total_tokens", "total"))
            if type(value.get(source)) is int and value[source] >= 0}

    @staticmethod
    def _size(messages):
        return {"messages": len(messages), "chars": sum(len(item["content"]) for item in messages)}

    async def _produce(self, session, run):
        run.started = True
        root = run.root
        generation = None
        output = ""
        usage = {}
        status = "error"
        error_code = None
        try:
            await self._emit(run, "meta", {"session_id": session.id, "request_id": run.request_id,
                                           "trace_id": root.trace_id})
            if run.cancel_requested:
                raise asyncio.CancelledError
            history = root.child("history.prepare", input={"stored_messages": len(session.messages)})
            messages = [item.copy() for item in session.messages]
            # The full conversation is stored once, as the vllm.generate input.
            history.finish("completed", output=self._size(messages))
            prompt = root.child("prompt.build", input={"history": self._size(messages),
                                                       "question_chars": len(run.message)})
            messages.append({"role": "user", "content": run.message})
            prompt.finish("completed", output=self._size(messages))
            # This is an overall request deadline, not only a per-chunk read timeout.
            async with asyncio.timeout(self.settings.vllm_timeout_seconds):
                completion_url = self.url("chat/completions")
                model = await self._model(root, run)
                generation = root.child("vllm.generate", generation=True, input=messages, model=model)
                async with self.client.stream("POST", completion_url, headers=self.headers,
                        json={"model": model, "messages": messages, "stream": True,
                              "stream_options": {"include_usage": True}},
                        timeout=self.settings.vllm_timeout_seconds) as response:
                    response.raise_for_status()
                    completed = False
                    first_token = True
                    async for packet in self._packets(response):
                        if packet == "[DONE]":
                            completed = True
                            break
                        value = json.loads(packet)
                        if not isinstance(value, dict) or value.get("error"):
                            raise ModelError("model_error", "모델 서버에서 오류가 발생했습니다.")
                        if isinstance(value.get("model"), str) and value["model"]:
                            generation.update(model=value["model"])
                        usage.update(self._usage(value.get("usage")))
                        choices = value.get("choices", [])
                        for choice in choices:
                            if choice.get("index", 0) != 0:
                                continue
                            text = choice.get("delta", {}).get("content")
                            if text is None:
                                continue
                            if not isinstance(text, str):
                                raise ModelError("invalid_stream", "모델 응답 형식을 처리할 수 없습니다.")
                            if len(output) + len(text) > MAX_OUTPUT_CHARS:
                                raise ModelError("output_limit", "시연 응답 길이 한도를 초과했습니다. 질문 범위를 줄여 주세요.")
                            if first_token and text:
                                generation.update(completion_start_time=datetime.now(timezone.utc))
                                first_token = False
                            output += text
                            await self._emit(run, "delta", {"text": text})
                    if not completed:
                        raise ModelError("incomplete_stream", "모델 응답 연결이 완료 전에 끊어졌습니다.")
            if run.cancel_requested:
                status = "cancelled"
            else:
                session.messages.extend([{"role": "user", "content": run.message},
                                         {"role": "assistant", "content": output}])
                while len(session.messages) > MAX_HISTORY_TURNS * 2 or sum(len(m["content"]) for m in session.messages) > MAX_HISTORY_CHARS:
                    del session.messages[:2]
                status = "completed"
        except asyncio.CancelledError:
            status = "cancelled"
            # Task cancellation is preserved; the terminal SSE event is queued in finally.
            raise
        except Exception as exc:
            if isinstance(exc, ModelError):
                error_code, message = exc.code, exc.message
            elif isinstance(exc, (TimeoutError, httpx.TimeoutException)):
                error_code, message = "timeout", "모델 응답 시간이 초과되었습니다. 다시 시도해 주세요."
            elif isinstance(exc, httpx.HTTPStatusError):
                error_code, message = "upstream_http", "모델 서버가 요청을 거부했습니다. 연결 설정과 모델명을 확인해 주세요."
            elif isinstance(exc, httpx.RequestError):
                error_code, message = "upstream_connection", "모델 서버에 연결할 수 없습니다. 연결 설정을 확인해 주세요."
            else:
                error_code, message = "invalid_stream", "모델 응답을 처리하지 못했습니다. 다시 시도해 주세요."
            await self._emit(run, "error", {"code": error_code, "message": message})
        finally:
            if generation:
                generation.finish(status, output={"role": "assistant", "content": output},
                                  error_code=error_code, **({"usage_details": usage} if usage else {}))
            root.finish(status, output=output, error_code=error_code)
            try:
                await self._emit(run, "done", {"status": status})
            finally:
                # Keep a backpressured producer discoverable by shutdown until
                # its terminal event has been queued or its browser disconnects.
                if session.active is run:
                    session.active = None
                    session.touched = time.monotonic()

    async def aclose(self):
        for session in list(self.sessions.values()):
            if session.active:
                await self.disconnect(session, session.active)
        await self.client.aclose()
        await asyncio.to_thread(self.telemetry.shutdown)

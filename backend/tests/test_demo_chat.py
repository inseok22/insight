"""Demo chat contracts with real ASGI routing and a local mock vLLM transport.

No database, field server, model, or Langfuse credentials are required.
"""
import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
import httpx

from app.api.v1.endpoints import config, demo_chat
from app.core.config import Settings
from app.dependencies.auth import get_current_active_admin
from app.services.demo_chat import ChatService
from app.services.chat_telemetry import ChatTelemetry


MODEL = "actual-model-from-mock-server"
PRIVATE_KEY = "mock-vllm-secret-never-return-this"


def sse_packet(payload):
    return ("data: " + json.dumps(payload) + "\n\n").encode()


def generation_bytes(text="모의 답변"):
    return b"".join([
        sse_packet({"model": MODEL, "choices": [{"delta": {"content": text}}]}),
        sse_packet({"model": MODEL, "choices": [], "usage": {
            "prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}}),
        b"data: [DONE]\n\n",
    ])


def events(response):
    """Parse the public SSE contract without assuming TCP chunk boundaries."""
    parsed = []
    for packet in response.text.replace("\r\n", "\n").split("\n\n"):
        event = "message"
        data = []
        for line in packet.splitlines():
            if line.startswith("event:"):
                event = line.partition(":")[2].strip()
            elif line.startswith("data:"):
                data.append(line.partition(":")[2].lstrip())
        if data:
            parsed.append((event, json.loads("\n".join(data))))
    return parsed


class PausedModelStream(httpx.AsyncByteStream):
    """After one token, behave like a model waiting indefinitely for its next token."""

    def __init__(self):
        self.waiting = asyncio.Event()
        self.release = asyncio.Event()
        self.closed = False

    async def __aiter__(self):
        yield sse_packet({"model": MODEL, "choices": [{"delta": {"content": "first"}}]})
        self.waiting.set()
        await self.release.wait()
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        self.closed = True


class SlowClosingModelStream(PausedModelStream):
    def __init__(self):
        super().__init__()
        self.closing = asyncio.Event()
        self.close_release = asyncio.Event()

    async def aclose(self):
        self.closing.set()
        await self.close_release.wait()
        self.closed = True


class DemoChatTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.settings = Settings(
            _env_file=None,
            product_profile="llm",
            demo_chat_enabled=True,
            vllm_api_base_url="http://mock-vllm.test/v1",
            vllm_model=MODEL,
            vllm_api_key=PRIVATE_KEY,
            vllm_timeout_seconds=5,
            langfuse_tracing_enabled=False,
        )
        self.calls = []
        self.model_ids = [MODEL]
        self.generation_status = 200
        self.generation_body = generation_bytes()
        self.stream = None
        self.transport_exception = None
        self.model_delay = 0

        async def model_handler(request):
            self.calls.append({"path": request.url.path, "url": str(request.url),
                               "timeout": request.extensions.get("timeout"), "headers": dict(request.headers),
                               "body": json.loads(request.content) if request.content else None})
            if self.transport_exception is not None:
                raise self.transport_exception
            if request.url.path == "/v1/models":
                if self.model_delay:
                    await asyncio.sleep(self.model_delay)
                return httpx.Response(200, json={"data": [{"id": value} for value in self.model_ids]})
            self.assertEqual(request.url.path, "/v1/chat/completions")
            if self.stream is not None:
                return httpx.Response(200, stream=self.stream,
                                      headers={"content-type": "text/event-stream"})
            return httpx.Response(self.generation_status, content=self.generation_body,
                                  headers={"content-type": "text/event-stream"})

        self.upstream = httpx.AsyncClient(transport=httpx.MockTransport(model_handler))
        self.service = ChatService(self.settings, client=self.upstream)
        self.app = FastAPI()
        self.app.state.demo_chat = self.service
        self.app.include_router(demo_chat.router, prefix="/api/v1")
        self.app.include_router(config.router, prefix="/api/v1")
        self.admin = SimpleNamespace(id=101, username="user-a", is_active=True)
        self.app.dependency_overrides[get_current_active_admin] = lambda: self.admin
        self.patches = [patch(f"{module}.get_settings", return_value=self.settings) for module in (
            "app.dependencies.features", "app.api.v1.endpoints.config")]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")

    async def asyncTearDown(self):
        if self.stream is not None:
            self.stream.release.set()
        await self.client.aclose()
        await self.upstream.aclose()

    async def new_session(self):
        response = await self.client.post("/api/v1/chat/sessions")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["session_id"]

    async def ask(self, session_id, message="안녕하세요", request_id=None, **extra):
        return await self.client.post(f"/api/v1/chat/sessions/{session_id}/messages", json={
            "message": message, "request_id": request_id or str(uuid4()), **extra})

    def assert_completed(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        result = events(response)
        self.assertEqual([data["status"] for event, data in result if event == "done"], ["completed"])
        self.assertEqual("".join(data["text"] for event, data in result if event == "delta"), "모의 답변")
        return next(data for event, data in result if event == "meta")

    def collect_sdk_spans(self):
        """Use the pinned SDK and its real processor; replace only network export."""
        from langfuse import Langfuse
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        with patch("langfuse._client.span_processor.OTLPSpanExporter", return_value=exporter):
            sdk = Langfuse(public_key=f"mock-public-{uuid4()}", secret_key="mock-secret",
                           base_url="http://mock-langfuse.test", tracer_provider=provider)
        self.addCleanup(sdk.shutdown)
        self.service.telemetry = ChatTelemetry(self.settings, client=sdk)

        def collected():
            provider.force_flush()
            return exporter.get_finished_spans()

        return collected

    async def test_two_turns_keep_session_and_send_real_history(self):
        session_id = await self.new_session()
        first = self.assert_completed(await self.ask(session_id, "첫 질문"))
        second = self.assert_completed(await self.ask(session_id, "후속 질문"))
        self.assertEqual(first["session_id"], session_id)
        self.assertEqual(second["session_id"], session_id)
        # A disabled collector must not invent a Langfuse trace identifier.
        self.assertIsNone(first["trace_id"])
        self.assertIsNone(second["trace_id"])
        self.assertEqual([item for item in self.calls[-1]["body"]["messages"] if item["role"] != "system"], [
            {"role": "user", "content": "첫 질문"},
            {"role": "assistant", "content": "모의 답변"},
            {"role": "user", "content": "후속 질문"},
        ])
        self.assertEqual(self.calls[-1]["body"]["model"], MODEL)
        self.assertTrue(self.calls[-1]["body"]["stream"])
        self.assertEqual(self.calls[-1]["body"]["stream_options"], {"include_usage": True})
        self.assertEqual(self.calls[-1]["headers"]["authorization"], f"Bearer {PRIVATE_KEY}")

    async def test_new_conversation_has_new_server_id_and_no_old_history(self):
        first = await self.new_session()
        self.assert_completed(await self.ask(first, "old question"))
        second = await self.new_session()
        self.assertNotEqual(first, second)
        self.assert_completed(await self.ask(second, "new question"))
        messages = [item for item in self.calls[-1]["body"]["messages"] if item["role"] != "system"]
        self.assertEqual(messages, [{"role": "user", "content": "new question"}])

    async def test_other_user_cannot_read_or_stop_session(self):
        session_id = await self.new_session()
        self.admin = SimpleNamespace(id=202, username="user-b", is_active=True)
        response = await self.ask(session_id)
        self.assertIn(response.status_code, (403, 404), response.text)
        response = await self.client.post(f"/api/v1/chat/sessions/{session_id}/stop", json={"request_id": str(uuid4())})
        self.assertIn(response.status_code, (403, 404), response.text)
        self.assertEqual(self.calls, [])
        own_session = await self.new_session()
        self.assert_completed(await self.ask(own_session))

    async def test_client_cannot_override_authenticated_identity(self):
        session_id = await self.new_session()
        for field in ("user_id", "username"):
            response = await self.ask(session_id, **{field: "user-b"})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.calls, [])

    async def test_authentication_is_required(self):
        self.app.dependency_overrides.clear()
        response = await self.client.post("/api/v1/chat/sessions")
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(self.calls, [])

    async def test_disable_setting_hides_feature_and_blocks_all_chat_endpoints(self):
        session_id = await self.new_session()
        self.settings.demo_chat_enabled = False
        public = (await self.client.get("/api/v1/config/product")).json()
        self.assertNotIn("demo_chat", public["features"])
        responses = [
            await self.client.post("/api/v1/chat/sessions"),
            await self.ask(session_id),
            await self.client.post(f"/api/v1/chat/sessions/{session_id}/stop", json={"request_id": str(uuid4())}),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.calls, [])

    async def test_shared_chat_preserves_company_and_kac_profiles_and_uses_supplied_connection(self):
        cases = [
            ("profile", "http://company-model.test:8001/v1", "configured-company-model"),
            ("kac", "http://delivery-model.test:8100/v1", "configured-delivery-model"),
        ]
        for scope, base_url, model in cases:
            with self.subTest(monitoring_scope=scope):
                self.settings.monitoring_scope = scope
                self.settings.vllm_api_base_url = base_url
                self.settings.vllm_model = model
                self.settings.demo_chat_enabled = False
                baseline = (await self.client.get("/api/v1/config/product")).json()
                self.settings.demo_chat_enabled = True
                enabled = (await self.client.get("/api/v1/config/product")).json()
                self.assertEqual(enabled, {**baseline, "features": baseline["features"] + ["demo_chat"]})

                self.app.dependency_overrides.clear()
                self.assertEqual((await self.client.post("/api/v1/chat/sessions")).status_code, 401)
                self.app.dependency_overrides[get_current_active_admin] = lambda: self.admin
                self.admin = SimpleNamespace(id=101, username="user-a", is_active=True)
                session_id = await self.new_session()
                self.assert_completed(await self.ask(session_id))
                self.assertEqual(self.calls[-1]["url"], base_url + "/chat/completions")
                self.assertEqual(self.calls[-1]["body"]["model"], model)

                call_count = len(self.calls)
                self.admin = SimpleNamespace(id=202, username="user-b", is_active=True)
                self.assertEqual((await self.ask(session_id)).status_code, 404)
                response = await self.client.post(f"/api/v1/chat/sessions/{session_id}/stop",
                                                  json={"request_id": str(uuid4())})
                self.assertEqual(response.status_code, 404)
                self.assertEqual(len(self.calls), call_count)

    async def test_model_is_discovered_when_config_is_blank(self):
        self.settings.vllm_model = ""
        session_id = await self.new_session()
        self.assert_completed(await self.ask(session_id))
        self.assertEqual([call["path"] for call in self.calls], ["/v1/models", "/v1/chat/completions"])
        self.assertEqual(self.calls[-1]["body"]["model"], MODEL)

    async def test_ambiguous_model_discovery_does_not_choose_arbitrary_model(self):
        self.settings.vllm_model = ""
        self.model_ids = ["real-model-a", "real-model-b"]
        response = await self.ask(await self.new_session())
        result = events(response)
        self.assertEqual([data["status"] for event, data in result if event == "done"], ["error"])
        self.assertTrue(any(event == "error" for event, _ in result))
        self.assertEqual([call["path"] for call in self.calls], ["/v1/models"])

    async def test_upstream_error_body_and_credentials_are_not_disclosed(self):
        self.generation_status = 500
        self.generation_body = json.dumps({"error": f"upstream stack trace: {PRIVATE_KEY}"}).encode()
        response = await self.ask(await self.new_session())
        result = events(response)
        self.assertEqual([data["status"] for event, data in result if event == "done"], ["error"])
        self.assertTrue(any(event == "error" for event, _ in result))
        self.assertNotIn(PRIVATE_KEY, response.text)
        self.assertNotIn("upstream stack trace", response.text)

    async def test_timeout_finishes_with_safe_error(self):
        self.transport_exception = httpx.ReadTimeout(f"internal {PRIVATE_KEY}")
        response = await self.ask(await self.new_session())
        result = events(response)
        self.assertEqual([data["status"] for event, data in result if event == "done"], ["error"])
        self.assertNotIn(PRIVATE_KEY, response.text)

    async def test_stop_interrupts_waiting_model_and_closes_upstream(self):
        self.stream = PausedModelStream()
        session_id = await self.new_session()
        request_id = str(uuid4())
        pending = asyncio.create_task(self.ask(session_id, request_id=request_id))
        try:
            await asyncio.wait_for(self.stream.waiting.wait(), timeout=3)
            response = await self.client.post(f"/api/v1/chat/sessions/{session_id}/stop", json={"request_id": request_id})
            self.assertEqual(response.status_code, 200, response.text)
            result = events(await asyncio.wait_for(pending, timeout=3))
            self.assertEqual([data["status"] for event, data in result if event == "done"], ["cancelled"])
            self.assertTrue(self.stream.closed)
        finally:
            self.stream.release.set()
            if not pending.done():
                pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)

    async def test_second_request_cannot_overlap_and_stale_stop_cannot_cancel_active_turn(self):
        self.stream = PausedModelStream()
        session_id = await self.new_session()
        request_id = str(uuid4())
        pending = asyncio.create_task(self.ask(session_id, request_id=request_id))
        try:
            await asyncio.wait_for(self.stream.waiting.wait(), timeout=3)
            response = await self.ask(session_id, "another overlapping question")
            self.assertEqual(response.status_code, 409, response.text)
            await self.client.post(f"/api/v1/chat/sessions/{session_id}/stop", json={"request_id": str(uuid4())})
            await asyncio.sleep(0)
            self.assertFalse(pending.done())
            self.stream.release.set()
            response = await asyncio.wait_for(pending, timeout=3)
            self.assertEqual([data["status"] for event, data in events(response) if event == "done"], ["completed"])
        finally:
            self.stream.release.set()
            if not pending.done():
                pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)

    async def test_browser_disconnect_closes_model_and_releases_session(self):
        self.stream = PausedModelStream()
        paused = self.stream
        session_id = await self.new_session()
        body = json.dumps({"message": "disconnect this turn", "request_id": str(uuid4())}).encode()
        path = f"/api/v1/chat/sessions/{session_id}/messages"
        received_body = False
        sent = []

        async def receive():
            nonlocal received_body
            if not received_body:
                received_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            await paused.waiting.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            "server": ("test", 80), "client": ("127.0.0.1", 1234),
        }
        try:
            await asyncio.wait_for(self.app(scope, receive, send), timeout=3)
            self.assertTrue(paused.closed)
            self.assertEqual(next(item["status"] for item in sent if item["type"] == "http.response.start"), 200)
            self.stream = None
            self.assert_completed(await self.ask(session_id, "new turn after disconnect"))
        finally:
            paused.release.set()

    async def test_real_sdk_records_users_sessions_unique_trace_trees_timing_and_usage(self):
        collected = self.collect_sdk_spans()
        session_a = await self.new_session()
        first = self.assert_completed(await self.ask(session_a, "A first"))
        second = self.assert_completed(await self.ask(session_a, "A second"))
        fresh_a = await self.new_session()
        third = self.assert_completed(await self.ask(fresh_a, "A new conversation"))
        self.admin = SimpleNamespace(id=202, username="user-b", is_active=True)
        session_b = await self.new_session()
        fourth = self.assert_completed(await self.ask(session_b, "B first"))
        spans = collected()
        roots = [span for span in spans if span.name == "chat.request"]
        self.assertEqual(len(roots), 4)
        root_inputs = {int(meta["trace_id"], 16): question for meta, question in (
            (first, "A first"), (second, "A second"), (third, "A new conversation"), (fourth, "B first"))}
        self.assertEqual(len({root.context.trace_id for root in roots}), 4)
        self.assertEqual({format(root.context.trace_id, "032x") for root in roots},
                         {item["trace_id"] for item in (first, second, third, fourth)})
        self.assertEqual([(root.attributes["user.id"], root.attributes["session.id"]) for root in roots], [
            ("101", session_a), ("101", session_a), ("101", fresh_a), ("202", session_b)])
        for root in roots:
            self.assertIsNone(root.parent)
            self.assertEqual(root.attributes["langfuse.trace.name"], "chat.request")
            self.assertEqual(root.attributes["langfuse.observation.input"], root_inputs[root.context.trace_id])
            self.assertEqual(root.attributes["langfuse.observation.output"], "모의 답변")
            self.assertFalse(any(key.startswith(("langfuse.trace.input", "langfuse.trace.output"))
                                 for key in root.attributes))
            tree = [span for span in spans if span.context.trace_id == root.context.trace_id]
            names = {span.name for span in tree}
            self.assertTrue({"chat.request", "history.prepare", "prompt.build", "vllm.generate"} <= names, names)
            self.assertFalse(any("rag" in name.lower() or "search" in name.lower() or "reasoning" in name.lower()
                                 for name in names))
            for span in tree:
                self.assertEqual(span.attributes["user.id"], root.attributes["user.id"])
                self.assertEqual(span.attributes["session.id"], root.attributes["session.id"])
                self.assertGreaterEqual(span.start_time, root.start_time)
                self.assertGreaterEqual(span.end_time, span.start_time)
                self.assertLessEqual(span.end_time, root.end_time)
                self.assertEqual(span.attributes["langfuse.trace.name"], "chat.request")
                self.assertEqual(json.loads(span.attributes["langfuse.observation.metadata.status"]), "completed")
                if span is not root:
                    self.assertEqual(span.parent.span_id, root.context.span_id)
            generation = next(span for span in tree if span.name == "vllm.generate")
            # Conversation text is stored once (generation input); the two
            # preparation spans carry only message and character counts.
            sent = json.loads(generation.attributes["langfuse.observation.input"])
            self.assertEqual(sent[-1], {"role": "user", "content": root_inputs[root.context.trace_id]})
            size = {"messages": len(sent), "chars": sum(len(item["content"]) for item in sent)}
            history = next(span for span in tree if span.name == "history.prepare")
            prompt = next(span for span in tree if span.name == "prompt.build")
            self.assertEqual(json.loads(history.attributes["langfuse.observation.output"]),
                             {"messages": size["messages"] - 1, "chars": size["chars"] - len(sent[-1]["content"])})
            self.assertEqual(json.loads(prompt.attributes["langfuse.observation.output"]), size)
            for span in (history, prompt):
                recorded = span.attributes["langfuse.observation.input"] + span.attributes["langfuse.observation.output"]
                self.assertNotIn("content", recorded)
                self.assertNotIn(root_inputs[root.context.trace_id], recorded)
            self.assertIn("langfuse.observation.completion_start_time", generation.attributes)
            self.assertEqual(generation.attributes["langfuse.observation.type"], "generation")
            self.assertEqual(generation.attributes["langfuse.observation.model.name"], MODEL)
            self.assertEqual(json.loads(generation.attributes["langfuse.observation.output"]),
                             {"role": "assistant", "content": "모의 답변"})
            self.assertIn("langfuse.observation.input", generation.attributes)
            self.assertEqual(json.loads(generation.attributes["langfuse.observation.usage_details"]),
                             {"input": 12, "output": 3, "total": 15})
            self.assertFalse(any("cost" in key for key in generation.attributes))
        self.assertNotIn(PRIVATE_KEY, repr([dict(span.attributes) for span in spans]))
        # Login names never reach the collector; only the internal account id does.
        self.assertNotIn("user-a", repr([dict(span.attributes) for span in spans]))
        self.assertNotIn("user-b", repr([dict(span.attributes) for span in spans]))

    async def test_real_sdk_missing_usage_does_not_invent_tokens_or_cost(self):
        collected = self.collect_sdk_spans()
        self.generation_body = (sse_packet({"model": MODEL, "choices": [{"delta": {"content": "모의 답변"}}]})
                                + b"data: [DONE]\n\n")
        self.assert_completed(await self.ask(await self.new_session()))
        generation = next(span for span in collected() if span.name == "vllm.generate")
        self.assertNotIn("langfuse.observation.usage_details", generation.attributes)
        self.assertFalse(any("cost" in key for key in generation.attributes))

    async def test_real_sdk_error_ends_generation_and_trace_without_secret_body(self):
        collected = self.collect_sdk_spans()
        await self.test_upstream_error_body_and_credentials_are_not_disclosed()
        spans = collected()
        for name in ("chat.request", "vllm.generate"):
            span = next(span for span in spans if span.name == name)
            self.assertEqual(json.loads(span.attributes["langfuse.observation.metadata.status"]), "error")
            self.assertEqual(span.attributes["langfuse.observation.level"], "ERROR")
            self.assertIsNotNone(span.end_time)
        self.assertNotIn(PRIVATE_KEY, repr([dict(span.attributes) for span in spans]))
        self.assertNotIn("upstream stack trace", repr([dict(span.attributes) for span in spans]))

    async def test_real_sdk_cancel_ends_generation_and_trace(self):
        collected = self.collect_sdk_spans()
        await self.test_stop_interrupts_waiting_model_and_closes_upstream()
        spans = collected()
        for name in ("chat.request", "vllm.generate"):
            span = next(span for span in spans if span.name == name)
            self.assertEqual(json.loads(span.attributes["langfuse.observation.metadata.status"]), "cancelled")
            self.assertEqual(span.attributes["langfuse.observation.level"], "WARNING")
            self.assertIsNotNone(span.end_time)

    async def test_langfuse_collection_exception_does_not_break_chat(self):
        class UnavailableCollector:
            def start_observation(self, **kwargs):
                raise RuntimeError(f"collector unavailable: {PRIVATE_KEY}")

        self.service.telemetry = ChatTelemetry(self.settings, client=UnavailableCollector())
        with self.assertLogs("app.services.chat_telemetry", level="WARNING") as output:
            self.assert_completed(await self.ask(await self.new_session()))
        self.assertNotIn(PRIVATE_KEY, "\n".join(output.output))

    async def test_stop_before_producer_is_scheduled_terminates_without_model_call(self):
        collected = self.collect_sdk_spans()
        session = self.service.create_session(self.admin.id)
        run = self.service.begin(session, str(uuid4()), "stop immediately")
        self.service.stop(session, run.request_id)

        async def consume():
            return [packet async for packet in self.service.events(run)]

        try:
            packets = await asyncio.wait_for(consume(), timeout=2)
            response = httpx.Response(200, text="".join(packets))
            self.assertEqual([data["status"] for event, data in events(response) if event == "done"], ["cancelled"])
            self.assertEqual(self.calls, [])
            self.assertIsNone(session.active)
            roots = [span for span in collected() if span.name == "chat.request"]
            self.assertEqual(len(roots), 1)
            self.assertEqual(json.loads(roots[0].attributes["langfuse.observation.metadata.status"]), "cancelled")
        finally:
            await self.service.disconnect(session, run)

    async def test_backend_dotenv_drives_vllm_request_and_sdk_initialization(self):
        values = {
            "DEMO_CHAT_ENABLED": "true",
            "VLLM_API_BASE_URL": "http://configured-model.test:8001/v1",
            "VLLM_MODEL": "actual-configured-model",
            "VLLM_API_KEY": "configured-private-api-key",
            "VLLM_TIMEOUT_SECONDS": "8.5",
            "LANGFUSE_BASE_URL": "http://configured-collector.test:3000",
            "LANGFUSE_PUBLIC_KEY": "configured-public-key",
            "LANGFUSE_SECRET_KEY": "configured-private-sdk-key",
            "LANGFUSE_TRACING_ENABLED": "true",
            "TRACE_URL": "http://browser-iframe.test/trace",
        }
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            env = Path(directory) / ".env.backend"
            env.write_text("\n".join(f"{key}={value}" for key, value in values.items()))
            configured = Settings(_env_file=env)
        with patch("langfuse.Langfuse") as constructor:
            constructor.return_value.start_observation.return_value = None
            telemetry = ChatTelemetry(configured)
            sdk_args = constructor.call_args.kwargs
            self.assertEqual(sdk_args["base_url"], values["LANGFUSE_BASE_URL"])
            self.assertEqual(sdk_args["public_key"], values["LANGFUSE_PUBLIC_KEY"])
            self.assertEqual(sdk_args["secret_key"], values["LANGFUSE_SECRET_KEY"])
            self.assertTrue(sdk_args["tracing_enabled"])
            self.assertNotEqual(sdk_args["base_url"], configured.trace_url)
            self.service = ChatService(configured, client=self.upstream, telemetry=telemetry)
            self.app.state.demo_chat = self.service
            self.assert_completed(await self.ask(await self.new_session()))
        call = self.calls[-1]
        self.assertEqual(call["url"], values["VLLM_API_BASE_URL"] + "/chat/completions")
        self.assertEqual(call["body"]["model"], values["VLLM_MODEL"])
        self.assertEqual(call["headers"]["authorization"], "Bearer " + values["VLLM_API_KEY"])
        self.assertEqual(set(call["timeout"].values()), {8.5})

    async def test_concurrent_users_do_not_share_trace_context(self):
        collected = self.collect_sdk_spans()
        paused = PausedModelStream()
        self.stream = paused
        session_a = await self.new_session()
        pending_a = asyncio.create_task(self.ask(session_a, "A waiting"))
        try:
            await asyncio.wait_for(paused.waiting.wait(), timeout=3)
            self.admin = SimpleNamespace(id=202, username="user-b", is_active=True)
            self.stream = None
            session_b = await self.new_session()
            self.assert_completed(await self.ask(session_b, "B while A is streaming"))
            paused.release.set()
            response_a = await asyncio.wait_for(pending_a, timeout=3)
            self.assertEqual([data["status"] for event, data in events(response_a) if event == "done"], ["completed"])
            spans = collected()
            roots = [span for span in spans if span.name == "chat.request"]
            self.assertEqual(len(roots), 2)
            self.assertEqual(len({root.context.trace_id for root in roots}), 2)
            expected_users = {session_a: "101", session_b: "202"}
            for root in roots:
                expected_user = expected_users[root.attributes["session.id"]]
                self.assertEqual(root.attributes["langfuse.trace.name"], "chat.request")
                tree = [span for span in spans if span.context.trace_id == root.context.trace_id]
                for span in tree:
                    self.assertEqual(span.attributes["user.id"], expected_user)
                    self.assertEqual(span.attributes["session.id"], root.attributes["session.id"])
                    if span is not root:
                        self.assertEqual(span.parent.span_id, root.context.span_id)
        finally:
            paused.release.set()
            if not pending_a.done():
                pending_a.cancel()
            await asyncio.gather(pending_a, return_exceptions=True)

    async def test_stop_then_disconnect_does_not_interrupt_upstream_cleanup(self):
        self.stream = SlowClosingModelStream()
        session = self.service.create_session(self.admin.id)
        run = self.service.begin(session, str(uuid4()), "cancel while closing")
        disconnect = None
        try:
            await asyncio.wait_for(self.stream.waiting.wait(), timeout=3)
            self.service.stop(session, run.request_id)
            await asyncio.wait_for(self.stream.closing.wait(), timeout=3)
            disconnect = asyncio.create_task(self.service.disconnect(session, run))
            await asyncio.sleep(0)
            self.assertFalse(disconnect.done())
            self.stream.close_release.set()
            await asyncio.wait_for(disconnect, timeout=3)
            self.assertTrue(self.stream.closed)
            self.assertTrue(run.task.done())
            self.assertIsNone(session.active)
        finally:
            self.stream.close_release.set()
            self.stream.release.set()
            if disconnect is not None:
                await asyncio.gather(disconnect, return_exceptions=True)
            await self.service.disconnect(session, run)

    async def test_model_discovery_deadline_records_error_instead_of_user_cancellation(self):
        collected = self.collect_sdk_spans()
        self.settings.vllm_model = ""
        self.settings.vllm_timeout_seconds = 0.02
        self.model_delay = 2
        response = await self.ask(await self.new_session())
        result = events(response)
        self.assertEqual([data["status"] for event, data in result if event == "done"], ["error"])
        self.assertEqual([data["code"] for event, data in result if event == "error"], ["timeout"])
        spans = collected()
        for name in ("chat.request", "model.resolve"):
            span = next(span for span in spans if span.name == name)
            self.assertEqual(json.loads(span.attributes["langfuse.observation.metadata.status"]), "error")
            self.assertEqual(span.attributes["langfuse.observation.level"], "ERROR")
        self.assertFalse(any(span.name == "vllm.generate" for span in spans))

    async def test_shutdown_finds_producer_blocked_on_terminal_event(self):
        class FullQueueStream(PausedModelStream):
            def __init__(self):
                super().__init__()
                self.finished = asyncio.Event()

            async def __aiter__(self):
                # Together with meta, exactly fill the bounded delivery queue.
                for _ in range(31):
                    yield sse_packet({"choices": [{"delta": {"content": "token"}}]})
                yield b"data: [DONE]\n\n"

            async def aclose(self):
                self.closed = True
                self.finished.set()

        self.stream = FullQueueStream()
        session = self.service.create_session(self.admin.id)
        run = self.service.begin(session, str(uuid4()), "browser has stopped reading")
        try:
            await asyncio.wait_for(self.stream.finished.wait(), timeout=3)
            self.assertTrue(run.queue.full())
            self.assertFalse(run.task.done())
            self.assertIs(session.active, run)
            await asyncio.wait_for(self.service.aclose(), timeout=3)
            self.assertTrue(run.task.done())
            self.assertIsNone(session.active)
        finally:
            await self.service.disconnect(session, run)


if __name__ == "__main__":
    unittest.main()

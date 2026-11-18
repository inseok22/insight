"""Best-effort Langfuse v5 observations with explicit parents across SSE tasks.

No active context is kept across an async generator yield. Each observation owns
its SDK handle, so concurrent requests, cancellation and streaming cannot reparent
another request's generation. Trace attributes (user, session, trace name) are
propagated only while a span is being created, inside a fresh OpenTelemetry
context, so they reach the root and every child even when the child is created
in another asyncio task. Only application payloads enter the SDK, never HTTP
headers, credentials or upstream exception bodies.
"""
from contextlib import contextmanager
import logging
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)

TRACE_NAME = "chat.request"


class Observation:
    def __init__(self, telemetry, handle=None, *, user_id="", session_id="", root=False):
        self.telemetry = telemetry
        self.handle = handle
        self.user_id = user_id
        self.session_id = session_id
        self.root = root
        self.ended = False
        self.trace_id = getattr(handle, "trace_id", None)

    def _call(self, method, **kwargs):
        if self.handle is None:
            return None
        try:
            return getattr(self.handle, method)(**self.telemetry.scrub(kwargs))
        except Exception:
            # Never log exception strings: SDK/network errors can contain secrets.
            logger.warning("Demo chat telemetry operation failed (%s)", method)
            return None

    def child(self, name: str, *, generation=False, **kwargs):
        handle = None
        if self.handle is not None:
            try:
                with self.telemetry.attributes(self.user_id, self.session_id):
                    handle = self.handle.start_observation(
                        as_type="generation" if generation else "span", name=name,
                        **self.telemetry.scrub(kwargs))
            except Exception:
                logger.warning("Demo chat telemetry operation failed (start_observation)")
        return Observation(self.telemetry, handle, user_id=self.user_id, session_id=self.session_id)

    def update(self, **kwargs):
        self._call("update", **kwargs)

    def finish(self, status: str, *, output=None, error_code=None, **kwargs):
        if self.ended:
            return
        self.ended = True
        metadata = {"status": status}
        if error_code:
            metadata["error_code"] = error_code
        # Trace input/output mirror the root observation; no trace-level update.
        self.update(output=output, metadata=metadata,
                    level="ERROR" if status == "error" else "WARNING" if status == "cancelled" else "DEFAULT",
                    status_message=error_code or status, **kwargs)
        self._call("end")


class ChatTelemetry:
    def __init__(self, settings: Settings, client=None):
        self.client = client
        self.secrets = tuple(value for value in (
            settings.vllm_api_key, settings.langfuse_secret_key, settings.langfuse_public_key,
            settings.secret_key, settings.initial_admin_password,
        ) if value and value not in {"admin", "change-me", "change-me-in-production"})
        if client is not None or not settings.langfuse_tracing_enabled:
            return
        if not all((settings.langfuse_base_url, settings.langfuse_public_key, settings.langfuse_secret_key)):
            logger.warning("Demo chat tracing disabled: Langfuse connection settings are incomplete")
            return
        try:
            from langfuse import Langfuse
            from opentelemetry.sdk.trace import TracerProvider

            # A dedicated provider collects only these explicitly created demo spans.
            self.client = Langfuse(
                base_url=settings.langfuse_base_url,
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                tracing_enabled=True, debug=False, timeout=5,
                flush_at=32, flush_interval=1,
                tracer_provider=TracerProvider(),
            )
        except Exception:
            logger.warning("Demo chat tracing initialization failed; chat remains available")

    def scrub(self, value: Any):
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, dict):
            return {key: self.scrub(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.scrub(item) for item in value]
        return value

    @contextmanager
    def attributes(self, user_id: str, session_id: str):
        """Propagate trace attributes to spans created inside this block only.

        The fresh Context keeps an inbound traceparent header or another active
        instrumentation span from becoming the parent or receiving these values.
        """
        from langfuse import propagate_attributes
        from opentelemetry.context import Context, attach, detach

        token = attach(Context())
        try:
            with propagate_attributes(user_id=user_id, session_id=session_id, trace_name=TRACE_NAME):
                yield
        finally:
            detach(token)

    def start(self, *, user_id: str, session_id: str, message: str):
        handle = None
        if self.client is not None:
            try:
                # Every submitted question is a fresh root trace.
                with self.attributes(user_id, session_id):
                    handle = self.client.start_observation(
                        as_type="span", name=TRACE_NAME, input=self.scrub(message))
            except Exception:
                logger.warning("Demo chat trace creation failed; chat remains available")
        return Observation(self, handle, user_id=user_id, session_id=session_id, root=True)

    def shutdown(self):
        if self.client is not None:
            try:
                self.client.shutdown()
            except Exception:
                logger.warning("Demo chat telemetry shutdown failed")

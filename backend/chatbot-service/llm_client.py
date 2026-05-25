"""
LLM provider adapters with inference logging.
Supports sync completions, streaming completions, provider fallback, and Redis
Streams-based log publishing.
"""
import json
import re
import secrets
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Generator, Iterable, List, Optional, Tuple

import redis
from groq import Groq
from openai import OpenAI

from config import settings


class ProviderAdapter(ABC):
    """Provider-neutral chat completion adapter."""

    name: str

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def complete(self, messages: List[Dict[str, str]], max_tokens: int) -> Tuple[str, Dict[str, int]]:
        """Return the full assistant response and token usage."""

    @abstractmethod
    def stream(self, messages: List[Dict[str, str]], max_tokens: int) -> Iterable[str]:
        """Yield assistant response chunks."""


class MockAdapter(ProviderAdapter):
    name = "mock"

    def complete(self, messages: List[Dict[str, str]], max_tokens: int) -> Tuple[str, Dict[str, int]]:
        response = self._mock_completion(messages)
        prompt_tokens = sum(LoggingLLMClient.estimate_tokens(msg.get("content", "")) for msg in messages)
        completion_tokens = LoggingLLMClient.estimate_tokens(response)
        return response, {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    def stream(self, messages: List[Dict[str, str]], max_tokens: int) -> Iterable[str]:
        for word in self._mock_completion(messages).split(" "):
            yield word + " "

    @staticmethod
    def _mock_completion(messages: List[Dict[str, str]]) -> str:
        last_user_message = next(
            (msg.get("content", "") for msg in reversed(messages) if msg.get("role") == "user"),
            ""
        )
        short_context = len([msg for msg in messages if msg.get("role") in {"user", "assistant"}])
        return (
            "Demo response from the local mock provider. "
            f"I received your message: \"{LoggingLLMClient._truncate_text(last_user_message, 140)}\". "
            f"This conversation currently has {short_context} contextual messages."
        )


class OpenAIAdapter(ProviderAdapter):
    name = "openai"

    def __init__(self, model: str):
        super().__init__(model)
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**client_kwargs)

    def complete(self, messages: List[Dict[str, str]], max_tokens: int) -> Tuple[str, Dict[str, int]]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=False,
        )
        response_text = response.choices[0].message.content or ""
        usage = response.usage
        return response_text, {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }

    def stream(self, messages: List[Dict[str, str]], max_tokens: int) -> Iterable[str]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta


class GroqAdapter(ProviderAdapter):
    name = "groq"

    def __init__(self, model: str):
        super().__init__(model)
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        self.client = Groq(api_key=settings.groq_api_key)

    def complete(self, messages: List[Dict[str, str]], max_tokens: int) -> Tuple[str, Dict[str, int]]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=False,
        )
        response_text = response.choices[0].message.content or ""
        usage = response.usage
        return response_text, {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }

    def stream(self, messages: List[Dict[str, str]], max_tokens: int) -> Iterable[str]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta


ADAPTERS = {
    "mock": MockAdapter,
    "openai": OpenAIAdapter,
    "groq": GroqAdapter,
}


class LoggingLLMClient:
    """Provider wrapper that captures inference metadata and publishes log events."""

    def __init__(self):
        self.model = settings.default_model
        self.adapters = self._build_adapters()
        if not self.adapters:
            raise ValueError("No usable LLM providers are configured")
        self.provider = self.adapters[0].name
        self.redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def _build_adapters(self) -> list[ProviderAdapter]:
        adapters: list[ProviderAdapter] = []
        errors: list[str] = []
        for provider in settings.provider_order:
            adapter_cls = ADAPTERS.get(provider)
            if not adapter_cls:
                errors.append(f"{provider}: unsupported provider")
                continue
            try:
                adapters.append(adapter_cls(self.model))
            except Exception as exc:
                errors.append(f"{provider}: {exc}")
        if not adapters and errors:
            raise ValueError("; ".join(errors))
        return adapters

    def chat_completion(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        message_id: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        """Execute a non-streaming chat completion with provider fallback."""
        if not message_id:
            message_id = secrets.token_urlsafe(16)

        last_error: Optional[Exception] = None
        for adapter in self.adapters:
            try:
                response_text, metadata = self._complete_with_adapter(adapter, conversation_id, messages, message_id)
                return response_text, metadata
            except Exception as exc:
                last_error = exc
                self._publish_error_log(adapter, conversation_id, messages, message_id, exc)

        raise last_error or RuntimeError("No provider completed the request")

    def stream_chat_completion(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        message_id: Optional[str] = None,
    ) -> Generator[Tuple[str, Optional[Dict]], None, None]:
        """Yield response chunks and finally metadata. Falls back before first chunk."""
        if not message_id:
            message_id = secrets.token_urlsafe(16)

        last_error: Optional[Exception] = None
        for adapter in self.adapters:
            output_parts: list[str] = []
            request_timestamp = datetime.utcnow().isoformat()
            start_time = time.perf_counter()
            try:
                for chunk in adapter.stream(messages, settings.max_tokens):
                    output_parts.append(chunk)
                    yield chunk, None

                response_text = "".join(output_parts)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                prompt_tokens = sum(self.estimate_tokens(msg.get("content", "")) for msg in messages)
                completion_tokens = self.estimate_tokens(response_text)
                metadata = self._build_metadata(
                    adapter=adapter,
                    conversation_id=conversation_id,
                    messages=messages,
                    message_id=message_id,
                    request_timestamp=request_timestamp,
                    latency_ms=latency_ms,
                    status="success",
                    response_text=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                )
                self._publish_log_event(metadata)
                yield "", metadata
                return
            except Exception as exc:
                last_error = exc
                self._publish_error_log(adapter, conversation_id, messages, message_id, exc, request_timestamp, start_time)
                if output_parts:
                    raise

        raise last_error or RuntimeError("No provider completed the request")

    def _complete_with_adapter(
        self,
        adapter: ProviderAdapter,
        conversation_id: str,
        messages: List[Dict[str, str]],
        message_id: str,
    ) -> Tuple[str, Dict]:
        request_timestamp = datetime.utcnow().isoformat()
        start_time = time.perf_counter()
        response_text, usage = adapter.complete(messages, settings.max_tokens)
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        metadata = self._build_metadata(
            adapter=adapter,
            conversation_id=conversation_id,
            messages=messages,
            message_id=message_id,
            request_timestamp=request_timestamp,
            latency_ms=latency_ms,
            status="success",
            response_text=response_text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
        self._publish_log_event(metadata)
        return response_text, metadata

    def _publish_error_log(
        self,
        adapter: ProviderAdapter,
        conversation_id: str,
        messages: List[Dict[str, str]],
        message_id: str,
        exc: Exception,
        request_timestamp: Optional[str] = None,
        start_time: Optional[float] = None,
    ) -> None:
        metadata = self._build_metadata(
            adapter=adapter,
            conversation_id=conversation_id,
            messages=messages,
            message_id=message_id,
            request_timestamp=request_timestamp or datetime.utcnow().isoformat(),
            latency_ms=int((time.perf_counter() - start_time) * 1000) if start_time else 0,
            status="error",
            response_text="",
            error_message=str(exc)[:1000],
        )
        self._publish_log_event(metadata)

    def _build_metadata(
        self,
        adapter: ProviderAdapter,
        conversation_id: str,
        messages: List[Dict[str, str]],
        message_id: str,
        request_timestamp: str,
        latency_ms: int,
        status: str,
        response_text: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        error_message: Optional[str] = None,
    ) -> Dict:
        return {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "provider": adapter.name,
            "model": adapter.model,
            "request_timestamp": request_timestamp,
            "response_timestamp": datetime.utcnow().isoformat(),
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "status": status,
            "error_message": error_message,
            "input_preview": self._safe_preview(messages[-1].get("content", ""), 200) if messages else None,
            "output_preview": self._safe_preview(response_text, 200) if response_text else None,
        }

    def _publish_log_event(self, metadata: Dict) -> None:
        """Publish a structured inference log to Redis Streams."""
        payload = json.dumps(metadata)
        try:
            self.redis_client.xadd(settings.inference_log_stream, {"payload": payload}, maxlen=10000, approximate=True)
        except Exception as exc:
            print(f"Failed to publish inference log event: {exc}")

    @staticmethod
    def _truncate_text(text: str, max_length: int) -> str:
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    @classmethod
    def _safe_preview(cls, text: str, max_length: int) -> str:
        redacted = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[redacted-email]', text or "")
        redacted = re.sub(r'\b(?:\+?\d[\d\s().-]{7,}\d)\b', '[redacted-phone]', redacted)
        redacted = re.sub(r'\b(?:\d[ -]*?){13,16}\b', '[redacted-card]', redacted)
        return cls._truncate_text(redacted, max_length)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimation for local accounting."""
        return len(text) // 4

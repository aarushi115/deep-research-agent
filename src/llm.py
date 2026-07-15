"""Groq LLM client construction and retry helpers.

Groq's free tier has tighter rate limits than paid OpenAI, and the graph
fans out multiple parallel LLM calls at once, so every structured-output
call is wrapped in exponential-backoff retry logic.
"""

from functools import lru_cache
from typing import TypeVar

from langchain_groq import ChatGroq
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings
from src.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# Broad on purpose: Groq/httpx raise a mix of RateLimitError, APIError,
# APIConnectionError, and timeout exceptions depending on failure mode.
_RETRYABLE_EXCEPTIONS = (Exception,)


@lru_cache
def get_llm() -> ChatGroq:
    """Return a cached ChatGroq instance configured from settings."""
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=settings.groq_temperature,
    )


def _log_retry(retry_state) -> None:
    exc = retry_state.outcome.exception()
    logger.warning(
        "LLM call failed (attempt %d): %s — retrying",
        retry_state.attempt_number,
        exc,
    )


def call_structured(prompt: str, schema: type[T], *, system: str | None = None) -> T:
    """Call the LLM with a prompt and parse the response into `schema`.

    Retries with exponential backoff on any exception (rate limits,
    transient network errors, malformed tool-call responses).
    """
    settings = get_settings()

    @retry(
        stop=stop_after_attempt(settings.max_llm_retries),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        before_sleep=_log_retry,
        reraise=True,
    )
    def _invoke() -> T:
        llm = get_llm().with_structured_output(schema)
        messages = []
        if system:
            messages.append(("system", system))
        messages.append(("human", prompt))
        result = llm.invoke(messages)
        if not isinstance(result, schema):
            raise ValueError(f"LLM returned unexpected type: {type(result)}")
        return result

    return _invoke()


def call_text(prompt: str, *, system: str | None = None) -> str:
    """Call the LLM for a plain-text completion, with the same retry policy."""
    settings = get_settings()

    @retry(
        stop=stop_after_attempt(settings.max_llm_retries),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        before_sleep=_log_retry,
        reraise=True,
    )
    def _invoke() -> str:
        llm = get_llm()
        messages = []
        if system:
            messages.append(("system", system))
        messages.append(("human", prompt))
        response = llm.invoke(messages)
        content = response.content
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM returned an empty text response.")
        return content

    return _invoke()

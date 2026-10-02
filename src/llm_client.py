"""OpenRouter LLM client: initialization and per-page OCR requests.

Uses the OpenAI Python SDK pointed at OpenRouter's OpenAI-compatible endpoint.
The client is shared across worker threads (it is thread-safe).
"""

import base64
import os
import time

import openai
from openai import OpenAI

from src.config import (
    API_DELAY_SECONDS,
    API_MAX_RETRIES,
    API_TIMEOUT_SECONDS,
    ENV_FILE_PATH,
    MODEL_ID,
    OCR_MAX_TOKENS,
    OCR_REASONING_EFFORT,
    OCR_SYSTEM_PROMPT,
    OCR_USER_PROMPT,
    OPENROUTER_API_KEY_ENV,
    OPENROUTER_BASE_URL,
    PRICE_INPUT_PER_M,
    PRICE_OUTPUT_PER_M,
)
from src.logger import get_logger

logger = get_logger("llm_client")

# Transient failures worth retrying with backoff; other API errors (400/401/402/404) fail fast.
_RETRYABLE_ERRORS = (
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)


class EmptyLLMResponseError(RuntimeError):
    """Raised when OpenRouter returns a response with no choices (upstream provider error)."""


def init_llm_client() -> OpenAI:
    """Create an OpenAI SDK client configured for OpenRouter.

    ``.env`` is loaded by src.config at import, so ``OPENROUTER_API_KEY`` can live there.

    Returns:
        OpenAI client pointed at the OpenRouter base URL.

    Raises:
        RuntimeError: If the API key environment variable is not set.
    """
    api_key = os.getenv(OPENROUTER_API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"{OPENROUTER_API_KEY_ENV} is not set. Add it to {ENV_FILE_PATH} "
            f"(see .env.example) or export it in your shell."
        )

    # Retries are handled in ocr_page_with_llm() so they are logged with page context.
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        timeout=API_TIMEOUT_SECONDS,
        max_retries=0,
    )
    logger.info("OpenRouter client initialized (model=%s)", MODEL_ID)
    return client


def ocr_page_with_llm(image_bytes: bytes, client: OpenAI, mime_type: str = "image/jpeg") -> tuple[str, dict]:
    """Send a rendered page image to the LLM for OCR text extraction.

    Args:
        image_bytes: Encoded page image (JPEG by default).
        client: OpenRouter client from init_llm_client().
        mime_type: MIME type of image_bytes.

    Returns:
        Tuple of (extracted_text, token_usage_dict). token_usage_dict has keys
        prompt_tokens, output_tokens, total_tokens, reasoning_tokens, cost_usd,
        and cost_source ("openrouter" when reported, "estimated" otherwise).

    Raises:
        RuntimeError: If all retries are exhausted.
        openai.APIStatusError: For non-retryable API errors (bad request, auth, credits).
    """
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    messages = [
        {"role": "system", "content": OCR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": OCR_USER_PROMPT},
            ],
        },
    ]

    last_error: Exception | None = None
    for attempt in range(API_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=messages,
                max_tokens=OCR_MAX_TOKENS,
                extra_body={
                    "reasoning": _reasoning_param(OCR_REASONING_EFFORT),
                    "usage": {"include": True},
                },
            )
            if not response.choices:
                raise EmptyLLMResponseError(f"No choices in response: {response}")

            choice = response.choices[0]
            if choice.finish_reason == "length":
                logger.warning("OCR output hit max_tokens=%d; page text may be truncated", OCR_MAX_TOKENS)

            token_usage = _parse_usage(response.usage)

            if API_DELAY_SECONDS > 0:
                time.sleep(API_DELAY_SECONDS)

            return choice.message.content or "", token_usage

        except (*_RETRYABLE_ERRORS, EmptyLLMResponseError) as e:
            last_error = e
            wait_time = 2 ** attempt
            logger.warning(
                "LLM OCR attempt %d/%d failed: %s. Retrying in %ds...",
                attempt + 1, API_MAX_RETRIES, e, wait_time,
            )
            time.sleep(wait_time)

    raise RuntimeError(f"LLM OCR failed after {API_MAX_RETRIES} retries: {last_error}")


def _reasoning_param(effort: str) -> dict:
    """Build OpenRouter's reasoning parameter; "none" disables reasoning entirely."""
    return {"enabled": False} if effort == "none" else {"effort": effort}


def estimate_cost(prompt_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts using the fallback prices in config."""
    return prompt_tokens / 1_000_000 * PRICE_INPUT_PER_M + output_tokens / 1_000_000 * PRICE_OUTPUT_PER_M


def _parse_usage(usage) -> dict:
    """Extract token counts and cost from a usage object.

    Prefers the actual cost OpenRouter reports; falls back to a config-price estimate.
    """
    if usage is None:
        return {
            "prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "reasoning_tokens": 0, "cost_usd": 0.0, "cost_source": "estimated",
        }

    prompt_tokens = usage.prompt_tokens or 0
    output_tokens = usage.completion_tokens or 0
    details = getattr(usage, "completion_tokens_details", None)
    reported_cost = (usage.model_extra or {}).get("cost")
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": usage.total_tokens or 0,
        "reasoning_tokens": (getattr(details, "reasoning_tokens", 0) or 0) if details else 0,
        "cost_usd": float(reported_cost) if reported_cost is not None else estimate_cost(prompt_tokens, output_tokens),
        "cost_source": "openrouter" if reported_cost is not None else "estimated",
    }

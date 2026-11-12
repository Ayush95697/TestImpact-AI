from typing import Any, Dict, List, Optional
import requests
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LLM
from pydantic import Field, field_validator

from app.llm.config import (
    get_llm_settings,
    is_placeholder_or_empty,
    is_valid_http_url,
)


class CompanyLLMError(RuntimeError):
    """Base exception for company LLM API operations."""


class CompanyLLMNotConfiguredError(CompanyLLMError):
    """Raised when LLM operations are attempted before the company LLM API is configured."""

    def __init__(
        self,
        message: str = (
            "Company LLM API is not yet configured. "
            "Set COMPANY_LLM_API_URL, COMPANY_LLM_API_KEY, and COMPANY_LLM_MODEL_NAME "
            "in environment configuration to enable explanation generation."
        ),
    ):
        super().__init__(message)


class CompanyLLMResponseError(CompanyLLMError):
    """Raised when the company LLM API returns an invalid, empty, or malformed response."""


class CompanyLLM(LLM):
    """Custom LangChain LLM adapter for the company's on-prem LLaMA 3.1 8B API.

    Conforms to the company HTTP specification:
    - Method: POST
    - Headers: Content-Type: application/json, X-API-KEY: <api_key>
    - Body: {model, messages: [{role: "user", content: prompt}], temperature, top_p, max_tokens[, stop]}
    - Response: {"choices": [{"message": {"content": "..."}}]}
    """

    model: str = Field(default="")
    endpoint_url: str = Field(default="")
    api_key: str = Field(default="", repr=False, exclude=True)
    temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, gt=0.0, le=1.0)
    max_tokens: int = Field(default=1000, ge=1)
    timeout: int = Field(default=60, ge=1)

    @field_validator("model", "endpoint_url", "api_key", mode="before")
    @classmethod
    def _normalize_str_field(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Field value must be a string")
        return value.strip()

    @property
    def _llm_type(self) -> str:
        return "company_llama"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Returns non-secret identifying parameters for LangChain tracing/caching."""
        return {
            "model": self.model,
            "endpoint_url": self.endpoint_url,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }

    @property
    def lc_secrets(self) -> Dict[str, str]:
        return {"api_key": "COMPANY_LLM_API_KEY"}

    def is_configured(self) -> bool:
        """Checks whether required endpoint, credentials, and model identifier are present."""
        return (
            is_valid_http_url(self.endpoint_url)
            and not is_placeholder_or_empty(self.api_key)
            and not is_placeholder_or_empty(self.model)
        )

    def _masked_api_key(self) -> str:
        if not self.api_key:
            return "<unset>"
        if len(self.api_key) > 5:
            return f"{self.api_key[:3]}...{self.api_key[-2:]}"
        return "***"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Executes a non-streaming completion request against the company LLM endpoint."""
        if not self.is_configured():
            raise CompanyLLMNotConfiguredError()

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string")

        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key,
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

        if stop:
            payload["stop"] = list(stop)

        response = None
        try:
            response = requests.post(
                self.endpoint_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise CompanyLLMError(
                f"Company LLM API request timed out after {self.timeout} seconds"
            ) from None
        except requests.exceptions.ConnectionError:
            raise CompanyLLMError(
                "Network connection to Company LLM API failed"
            ) from None
        except requests.exceptions.HTTPError:
            status_code = response.status_code if response is not None else "unknown"
            raise CompanyLLMError(
                f"Company LLM API request failed with HTTP {status_code}"
            ) from None
        except requests.exceptions.RequestException:
            raise CompanyLLMError(
                "Company LLM API request failed"
            ) from None

        try:
            data = response.json()
        except Exception:
            raise CompanyLLMResponseError(
                "Company LLM API response could not be parsed as valid JSON"
            ) from None

        if not isinstance(data, dict):
            raise CompanyLLMResponseError(
                "Company LLM API response must be a JSON object"
            )

        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            raise CompanyLLMResponseError(
                "Company LLM API response missing non-empty 'choices' list"
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise CompanyLLMResponseError(
                "Company LLM API response 'choices[0]' must be a JSON object"
            )

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise CompanyLLMResponseError(
                "Company LLM API response missing 'choices[0].message' object"
            )

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise CompanyLLMResponseError(
                "Company LLM API response 'choices[0].message.content' must be a non-empty string"
            )

        return content

    def __repr__(self) -> str:
        return (
            f"CompanyLLM(model='{self.model}', "
            f"endpoint_url='{self.endpoint_url}', "
            f"api_key='{self._masked_api_key()}', "
            f"temperature={self.temperature}, "
            f"top_p={self.top_p}, "
            f"max_tokens={self.max_tokens}, "
            f"timeout={self.timeout})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def get_llm_model() -> CompanyLLM:
    """Lazily instantiates a CompanyLLM adapter from environment configuration."""
    settings = get_llm_settings()
    return CompanyLLM(
        model=settings.company_llm_model_name,
        endpoint_url=settings.company_llm_api_url,
        api_key=settings.company_llm_api_key,
        temperature=settings.company_llm_temperature,
        top_p=settings.company_llm_top_p,
        max_tokens=settings.company_llm_max_tokens,
        timeout=settings.company_llm_timeout,
    )


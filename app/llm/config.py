import os
from typing import Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# Load .env without overriding existing process/system environment variables
load_dotenv(override=False)

_UNCONFIGURED_PLACEHOLDERS = {
    "",
    "PASTE_YOUR_API_KEY_HERE",
    "YOUR_API_KEY_HERE",
    "COMPANY_API_KEY",
    "MODEL_IDENTIFIER",
    "PASTE_MODEL_NAME_HERE",
    "YOUR_MODEL_NAME_HERE",
    "PASTE_ENDPOINT_URL_HERE",
    "YOUR_ENDPOINT_URL_HERE",
}

_PLACEHOLDER_PREFIXES = ("PASTE_", "YOUR_", "<")


def is_placeholder_or_empty(value: Optional[str]) -> bool:
    """Returns True if a configuration value is missing or uses a template placeholder."""
    if not value or not isinstance(value, str):
        return True
    stripped = value.strip()
    if stripped in _UNCONFIGURED_PLACEHOLDERS:
        return True
    upper_val = stripped.upper()
    return any(upper_val.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES)


def is_valid_http_url(value: Optional[str]) -> bool:
    """Checks that an endpoint URL is non-placeholder and uses http/https."""
    if is_placeholder_or_empty(value):
        return False
    assert value is not None
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _parse_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid float value for environment variable {name}") from exc


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid integer value for environment variable {name}") from exc


def _mask_secret(secret: str) -> str:
    if not secret:
        return "<unset>"
    if len(secret) > 5:
        return f"{secret[:3]}...{secret[-2:]}"
    return "***"


class LLMSettings(BaseModel):
    """Configuration container for the Company LLaMA 3.1 8B API."""

    company_llm_api_url: str = Field(default="")
    company_llm_api_key: str = Field(default="", repr=False, exclude=True)
    company_llm_model_name: str = Field(default="")
    company_llm_temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    company_llm_top_p: float = Field(default=0.9, gt=0.0, le=1.0)
    company_llm_max_tokens: int = Field(default=1000, ge=1)
    company_llm_timeout: int = Field(default=60, ge=1)

    @field_validator("company_llm_api_url", "company_llm_api_key", "company_llm_model_name", mode="before")
    @classmethod
    def _strip_strings(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Configuration value must be a string")
        return value.strip()

    def is_configured(self) -> bool:
        """Returns True only when endpoint URL, API key, and model identifier are validly set."""
        return (
            is_valid_http_url(self.company_llm_api_url)
            and not is_placeholder_or_empty(self.company_llm_api_key)
            and not is_placeholder_or_empty(self.company_llm_model_name)
        )

    def __repr__(self) -> str:
        return (
            f"LLMSettings(company_llm_api_url='{self.company_llm_api_url}', "
            f"company_llm_api_key='{_mask_secret(self.company_llm_api_key)}', "
            f"company_llm_model_name='{self.company_llm_model_name}', "
            f"company_llm_temperature={self.company_llm_temperature}, "
            f"company_llm_top_p={self.company_llm_top_p}, "
            f"company_llm_max_tokens={self.company_llm_max_tokens}, "
            f"company_llm_timeout={self.company_llm_timeout})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def get_llm_settings() -> LLMSettings:
    """Lazily reads and validates LLM settings from environment variables."""
    return LLMSettings(
        company_llm_api_url=os.getenv("COMPANY_LLM_API_URL", ""),
        company_llm_api_key=os.getenv("COMPANY_LLM_API_KEY", ""),
        company_llm_model_name=os.getenv("COMPANY_LLM_MODEL_NAME", ""),
        company_llm_temperature=_parse_float_env("COMPANY_LLM_TEMPERATURE", 0.5),
        company_llm_top_p=_parse_float_env("COMPANY_LLM_TOP_P", 0.9),
        company_llm_max_tokens=_parse_int_env("COMPANY_LLM_MAX_TOKENS", 1000),
        company_llm_timeout=_parse_int_env("COMPANY_LLM_TIMEOUT", 60),
    )


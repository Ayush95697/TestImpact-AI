import os
import sys

# Ensure testimpact-ai root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.rag.config import get_rag_settings
from app.rag.embeddings import CompanyEmbeddings, get_embedding_model


def verify_configuration():
    print("=" * 60)
    print("Verifying Environment Configuration")
    print("=" * 60)

    settings = get_rag_settings()

    # 1. API URL loaded
    expected_url = "https://quasarmarket.coforge.com/qag/llmrouter-api/v2/text/embeddings"
    assert settings.company_embedding_api_url == expected_url, (
        f"API URL mismatch: got {settings.company_embedding_api_url}"
    )
    print(f"[PASS] API URL loaded correctly: {settings.company_embedding_api_url}")

    # 2. Embedding dimensions read as integer 736
    assert isinstance(settings.company_embedding_dimensions, int), (
        f"Dimensions should be int, got {type(settings.company_embedding_dimensions)}"
    )
    assert settings.company_embedding_dimensions == 736, (
        f"Dimensions mismatch: got {settings.company_embedding_dimensions}"
    )
    print(f"[PASS] Dimensions loaded as integer: {settings.company_embedding_dimensions}")

    # 3. Timeout set to 30
    assert settings.company_embedding_timeout == 30, (
        f"Timeout mismatch: got {settings.company_embedding_timeout}"
    )
    print(f"[PASS] Timeout loaded correctly: {settings.company_embedding_timeout}s")

    # 4. API Key recognition: With placeholder, provider recognizes as unconfigured
    provider = get_embedding_model()
    assert not provider.is_configured(), (
        "Provider should recognize placeholder key as NOT configured!"
    )
    print("[PASS] With placeholder key ('PASTE_YOUR_API_KEY_HERE'), is_configured() is False")

    # When a simulated real key is supplied, provider recognizes as configured
    test_provider = CompanyEmbeddings(
        api_url=settings.company_embedding_api_url,
        api_key="actual-user-supplied-api-key-test",
        dimensions=settings.company_embedding_dimensions,
        timeout=settings.company_embedding_timeout,
    )
    assert test_provider.is_configured(), (
        "Provider should recognize real key as configured!"
    )
    print("[PASS] With simulated real key, is_configured() is True")

    # 5. Verify repr does not leak secret
    rep = repr(test_provider)
    assert "actual-user-supplied-api-key-test" not in rep, (
        "API key must never be printed in repr!"
    )
    print("[PASS] String representation masks API key safely:", rep)

    print("=" * 60)
    print("ALL CONFIGURATION VERIFICATION CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    verify_configuration()


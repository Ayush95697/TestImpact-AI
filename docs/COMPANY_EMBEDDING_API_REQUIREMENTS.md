# Company Embedding API Requirements & Integration Specification

This document details the HTTP contract, integration adapter implementation (`CompanyEmbeddings`), and remaining verification items for connecting **TestImpact AI** to the enterprise internal embedding service.

---

## 1. Environment Configuration

The embedding provider reads configuration lazily via environment variables (or `.env` loaded with `override=False`).

| Variable Name | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `COMPANY_EMBEDDING_API_URL` | **Yes** | *None* | Full HTTPS endpoint URL for embedding requests (e.g., `https://ml-gateway.internal.company.com/v1/embeddings`). |
| `COMPANY_EMBEDDING_API_KEY` | **Yes** | *None* | Authentication API key passed via the header. |
| `COMPANY_EMBEDDING_DIMENSIONS` | **Yes** | *None* | Target dense vector dimensions. Must be explicitly provided. |
| `COMPANY_EMBEDDING_TIMEOUT` | No | `30` | Request timeout in seconds. |
| `RAG_COLLECTION_NAME` | No | `testimpact_company_v1` | Name of the isolated Chroma collection. |
| `RAG_CHROMA_DIR` | No | `./chroma_db` | Persistent vector directory path on disk. |

> **Security Rule:** Never commit real API keys or sensitive endpoints to version control. Maintain `.env` in `.gitignore`.

---

## 2. API Contract Specification

### HTTP Method & Endpoint
- **Method**: `POST`
- **URL**: `${COMPANY_EMBEDDING_API_URL}`

### Headers
```http
Content-Type: application/json
X-API-KEY: <configured_api_key>
```

### Request Payload
```json
{
  "texts": ["text string 1", "text string 2"],
  "dimensions": 736
}
```

---

## 3. LangChain Contract & Response Formats

The adapter implements `langchain_core.embeddings.Embeddings`:
- `embed_documents(texts: list[str]) -> list[list[float]]`: Returns one dense vector per input text.
- `embed_query(text: str) -> list[float]`: Returns a single dense vector.

### Supported Response Formats

The adapter dynamically handles both known response formats returned by the API:

#### Format A: Nested Batch Response (Standard for Multiple Texts)
When multiple texts are supplied (`len(texts) > 1`), the API must return a nested array:
```json
{
  "embeddings": [
    [0.02711, 0.00058, 0.00634],
    [0.01944, -0.00412, 0.00891]
  ],
  "usage": {
    "input_tokens": 14,
    "duration": 0.421
  }
}
```

#### Format B: Flat Single-Text Response
When exactly one text is supplied (`len(texts) == 1`), the API may return an abbreviated 1D array:
```json
{
  "embeddings": [
    0.027111461386084557,
    0.0005847492720931768,
    0.006343955174088478
  ],
  "usage": {
    "input_tokens": 7,
    "duration": 1.6296
  }
}
```
*Resolution:* The adapter automatically converts this flat structure into `[[0.0271..., ...]]` for `embed_documents`, or unwraps it directly for `embed_query`.

#### Rejected Ambiguous Format: Flat Response for Multiple Texts
If multiple texts are sent (`len(texts) > 1`) but the API responds with a flat 1D vector, the adapter raises `CompanyEmbeddingResponseError`. The adapter **never** guesses which text the vector belongs to nor duplicates the vector across inputs.

---

## 4. Vector & Dimension Validation

Every vector returned by the endpoint undergoes validation before being passed to Chroma:
1. **Count Equality**: Returned vector count must strictly equal `len(texts)`.
2. **Dimension Conformance**: `len(vector)` must equal `COMPANY_EMBEDDING_DIMENSIONS`. Any mismatch raises a `CompanyEmbeddingResponseError`.
3. **Numeric & Finite Verification**: All values must be valid numeric floats. Non-numeric types (including booleans) and non-finite values (`NaN`, `+Inf`, `-Inf`) are rejected.
4. **Float Normalization**: All numeric values are explicitly cast to native Python `float`.

---

## 5. Error Handling & Credential Protection

- **Missing Configuration**: If `api_url`, `api_key`, or `dimensions` is absent or unset, `is_configured()` returns `False`. Invocations immediately raise `CompanyEmbeddingNotConfiguredError`. RAG endpoints return `HTTP 503 Service Unavailable`.
- **HTTP Failures**: Status codes (e.g. 401 Unauthorized, 403 Forbidden, 500 Internal Error) are wrapped in `CompanyEmbeddingError` with generic, safe diagnostic messages.
- **Network Timeouts & Connectivity**: `requests.exceptions.Timeout` and `requests.exceptions.ConnectionError` are caught and mapped to clear exceptions.
- **Credential Protection**:
  - `requests` exceptions are not chained via default tracebacks (`from None`), preventing headers containing `X-API-KEY` from leaking into logs.
  - The `__repr__` method of `CompanyEmbeddings` masks the API key (`abc...yz`).
  - No logs print authorization headers or query parameters.

---

## 6. How to Run Mocked Unit Tests

Unit tests simulate the API contract without requiring a live endpoint or real credentials.

From the `testimpact-ai` directory:
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_company_embeddings.py
```

### Coverage
1. Batch embeddings with nested vectors.
2. Single-text embedding with flat vector.
3. Rejection of flat response for multiple input texts.
4. Rejection of dimension mismatch.
5. Rejection of non-numeric and non-finite (`NaN`/`Inf`) values.
6. Handling of HTTP 401.
7. Handling of HTTP 500.
8. Handling of API timeout.
9. Handling of missing credentials.
10. Strict protection and masking of API keys in errors and string representations.

---

## 7. Open Technical Questions / Details Pending Confirmation

Before enabling live indexing against the production or staging company API, the following parameters require formal confirmation from the ML / Platform engineering team:

1. **Exact Vector Dimension (736 vs 746)**:
   - The example request specified `736`, while example code referenced `746`.
   - *Action required*: Confirm the exact output dimension of the model deployment.
2. **Batch Response Format Confirmation**:
   - Confirm whether batch requests (`texts: [...]`) always return nested vectors (`[[...], [...]]`).
3. **Batch Size and Rate Limits**:
   - Confirm maximum allowed texts per request (e.g. 16, 32, 64) and rate limits (requests per minute / tokens per minute).
4. **Token Truncation Policy**:
   - Confirm the maximum character / token length per chunk and whether the server automatically truncates or returns HTTP 400 when input length is exceeded.

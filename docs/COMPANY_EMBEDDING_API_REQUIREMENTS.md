# Company Embedding API Requirements & Integration Specification

This document defines the interface and technical parameters required from the company's internal platform / ML engineering team to configure the enterprise embedding provider for **TestImpact AI**.

---

## 1. Required Integration Specifications

To replace the temporary provider boundary with the approved internal embedding service, provide the following parameters:

| Parameter | Description | Example / Required Detail |
| :--- | :--- | :--- |
| **Provider / Service Name** | Internal service name or gateway identifier | e.g. `Enterprise ML Gateway - Embedding Service` |
| **Embedding Endpoint URL** | Full HTTPS base URL and path | e.g. `https://ml-api.internal.company.com/v1/embeddings` |
| **Authentication Mechanism** | Supported auth header / token format | e.g. Bearer Token, API Key header (`X-API-Key`), mTLS, or OAuth2 Client Credentials |
| **Request Payload Format** | JSON request schema expected by the API | Expected JSON body structure (e.g. `{"input": [...], "model": "..."}`) |
| **Response Payload Format** | JSON response schema returned by the API | Path to vector array in response (e.g. `data[i].embedding`) |
| **Model / Deployment Name** | Designated enterprise model identifier | e.g. `text-embedding-gecko`, `bge-large-en-v1.5`, etc. |
| **Embedding Dimensions** | Exact dimension of output dense vectors | e.g. `768`, `1536`, or `1024` |
| **Maximum Input Length** | Token / character limit per input chunk | e.g. `8192` tokens or `2048` characters |
| **Batch Size Limits** | Maximum number of texts permitted per single batch call | e.g. `32`, `64`, or `100` |
| **Rate Limits** | Requests per minute (RPM) and tokens per minute (TPM) | e.g. `1200 RPM` |
| **Timeout & Retry Policy** | Recommended HTTP timeout and backoff strategy | e.g. 10s connection timeout, exponential backoff with jitter on 429/503 |

---

## 2. Environment Configuration

Once the above details are provided, configure the service via the following environment variables (defined in `.env`):

```bash
COMPANY_EMBEDDING_API_URL=https://<company-endpoint>
COMPANY_EMBEDDING_API_KEY=<secure-api-key>
COMPANY_EMBEDDING_MODEL=<model-name>
```

> **Security Notice:** Never commit actual API keys or credentials to version control. Keep `.env` listed in `.gitignore`.


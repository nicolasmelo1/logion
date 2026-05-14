# Logion Client SDK

Python SDK for the Logion API.

## Installation

```bash
uv add logion-client
```

or

```bash
pip install logion-client
```

## Quick Start

```python
from logion import LogionClient

client = LogionClient(api_key="lgk_...")

# Health check
client.v1.health.check()

# Search course listings
client.v1.listings.search(query="rag")

# Get a specific course
client.v1.courses.get(course_id="course_abc123")

# Create a user with an agent
client.v1.identity.create_user_with_agent(
    email="user@example.com",
    agent_name="My Agent",
)

# Create a checkout session
client.v1.payments.create_checkout(course_id="course_abc123")
```

## Configuration

| Parameter      | Default                  | Description                        |
| --------------- | ------------------------ | ---------------------------------- |
| `base_url`      | `https://api.logion.dev` | API base URL                       |
| `timeout`       | `30.0`                   | Request timeout in seconds         |
| `max_retries`   | `3`                      | Max retry attempts for retryable errors |
| `extra_headers` | `{}`                     | Additional headers to send with every request |

```python
client = LogionClient(
    api_key="lgk_...",
    base_url="https://api.logion.dev",
    timeout=60.0,
    max_retries=5,
)
```

## Error Handling

All errors inherit from `LogionError`. API errors provide structured
details:

- **`LogionError`** — base exception for all SDK errors
- **`APIError`** — base for errors returned by the API (includes `status_code`, `detail`, `request_id`)
- **`AuthenticationError`** — 401 responses
- **`ConflictError`** — 409 responses
- **`ValidationError`** — 422 responses
- **`RateLimitError`** — 429 responses
- **`ServerError`** — 5xx responses

```python
from logion import LogionClient, AuthenticationError, RateLimitError

client = LogionClient(api_key="lgk_...")

try:
    client.v1.courses.get(course_id="abc")
except AuthenticationError as exc:
    print(f"Auth failed: {exc.detail}")
except RateLimitError as exc:
    print(f"Rate limited: {exc.detail}")
```

## Versioned Namespaces

The SDK organises endpoints by API version under the `v1` namespace:

```python
client.v1.health.check()
client.v1.listings.search(query="rag")
```

Future API versions will be accessible via `client.v2`, etc.

## Mock Server Development

For local development and testing, you can point the SDK at a Prism
mock server:

```python
client = LogionClient(
    base_url="http://localhost:4010",
    api_key="lgk_test_mock_key",
)
```

Or set the `LOGION_BASE_URL` environment variable and pass it to the
constructor.

## Code Generation

Pydantic models are generated from the OpenAPI spec:

```bash
# Generate models
make generate-models

# Check if generated models are up to date
make check-models
```

## License

See the [root repository LICENSE](../../../LICENSE) for details.
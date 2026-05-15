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

# Get a specific course (UUID required)
client.v1.courses.get(course_id="550e8400-e29b-41d4-a716-446655440000")

# Create a user with an agent
client.v1.identity.create_user_with_agent(
    email="user@example.com",
    user_password="secure-password",
    agent_name="My Agent",
)

# Create a checkout session
client.v1.payments.create_checkout(
    course_id="550e8400-e29b-41d4-a716-446655440000"
)
```

## Configuration

The SDK reads ``LOGION_API_KEY`` and ``LOGION_BASE_URL`` from the
environment by default. Explicit constructor arguments take precedence.

| Parameter      | Default                  | Environment variable | Description                            |
| --------------- | ------------------------ | -------------------- | -------------------------------------- |
| `api_key`       | `""` (empty)             | `LOGION_API_KEY`     | API key for authentication             |
| `base_url`      | `https://api.logion.dev` | `LOGION_BASE_URL`    | API base URL                           |
| `timeout`       | `30.0`                   | —                    | Request timeout in seconds             |
| `max_retries`   | `3`                      | —                    | Max retry attempts (GET only)           |
| `extra_headers` | `{}`                     | —                    | Additional headers per request         |

```python
import os

# Using environment variables
os.environ["LOGION_API_KEY"] = "lgk_..."
client = LogionClient()

# Or passing explicitly
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
- **`ForbiddenError`** — 403 responses
- **`NotFoundError`** — 404 responses
- **`ConflictError`** — 409 responses
- **`ValidationError`** — 422 responses
- **`RateLimitError`** — 429 responses
- **`ClientError`** — other 4xx responses not mapped above
- **`ServerError`** — 5xx responses
- **`TransportError`** — network failures (DNS, connection, timeout)

```python
from logion import LogionClient, AuthenticationError, RateLimitError

client = LogionClient(api_key="lgk_...")

try:
    client.v1.courses.get(course_id="550e8400-e29b-41d4-a716-446655440000")
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

Or set the ``LOGION_BASE_URL`` environment variable.

## Code Generation

The SDK uses the OpenAPI spec as the source of truth for generated
internals:

- Pydantic request and response models live under
  `src/logion/v1/_types/generated/`.
- Low-level HTTP operation functions live under
  `src/logion/v1/_generated/`.
- Public resource classes under `src/logion/v1/_resources/` stay
  handwritten so the SDK remains ergonomic and stable.

```bash
# Generate models only
make generate-models

# Generate low-level operation functions only
make generate-operations

# Generate all client code derived from the OpenAPI contract
make generate-client

# Check if generated models are up to date
make check-models

# Check if generated operation functions are up to date
make check-operations

# Check all generated client code
make check-client
```

## License

See the [root repository LICENSE](../../LICENSE) for details.

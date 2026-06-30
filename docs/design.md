# Solution Design

## Goal

This service is the usage-control layer for an AI product. Its job is to accept generation requests, enforce per-user credit limits, convert model usage into billable credits, and record a durable usage trail that can be inspected later.

## Architecture

The implementation follows a DDD + hexagonal shape:

- `app/api` contains the FastAPI routes and Pydantic DTOs.
- `app/application` contains the metering use cases.
- `app/domain` contains the policy objects, accounting rules, and exceptions.
- `app/ports` defines the inbound and outbound boundaries.
- `app/infrastructure` contains the Postgres adapter and the mock AI adapter.

The API layer is intentionally thin. It validates input, calls the application service, and translates domain errors into HTTP responses.

## Persistence Choice

Postgres is the durable source of truth for:

- user quota configuration
- in-flight reservations
- final usage records

That choice fits the concurrency requirement well because the service can lock the user row while reserving credits. It also keeps the history auditable, which matters for billing and support. Redis could still be added later as a cache or short-lived reservation layer, but it is not required for the core assignment.

## Credit Model

The service uses this rule:

- `prompt_tokens` is the token count of the prompt text
- `estimated_total_tokens = prompt_tokens + max_completion_tokens`
- `billable_credits = ceil(total_tokens * credit_multiplier)`

The user’s multiplier is stored with the quota policy and copied into each usage record as a snapshot. That means historical records remain explainable even if the user’s multiplier changes later.

## Quota Flow

The request flow is:

1. Lock the user quota row and capture the current policy snapshot.
2. Estimate the request cost before generation starts.
3. Reserve the estimated credits in Postgres.
4. Call the AI adapter.
5. Reconcile the actual usage after the model returns.
6. Store the final usage record and keep the reservation history.

If the AI call fails, the reservation is marked failed and released from the active reserved balance.

If actual usage is higher than the estimate, the final record still captures the true usage. The account may end up over quota after reconciliation, which is visible in the usage summary and the generation response.

## Concurrency

The key consistency rule is that reservation happens under a transaction with a row lock on the user quota record. That prevents two processes from both seeing the same remaining balance and overspending it at the same time.

This is the most important part of the service boundary because the exact model usage is only known after generation finishes.

## Concrete Example

User `alice` has:

- quota limit: `100` credits
- multiplier: `1.5`
- current used credits: `60`

She submits a request with:

- estimated prompt tokens: `10`
- `max_completion_tokens`: `10`
- estimated total tokens: `20`
- estimated billable credits: `ceil(20 * 1.5) = 30`

The service reserves `30` credits and allows the request.

The AI layer later reports:

- prompt tokens: `10`
- completion tokens: `14`
- total tokens: `24`
- final billable credits: `ceil(24 * 1.5) = 36`

The service records the final usage as `36` credits. Alice’s total used credits become `96`, leaving `4` credits.

## API Summary

- `PUT /users/{user_key}/quota` updates quota and multiplier.
- `POST /users/{user_key}/generate` runs text generation and records usage.
- `GET /users/{user_key}/usage` returns current usage and remaining credits.
- `GET /users/{user_key}/usage/records` returns the usage history.

## Testing Strategy

Tests focus on the important behavior:

- generation success and usage recording
- multiplier-driven credit calculation
- quota rejection
- AI failure handling
- current usage and remaining credits
- estimate-versus-actual mismatch
- near-simultaneous requests

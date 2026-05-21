# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A personal Telegram-based fitness tracker. Users send natural-language messages in Spanish to a Telegram bot; Claude (Haiku) extracts structured fitness data and replies with personalized feedback. Three AWS Lambda functions handle the workload:

- **WebhookFunction** — receives Telegram messages in real time and responds immediately
- **DailySummaryFunction** — fires nightly at 11 PM UTC, sends each allowed user a day recap
- **WeeklyTrendFunction** — fires every Sunday at 10 AM UTC, sends a 7-day trend analysis

## Build & deploy commands

```bash
make build          # sam build (requires Docker Desktop running)
make deploy         # build + deploy to dev stack (us-west-1)
make deploy-prod    # build + deploy to prod stack

make local-test     # sam local invoke WebhookFunction --event events/test-message.json

make setup-secrets  # interactive prompt to create/update Secrets Manager secret (dev)

make logs           # tail all Lambda logs for dev stack
make logs-webhook   # tail WebhookFunction only
make logs-daily     # tail DailySummaryFunction only
make logs-weekly    # tail WeeklyTrendFunction only
```

## Architecture

### Lambda + Shared Layer

All three functions share a single Lambda Layer (`layers/shared/`) that ships the `anthropic` SDK and the internal `shared` package. Source lives at `layers/shared/python/shared/`. The layer is built via `layers/shared/Makefile` (SAM `BuildMethod: makefile`).

The shared package modules:
- `config.py` — reads env vars; sets `CLAUDE_MODEL = "claude-haiku-4-5"`
- `models.py` — dataclasses for `MealLog`, `BodyMetrics`, `ExerciseLog`, `DailySummary`, `Profile` + `IntentType` enum
- `dynamo.py` — all DynamoDB access; lazy singleton table client
- `llm.py` — Anthropic SDK calls; lazy singleton client
- `telegram.py` — outbound `send_message` + inbound parsing + auth

### DynamoDB single-table design

Table name: `FitnessAssistant-{Stage}`. Key pattern:

| Entity | PK | SK |
|---|---|---|
| Meal | `USER#{chat_id}` | `MEAL#{ISO-timestamp}` |
| Exercise | `USER#{chat_id}` | `EXERCISE#{ISO-timestamp}` |
| Body metrics | `USER#{chat_id}` | `BODY#{YYYY-MM-DD}` |
| Daily summary | `USER#{chat_id}` | `DAY#{YYYY-MM-DD}` |
| Profile | `USER#{chat_id}` | `PROFILE` |

`compute_and_save_daily_summary` recomputes totals from raw meal/exercise rows and upserts the `DAY#` record — called on every meal/exercise write and on explicit summary queries.

### LLM call pattern

`extract_intent` in `llm.py` uses Claude tool_use with a single forced tool (`log_fitness_data`) to parse any incoming message into a typed, structured response. The static `SYSTEM_PROMPT` is sent with `cache_control: ephemeral` to take advantage of prompt caching. The user profile block and today's running totals are appended uncached so a profile update correctly invalidates.

### Secrets

All secrets (`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `ALLOWED_CHAT_IDS`) are stored in AWS Secrets Manager under `fitness-assistant/{Stage}` and injected into Lambda env vars by the SAM template. Local `.env` is used only for reference — SAM local tests need the env vars set manually.

### Authorization

`ALLOWED_CHAT_IDS` is a comma-separated list of Telegram numeric chat IDs. The webhook silently returns `200 OK` for unknown chat IDs to avoid leaking bot existence. `verify_telegram_secret` checks the `X-Telegram-Bot-Api-Secret-Token` header on every POST.

## Key constraints

- **Spanish-first**: all LLM prompts and user-facing replies are in Spanish.
- **Single-user by design**: no multi-tenancy; `user_id` == Telegram `chat_id` string.
- **No conversation memory**: each webhook invocation is stateless; context comes only from the materialized `DAY#` summary.
- **`user_id` is always a string**: Telegram sends chat IDs as integers; `telegram.py` casts to `str` immediately.

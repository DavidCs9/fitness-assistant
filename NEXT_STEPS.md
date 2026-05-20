# Next Steps: From Scaffold to Production

This document outlines the path from the current scaffold (commit `adcc9dd`) to a working production deployment.

## Phase 0 — Prerequisites (one-time)

### 0.1 AWS account setup
- [ ] AWS account with billing alerts configured (recommend: $10/month alert)
- [ ] IAM user (or SSO profile) with permissions for: CloudFormation, Lambda, API Gateway, DynamoDB, Secrets Manager, EventBridge Scheduler, IAM, S3
- [ ] `aws configure` locally — verify with `aws sts get-caller-identity`

### 0.2 Local tooling
- [ ] AWS SAM CLI installed (`brew install aws-sam-cli`) — verify `sam --version`
- [ ] Python 3.12 available — verify `python3.12 --version`
- [ ] Docker Desktop running (SAM uses it for `sam build` with the makefile method)

### 0.3 Anthropic API
- [ ] Create API key at https://console.anthropic.com
- [ ] Add ~$5 of credits for testing
- [ ] Verify key works: `curl https://api.anthropic.com/v1/models -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01"`

### 0.4 Telegram Bot
- [ ] Open Telegram and message [@BotFather](https://t.me/BotFather)
- [ ] Run `/newbot` → pick a display name → pick a unique username ending in `bot`
- [ ] Save the bot token BotFather returns (format `123456789:ABC-DEF...`)
- [ ] Message [@userinfobot](https://t.me/userinfobot) to get your numeric chat ID
- [ ] Generate a webhook secret locally: `openssl rand -hex 32` (any random string works)

---

## Phase 1 — Deploy dev environment

### 1.1 Configure secrets
- [ ] Run `make setup-secrets` — it will prompt for the 4 values:
  - `ANTHROPIC_API_KEY`
  - `TELEGRAM_BOT_TOKEN` (from BotFather)
  - `TELEGRAM_WEBHOOK_SECRET` (random string from 0.4)
  - `ALLOWED_CHAT_IDS` (your numeric Telegram chat ID, comma-separated if multiple)
- [ ] Verify in AWS Console → Secrets Manager → `fitness-assistant/dev`

### 1.2 First build + deploy
- [ ] `make build` — confirm the SharedLayer Makefile runs and pulls down `anthropic` SDK
- [ ] `make deploy` — answer `y` to confirm changeset
- [ ] Note the `WebhookUrl` output from the stack

### 1.3 Register the webhook with Telegram
- [ ] Run the setWebhook curl (substitute your token, URL, and secret):
  ```bash
  curl -X POST "https://api.telegram.org/bot${TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d '{"url":"<WebhookUrl>","secret_token":"<TELEGRAM_WEBHOOK_SECRET>","allowed_updates":["message"]}'
  ```
- [ ] Verify with: `curl "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"` — `url` should match and `pending_update_count` should be 0

### 1.4 Smoke test
- [ ] Send a Telegram message to your bot: `Peso 99.8 hoy`
- [ ] Expect a reply within ~5 seconds
- [ ] `make logs-webhook` — verify the request was received and processed
- [ ] AWS Console → DynamoDB → `FitnessAssistant-dev` — confirm the `BODY#YYYY-MM-DD` item exists
- [ ] Repeat with a meal: `Desayuné 2 huevos revueltos con licuado de proteína`
- [ ] Repeat with exercise: `Caminé 30 minutos`
- [ ] Repeat with a query: `Cómo voy hoy?`

---

## Phase 2 — Iteration and hardening (dev only)

These can happen in any order based on what breaks first.

### 2.1 Observability
- [ ] Add CloudWatch alarm for webhook Lambda errors > 0 in 5 minutes
- [ ] Add CloudWatch alarm for webhook Lambda p95 duration > 10s
- [ ] Add structured logging (JSON) in `handler.py` to make CloudWatch Insights queries easy
- [ ] Consider adding a CloudWatch dashboard with: messages/day, intent breakdown, LLM tokens used

### 2.2 Edge cases & resilience
- [ ] Test message with no intent match (random text) — confirm the fallback reply makes sense
- [ ] Test message from an unauthorized chat ID — confirm it returns 200 silently (no leak)
- [ ] Test a long message (>500 chars) — confirm extraction still works
- [ ] Test a Telegram media message (photo/voice/sticker) — confirm `parse_incoming_message` returns `None, None` and we return 200
- [ ] Test a webhook with wrong/missing `X-Telegram-Bot-Api-Secret-Token` — confirm it returns 403
- [ ] Add a retry on the `send_message` call (Telegram API can transient-fail)
- [ ] Consider a DLQ for the webhook Lambda to catch dropped messages

### 2.3 Scheduled jobs
- [ ] Wait for the next 11 PM UTC tick — verify the daily summary fires (or trigger manually via AWS Console → Lambda → Test)
- [ ] Wait for the next Sunday 10 AM UTC — verify the weekly trend fires
- [ ] Verify the messages received feel useful; iterate on prompts in `llm.py`

### 2.4 Prompt quality
- [ ] Collect 10-20 real messages over a week
- [ ] Manually grade the LLM extractions (calorie estimates, intent classification)
- [ ] Tune `SYSTEM_PROMPT` and `EXTRACTION_TOOL` descriptions if accuracy is weak
- [ ] Verify prompt caching is working (check `cache_read_input_tokens` in Anthropic console)

### 2.5 Cost monitoring
- [ ] After 1 week of use, check:
  - Lambda invocations + duration (should be < $0.50/month for single user)
  - DynamoDB request units (should be < $0.10/month)
  - Anthropic API spend (should be ~$0.50-$2/month with Haiku + caching)
- [ ] Set Anthropic API usage limit to cap monthly spend

---

## Phase 3 — Production deployment

### 3.1 Decide what "prod" means here
For a single-user personal app, the "prod" environment may not be meaningfully different from dev. Options:
- **A:** Skip prod entirely, keep `dev` as the only environment (recommended for V1)
- **B:** Promote `dev` → `prod` with separate stack, secrets, and table
- **C:** Use `dev` for experimentation, `prod` for daily use, manually promote tested changes

If choosing B or C:

### 3.2 Prod secrets
- [ ] Generate a new Anthropic API key dedicated to prod (for separate billing/limits)
- [ ] Create a second Telegram bot for prod (so dev and prod don't share a webhook)
- [ ] Generate a fresh webhook secret for prod
- [ ] Create the `fitness-assistant/prod` secret in Secrets Manager (manually or adapt `make setup-secrets`)

### 3.3 Prod deploy
- [ ] `make deploy-prod` — deploys the `fitness-assistant-prod` stack
- [ ] Run `setWebhook` against the prod bot pointing at the prod stack's WebhookUrl
- [ ] Smoke test as in 1.4

### 3.4 Backup & recovery
- [ ] Enable point-in-time recovery on the prod DynamoDB table
- [ ] Document the manual restore procedure
- [ ] Consider a weekly export of the DynamoDB table to S3 (Glacier for cheap long-term storage)

### 3.5 CI/CD (optional)
- [ ] Add a GitHub Actions workflow that runs `sam build` on PR
- [ ] Add a workflow that deploys to dev on merge to `main`
- [ ] Prod stays manual (`make deploy-prod`) until V1 is stable

---

## Phase 4 — V2 ideas (not now)

Captured here so they don't get lost. Do not start any of these without a clear V1 sign-off.

- Multi-user support (proper user table, onboarding flow, per-user timezone)
- Image recognition for food photos (Claude vision)
- Voice message transcription (audio → text via Whisper/Claude)
- Web dashboard for viewing trends (static site, reads from DynamoDB via API)
- Goal setting + weekly check-ins ("you set a goal of X, you're at Y")
- Reminder messages (e.g. "didn't see a meal log today, want to record one?")
- Integration with Apple Health / Google Fit for steps
- Better hunger-risk model (not just fiber-based)

---

## Known limitations of V1

- **Single user** — chat ID whitelist in `ALLOWED_CHAT_IDS`; multi-tenancy is not designed in.
- **No conversation memory** — each message is processed independently; "the same as yesterday" won't work.
- **No undo / edit** — if the LLM misclassifies, the user has to manually correct via the AWS Console.
- **Spanish-first** — prompts are in Spanish; English messages will mostly work but feedback will be in Spanish.
- **Telegram-only** — bound to one bot per stack. To migrate channels later you'd swap `shared/telegram.py`.
- **Cold starts** — First message after Lambda goes cold can take 3-5s. Acceptable for V1.

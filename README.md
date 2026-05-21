# Fitness Assistant

A personal Telegram bot that tracks fitness activity using natural language. Send a message in Spanish describing a meal, workout, or body metrics — the bot parses it with Claude and logs it to DynamoDB, then replies with personalized feedback.

## How it works

Three AWS Lambda functions:

- **Webhook** — receives Telegram messages in real time and responds immediately
- **Daily Summary** — fires every night at 11 PM UTC with a day recap
- **Weekly Trend** — fires every Sunday at 10 AM UTC with a 7-day analysis

All functions share a Lambda Layer that bundles the Anthropic SDK and internal shared code.

## Stack

- AWS Lambda + SAM
- DynamoDB (single-table design)
- Anthropic Claude Haiku
- Telegram Bot API

## Deploy

```bash
make deploy       # deploy to dev (us-west-1)
make deploy-prod  # deploy to prod
```

Secrets (API keys, allowed Telegram IDs) are stored in AWS Secrets Manager. Run `make setup-secrets` to configure them.

## Local testing

```bash
make build        # requires Docker Desktop
make local-test   # invoke WebhookFunction with a sample event
```

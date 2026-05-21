.PHONY: build deploy deploy-prod local-test setup-secrets logs logs-webhook logs-daily logs-weekly

build:
	sam build

deploy: build
	sam deploy --config-env default --no-confirm-changeset

deploy-prod: build
	sam deploy --config-env prod --no-confirm-changeset

# Quick local test of the webhook handler
local-test:
	sam local invoke WebhookFunction --event events/test-message.json

# Create/update secrets in Secrets Manager (dev)
setup-secrets:
	@echo "Setting up secrets for dev environment..."
	@read -p "ANTHROPIC_API_KEY: " ANTHROPIC_API_KEY; \
	read -p "TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN; \
	read -p "TELEGRAM_WEBHOOK_SECRET: " TELEGRAM_WEBHOOK_SECRET; \
	read -p "ALLOWED_CHAT_IDS (comma-separated): " ALLOWED_CHAT_IDS; \
	aws secretsmanager create-secret \
		--name fitness-assistant/dev \
		--secret-string "{\"ANTHROPIC_API_KEY\":\"$$ANTHROPIC_API_KEY\",\"TELEGRAM_BOT_TOKEN\":\"$$TELEGRAM_BOT_TOKEN\",\"TELEGRAM_WEBHOOK_SECRET\":\"$$TELEGRAM_WEBHOOK_SECRET\",\"ALLOWED_CHAT_IDS\":\"$$ALLOWED_CHAT_IDS\"}" \
		|| aws secretsmanager update-secret \
		--secret-id fitness-assistant/dev \
		--secret-string "{\"ANTHROPIC_API_KEY\":\"$$ANTHROPIC_API_KEY\",\"TELEGRAM_BOT_TOKEN\":\"$$TELEGRAM_BOT_TOKEN\",\"TELEGRAM_WEBHOOK_SECRET\":\"$$TELEGRAM_WEBHOOK_SECRET\",\"ALLOWED_CHAT_IDS\":\"$$ALLOWED_CHAT_IDS\"}"

logs:
	sam logs --stack-name fitness-assistant-dev --tail

logs-webhook:
	sam logs --stack-name fitness-assistant-dev --name WebhookFunction --tail

logs-daily:
	sam logs --stack-name fitness-assistant-dev --name DailySummaryFunction --tail

logs-weekly:
	sam logs --stack-name fitness-assistant-dev --name WeeklyTrendFunction --tail

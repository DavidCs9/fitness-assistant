.PHONY: build deploy deploy-prod local-test setup-secrets logs logs-webhook logs-daily logs-weekly

build:
	sam build

deploy: build
	sam deploy --config-env default

deploy-prod: build
	sam deploy --config-env prod

# Quick local test of the webhook handler
local-test:
	sam local invoke WebhookFunction --event events/test-message.json

# Create/update secrets in Secrets Manager (dev)
setup-secrets:
	@echo "Setting up secrets for dev environment..."
	@read -p "ANTHROPIC_API_KEY: " ANTHROPIC_API_KEY; \
	read -p "WHATSAPP_TOKEN: " WHATSAPP_TOKEN; \
	read -p "WHATSAPP_VERIFY_TOKEN: " WHATSAPP_VERIFY_TOKEN; \
	read -p "WHATSAPP_PHONE_NUMBER_ID: " WHATSAPP_PHONE_NUMBER_ID; \
	read -p "ALLOWED_PHONE_NUMBERS (comma-separated): " ALLOWED_PHONE_NUMBERS; \
	aws secretsmanager create-secret \
		--name fitness-assistant/dev \
		--secret-string "{\"ANTHROPIC_API_KEY\":\"$$ANTHROPIC_API_KEY\",\"WHATSAPP_TOKEN\":\"$$WHATSAPP_TOKEN\",\"WHATSAPP_VERIFY_TOKEN\":\"$$WHATSAPP_VERIFY_TOKEN\",\"WHATSAPP_PHONE_NUMBER_ID\":\"$$WHATSAPP_PHONE_NUMBER_ID\",\"ALLOWED_PHONE_NUMBERS\":\"$$ALLOWED_PHONE_NUMBERS\"}" \
		|| aws secretsmanager update-secret \
		--secret-id fitness-assistant/dev \
		--secret-string "{\"ANTHROPIC_API_KEY\":\"$$ANTHROPIC_API_KEY\",\"WHATSAPP_TOKEN\":\"$$WHATSAPP_TOKEN\",\"WHATSAPP_VERIFY_TOKEN\":\"$$WHATSAPP_VERIFY_TOKEN\",\"WHATSAPP_PHONE_NUMBER_ID\":\"$$WHATSAPP_PHONE_NUMBER_ID\",\"ALLOWED_PHONE_NUMBERS\":\"$$ALLOWED_PHONE_NUMBERS\"}"

logs:
	sam logs --stack-name fitness-assistant-dev --tail

logs-webhook:
	sam logs --stack-name fitness-assistant-dev --name WebhookFunction --tail

logs-daily:
	sam logs --stack-name fitness-assistant-dev --name DailySummaryFunction --tail

logs-weekly:
	sam logs --stack-name fitness-assistant-dev --name WeeklyTrendFunction --tail

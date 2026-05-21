.PHONY: build deploy deploy-prod local-test setup-secrets register-webhook register-webhook-prod logs logs-webhook logs-daily logs-weekly

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

register-webhook:
	$(eval URL := $(shell aws cloudformation describe-stacks --stack-name fitness-assistant-dev \
		--query "Stacks[0].Outputs[?OutputKey=='WebhookUrl'].OutputValue" \
		--output text --region us-west-1))
	$(eval TOKEN := $(shell aws secretsmanager get-secret-value --secret-id fitness-assistant/dev \
		--query SecretString --output text --region us-west-1 | python3 -c "import sys,json; print(json.load(sys.stdin)['TELEGRAM_BOT_TOKEN'])"))
	$(eval SECRET := $(shell aws secretsmanager get-secret-value --secret-id fitness-assistant/dev \
		--query SecretString --output text --region us-west-1 | python3 -c "import sys,json; print(json.load(sys.stdin)['TELEGRAM_WEBHOOK_SECRET'])"))
	@echo "Registering dev webhook: $(URL)"
	@curl -s -X POST "https://api.telegram.org/bot$(TOKEN)/setWebhook" \
		-d "url=$(URL)&secret_token=$(SECRET)" | python3 -m json.tool

register-webhook-prod:
	$(eval URL := $(shell aws cloudformation describe-stacks --stack-name fitness-assistant-prod \
		--query "Stacks[0].Outputs[?OutputKey=='WebhookUrl'].OutputValue" \
		--output text --region us-west-1))
	$(eval TOKEN := $(shell aws secretsmanager get-secret-value --secret-id fitness-assistant/prod \
		--query SecretString --output text --region us-west-1 | python3 -c "import sys,json; print(json.load(sys.stdin)['TELEGRAM_BOT_TOKEN'])"))
	$(eval SECRET := $(shell aws secretsmanager get-secret-value --secret-id fitness-assistant/prod \
		--query SecretString --output text --region us-west-1 | python3 -c "import sys,json; print(json.load(sys.stdin)['TELEGRAM_WEBHOOK_SECRET'])"))
	@echo "Registering prod webhook: $(URL)"
	@curl -s -X POST "https://api.telegram.org/bot$(TOKEN)/setWebhook" \
		-d "url=$(URL)&secret_token=$(SECRET)" | python3 -m json.tool

logs:
	sam logs --stack-name fitness-assistant-dev --tail

logs-webhook:
	sam logs --stack-name fitness-assistant-dev --name WebhookFunction --tail

logs-daily:
	sam logs --stack-name fitness-assistant-dev --name DailySummaryFunction --tail

logs-weekly:
	sam logs --stack-name fitness-assistant-dev --name WeeklyTrendFunction --tail

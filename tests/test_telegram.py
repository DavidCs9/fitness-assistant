from unittest.mock import patch, MagicMock
from shared import telegram


class TestParseIncomingMessage:
    def test_parses_text_message(self):
        body = {"message": {"chat": {"id": 12345}, "text": "hola"}}
        chat_id, text = telegram.parse_incoming_message(body)
        assert chat_id == "12345"
        assert text == "hola"

    def test_chat_id_is_string(self):
        body = {"message": {"chat": {"id": 99999}, "text": "test"}}
        chat_id, _ = telegram.parse_incoming_message(body)
        assert isinstance(chat_id, str)

    def test_edited_message_is_parsed(self):
        body = {"edited_message": {"chat": {"id": 42}, "text": "editado"}}
        chat_id, text = telegram.parse_incoming_message(body)
        assert chat_id == "42"
        assert text == "editado"

    def test_returns_none_text_when_no_text(self):
        # Voice/non-text messages: chat_id is returned so voice fallback can proceed
        body = {"message": {"chat": {"id": 12345}}}
        chat_id, text = telegram.parse_incoming_message(body)
        assert chat_id == "12345"
        assert text is None

    def test_returns_none_when_no_message(self):
        body = {}
        chat_id, text = telegram.parse_incoming_message(body)
        assert chat_id is None
        assert text is None

    def test_returns_none_when_no_chat_id(self):
        body = {"message": {"text": "hola"}}
        chat_id, text = telegram.parse_incoming_message(body)
        assert chat_id is None
        assert text is None


class TestVerifyTelegramSecret:
    def test_valid_secret_lowercase_header(self):
        event = {"headers": {"x-telegram-bot-api-secret-token": "mysecret"}}
        with patch("shared.telegram.Config.get_telegram_webhook_secret", return_value="mysecret"):
            assert telegram.verify_telegram_secret(event) is True

    def test_valid_secret_uppercase_header(self):
        event = {"headers": {"X-Telegram-Bot-Api-Secret-Token": "mysecret"}}
        with patch("shared.telegram.Config.get_telegram_webhook_secret", return_value="mysecret"):
            assert telegram.verify_telegram_secret(event) is True

    def test_invalid_secret(self):
        event = {"headers": {"x-telegram-bot-api-secret-token": "wrong"}}
        with patch("shared.telegram.Config.get_telegram_webhook_secret", return_value="mysecret"):
            assert telegram.verify_telegram_secret(event) is False

    def test_missing_header(self):
        event = {"headers": {}}
        with patch("shared.telegram.Config.get_telegram_webhook_secret", return_value="mysecret"):
            assert telegram.verify_telegram_secret(event) is False

    def test_missing_headers_key(self):
        event = {}
        with patch("shared.telegram.Config.get_telegram_webhook_secret", return_value="mysecret"):
            assert telegram.verify_telegram_secret(event) is False


class TestIsAuthorized:
    def test_authorized_user(self):
        with patch("shared.telegram.Config.get_allowed_chat_ids", return_value={"123", "456"}):
            assert telegram.is_authorized("123") is True

    def test_unauthorized_user(self):
        with patch("shared.telegram.Config.get_allowed_chat_ids", return_value={"123"}):
            assert telegram.is_authorized("999") is False

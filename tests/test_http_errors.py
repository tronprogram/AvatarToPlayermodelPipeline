"""Tests for form validation messages."""

from app.core.http_errors import first_validation_error_message


def test_first_validation_error_message_missing_field() -> None:
    errors = [{"type": "missing", "loc": ("body", "name"), "msg": "Field required"}]
    assert first_validation_error_message(errors) == "The 'name' field is required."

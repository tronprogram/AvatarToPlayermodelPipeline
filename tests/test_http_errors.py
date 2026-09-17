"""Tests for friendly HTTP/DB error mapping."""

import sqlite3

from app.core.http_errors import (
    first_validation_error_message,
    friendly_integrity_error,
    friendly_mutation_error,
)


def test_friendly_integrity_error_maps_unique_constraint() -> None:
    exc = sqlite3.IntegrityError("UNIQUE constraint failed: items.name")
    assert friendly_integrity_error(exc) == "That record already exists."


def test_friendly_mutation_error_hides_generic_internals() -> None:
    message = friendly_mutation_error("the item", "save", RuntimeError("secret db detail"))
    assert message == "Could not save the item. Try again."
    assert "secret db detail" not in message


def test_friendly_mutation_error_logs_the_raw_exception(caplog) -> None:
    try:
        raise sqlite3.IntegrityError("UNIQUE constraint failed: items.name")
    except sqlite3.IntegrityError as exc:
        message = friendly_mutation_error("the item", "save", exc)

    assert message == "That record already exists."
    assert "items.name" in caplog.text


def test_friendly_mutation_error_maps_value_error() -> None:
    assert friendly_mutation_error("the item", "save", ValueError("Item 9 was not found")) == (
        "Item 9 was not found"
    )


def test_first_validation_error_message_missing_field() -> None:
    errors = [{"type": "missing", "loc": ("body", "name"), "msg": "Field required"}]
    assert first_validation_error_message(errors) == "The 'name' field is required."

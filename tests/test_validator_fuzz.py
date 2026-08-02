"""
tests/test_validator_fuzz.py — Validator Fuzzing & Deny-list Adversarial Suite.
§5.6.5 solution.md & eval.md L2: Zero bypass of validator bounds under adversarial LLM output.
"""

import pytest
import json
from discovery.core.validator import validate_llm_response, validate_reason_line


def test_validator_unknown_id_rejection():
    """Asserts that returning an ID outside whitelist discards whole response."""
    whitelist = {101, 102}
    raw_payload = json.dumps({
        "ranked": [
            {"id": 999, "rank": 1, "reason_code": "COMPLEMENT", "reason_line": "Goes with your cart"}
        ]
    })
    is_valid, data, msg = validate_llm_response(raw_payload, whitelist)
    assert is_valid is False
    assert "Unknown candidate ID 999" in msg


def test_validator_denylist_term_sanitization():
    """Asserts that deny-list claims (discount, returns, expiry, urgency, health) are replaced with fallback templates."""
    whitelist = {101}

    # Payload with deny-list terms ("discount", "free", "guarantee", "hurry")
    raw_payload = json.dumps({
        "ranked": [
            {"id": 101, "rank": 1, "reason_code": "COMPLEMENT", "reason_line": "Get 50% discount free guarantee!"}
        ]
    })

    is_valid, data, msg = validate_llm_response(raw_payload, whitelist)
    assert is_valid is True
    assert data["ranked"][0]["reason_line"] == "Pairs with your current basket"  # Replaced with template


def test_validator_line_length_truncation():
    """Asserts reason_line <= 40 chars truncation."""
    long_line = "This is an extremely long reason line that exceeds forty characters by a lot"
    is_valid, clean_line = validate_reason_line(long_line)
    assert is_valid is True
    assert len(clean_line) <= 40


def test_validator_malformed_json_resilience():
    """Asserts graceful rejection on malformed JSON or prompt injection."""
    whitelist = {101}
    bad_json = "```json { 'ranked': [{'id': 101, 'reason_line': 'hello'}] ```"

    is_valid, data, msg = validate_llm_response(bad_json, whitelist)
    assert is_valid is False
    assert "JSON parse error" in msg

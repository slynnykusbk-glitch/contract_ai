from contract_review_app.core.privacy import redact_pii, scrub_llm_output


def test_pii_redaction_and_scrub():
    text = (
        "Contact John Doe at john@example.com or +44 1234 567890, NI AB123456C, "
        "postcode SW1A 1AA on 01/02/2024."
    )
    redacted, pii_map = redact_pii(text)
    assert "john@example.com" not in redacted
    assert "+44 1234 567890" not in redacted
    assert "AB123456C" not in redacted
    assert "SW1A 1AA" not in redacted
    assert "John Doe" not in redacted
    assert "01/02/2024" not in redacted

    llm_out = (
        "Draft for John Doe: contact at john@example.com, phone +44 1234 567890, "
        "NI AB123456C, postcode SW1A 1AA on 01/02/2024."
    )
    scrubbed = scrub_llm_output(llm_out, pii_map)
    for original in [
        "john@example.com",
        "+44 1234 567890",
        "AB123456C",
        "SW1A 1AA",
        "John Doe",
        "01/02/2024",
    ]:
        assert original not in scrubbed

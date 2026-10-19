from adex_tools.connectors.mail_safety import safe_metadata


def test_authentication_subjects_are_not_exposed_to_agent_context():
    for subject in [
        "Your verification code is 123456",
        "验证码 123456",
        "Reset your password: https://private.example/token",
    ]:
        headers, redacted = safe_metadata(
            [{"name": "Subject", "value": subject}, {"name": "X-Login-Url", "value": "private-token"}]
        )
        assert redacted
        assert "123456" not in str(headers) and "private-token" not in str(headers)


def test_ordinary_message_keeps_only_requested_metadata():
    headers, redacted = safe_metadata(
        [
            {"name": "Subject", "value": "Project launch"},
            {"name": "From", "value": "team@example.test"},
            {"name": "Body", "value": "not metadata"},
        ]
    )
    assert not redacted
    assert len(headers) == 2 and "not metadata" not in str(headers)

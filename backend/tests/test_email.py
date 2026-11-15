import pytest

from app.alerts.email import DISCLAIMER, EmailError, build_message, mask, send_email
from app.config import Settings


def test_message_has_text_html_and_disclaimer():
    msg = build_message("farmer@example.com", "Alert", "Body", "<p>Body</p>",
                        "SowSmart Alerts <alerts@example.com>")
    assert msg["To"] == "farmer@example.com" and msg["Subject"] == "Alert"
    text = msg.get_body(preferencelist=("plain",)).get_content()
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert DISCLAIMER in text and DISCLAIMER in html


@pytest.mark.parametrize("bad", ["not-an-email", "a@b.com, c@d.com", "a@b.com\nBcc: x@y.com"])
def test_only_one_clean_recipient_is_allowed(bad):
    with pytest.raises(EmailError):
        build_message(bad, "s", "t", None, "from@example.com")


def test_unconfigured_email_fails_without_network():
    with pytest.raises(EmailError, match="not configured"):
        send_email("farmer@example.com", "s", "t", settings=Settings(_env_file=None))


def test_addresses_are_masked():
    assert mask("esample@school.edu") == "e***@school.edu"


def test_an_unreachable_smtp_server_is_an_email_error(monkeypatch):
    import smtplib

    def refuse(*args, **kwargs):
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr(smtplib, "SMTP", refuse)
    settings = Settings(_env_file=None, smtp_host="smtp.example.com", smtp_username="u",
                        smtp_password="p", alert_email_from="from@example.com")
    with pytest.raises(EmailError, match="ConnectionRefusedError"):
        send_email("farmer@example.com", "s", "t", settings=settings)

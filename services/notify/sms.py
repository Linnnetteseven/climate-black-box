"""SMS delivery for divergence alerts. Not connected.

Africa's Talking is the intended provider: it reaches Kenyan networks
directly, which is where every site we monitor is, and its sandbox lets the
whole path be exercised before a shilling is spent.

This module is a seam, not an implementation. It exists so the shape of the
call is settled and visible in review, and so that `send_alert_sms` has one
place to live when credentials arrive. It deliberately refuses rather than
silently doing nothing: a notification system that fails quietly is worse than
one that is obviously absent, because people rely on the silence meaning
nothing is wrong.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


class SmsNotConfigured(RuntimeError):
    """Raised when delivery is attempted without a configured provider."""


@dataclass(frozen=True)
class SmsCredentials:
    username: str
    api_key: str
    sender_id: str | None = None


def load_credentials() -> SmsCredentials | None:
    """Read Africa's Talking credentials from the environment, if present."""
    username = os.getenv("AT_USERNAME")
    api_key = os.getenv("AT_API_KEY")
    if not username or not api_key:
        return None
    return SmsCredentials(username, api_key, os.getenv("AT_SENDER_ID"))


def is_configured() -> bool:
    return load_credentials() is not None


def compose_alert(project_name: str, period_key: str, deviation: float) -> str:
    """The message body.

    Kept short and literal on purpose. An SMS is read on a cheap phone in a
    hurry, so it carries the site, the month, the size of the move and where
    to check -- and makes no claim about the cause, exactly as the alert in
    the product makes none.
    """
    return (
        f"Climate Black Box: {project_name} is {abs(deviation):.3f} NDVI below "
        f"its approved trajectory for {period_key}. No cause established. "
        f"Check climateblackbox.duckdns.org"
    )


def send_alert_sms(phone: str, message: str) -> None:
    """Deliver one alert. Raises until a provider is configured."""
    creds = load_credentials()
    if creds is None:
        raise SmsNotConfigured(
            "Africa's Talking is not configured. Set AT_USERNAME and AT_API_KEY "
            "to enable delivery; until then the waitlist records interest only."
        )
    # Deliberately unimplemented. Wiring the HTTP call without a sandbox
    # account to test it against would be guessing at an API in production.
    raise SmsNotConfigured(
        "Credentials are present but delivery is not implemented yet."
    )

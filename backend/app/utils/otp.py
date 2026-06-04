"""
OTP utility — MOCK/STUB implementation for MVP.

In production replace `_send_otp` with a real SMS gateway (e.g. Twilio).
The storage dict is process-local; for multi-process deployments replace it
with Redis or a DB-backed store before going to production.
"""

import logging
import random
import string
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OTP_LENGTH = 4
# Five minutes strikes the balance between usability and security for a
# phone-based verification flow.  Shorten for higher-security contexts.
OTP_TTL_SECONDS = 300


@dataclass
class OTPRecord:
    """
    Holds a single pending OTP for one phone number.

    Instances live in ``_otp_store`` until either the code is verified
    (consumed immediately) or the TTL expires (evicted lazily on next lookup).
    """

    code: str
    expires_at: datetime


# In-memory store: phone -> OTPRecord
_otp_store: dict[str, OTPRecord] = {}


def generate_otp() -> str:
    """Return a random numeric OTP string of length OTP_LENGTH."""
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def save_otp(phone: str, code: str) -> None:
    """Persist OTP in the in-memory store with an expiry timestamp."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=OTP_TTL_SECONDS)
    _otp_store[phone] = OTPRecord(code=code, expires_at=expires_at)


def verify_otp(phone: str, code: str) -> tuple[bool, str]:
    """
    Validate the submitted OTP against the stored record.

    Returns (True, "") on success or (False, reason) on failure.
    The record is consumed (deleted) after a successful verification.
    """
    record = _otp_store.get(phone)

    if record is None:
        return False, "No OTP found for this number. Please request a new one."

    if datetime.now(timezone.utc) > record.expires_at:
        _otp_store.pop(phone, None)
        return False, "OTP has expired. Please request a new one."

    if record.code != code:
        return False, "Invalid OTP. Please try again."

    # Consume the OTP so it cannot be replayed.
    _otp_store.pop(phone, None)
    return True, ""


def send_otp(phone: str, code: str) -> None:
    """
    STUB: Print OTP to terminal.
    Replace this function body with a real SMS gateway call in production.
    """
    logger.info("=" * 50)
    logger.info(f"[OTP STUB] Phone: {phone}  |  OTP: {code}")
    logger.info("=" * 50)
    # TODO: integrate SMS gateway here, e.g.:
    # twilio_client.messages.create(to=phone, from_=TWILIO_FROM, body=f"Your KaamWala OTP: {code}")

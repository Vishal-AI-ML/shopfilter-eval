from __future__ import annotations

import smtplib
import uuid
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol


class EmailVerificationDeliveryError(RuntimeError):
    pass


class EmailVerificationMailer(Protocol):
    def send(
        self, *, recipient: str, display_name: str, verification_url: str
    ) -> None: ...


@dataclass(frozen=True)
class EmailVerificationMessage:
    recipient: str
    verification_url: str


@dataclass
class InMemoryEmailVerificationMailer:
    messages: list[EmailVerificationMessage] = field(default_factory=list)

    def send(
        self, *, recipient: str, display_name: str, verification_url: str
    ) -> None:
        self.messages.append(
            EmailVerificationMessage(
                recipient=recipient, verification_url=verification_url
            )
        )


@dataclass(frozen=True)
class FileEmailVerificationMailer:
    directory: Path

    def send(
        self, *, recipient: str, display_name: str, verification_url: str
    ) -> None:
        message = _message(
            recipient=recipient,
            display_name=display_name,
            verification_url=verification_url,
            sender="no-reply@shopfilter.local",
        )
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            destination = self.directory / f"email-verification-{uuid.uuid4().hex}.eml"
            destination.write_text(message.as_string(), encoding="utf-8")
        except OSError as exc:
            raise EmailVerificationDeliveryError from exc


@dataclass(frozen=True)
class SmtpEmailVerificationMailer:
    host: str
    port: int
    sender: str
    use_starttls: bool = False
    username: str | None = None
    password: str | None = None

    def send(
        self, *, recipient: str, display_name: str, verification_url: str
    ) -> None:
        message = _message(
            recipient=recipient,
            display_name=display_name,
            verification_url=verification_url,
            sender=self.sender,
        )
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                if self.use_starttls:
                    smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password or "")
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailVerificationDeliveryError from exc


def _message(
    *, recipient: str, display_name: str, verification_url: str, sender: str
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Verify your ShopFilter Eval email"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Hello {display_name},\n\n"
        "Verify ownership of your email address using the single-use link below. "
        "The link expires automatically.\n\n"
        f"{verification_url}\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )
    return message

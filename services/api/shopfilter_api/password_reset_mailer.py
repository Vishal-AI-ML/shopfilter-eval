from __future__ import annotations

import smtplib
import uuid
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol


class PasswordResetDeliveryError(RuntimeError):
    pass


class PasswordResetMailer(Protocol):
    def send(
        self, *, recipient: str, display_name: str, reset_url: str
    ) -> None: ...


@dataclass(frozen=True)
class PasswordResetMessage:
    recipient: str
    reset_url: str


@dataclass
class InMemoryPasswordResetMailer:
    messages: list[PasswordResetMessage] = field(default_factory=list)

    def send(self, *, recipient: str, display_name: str, reset_url: str) -> None:
        self.messages.append(PasswordResetMessage(recipient=recipient, reset_url=reset_url))


@dataclass(frozen=True)
class FilePasswordResetMailer:
    directory: Path

    def send(self, *, recipient: str, display_name: str, reset_url: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Reset your ShopFilter Eval password"
        message["From"] = "no-reply@shopfilter.local"
        message["To"] = recipient
        message.set_content(
            f"Hello {display_name},\n\n"
            "Use this single-use password reset link:\n\n"
            f"{reset_url}\n"
        )
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            destination = self.directory / f"password-reset-{uuid.uuid4().hex}.eml"
            destination.write_text(message.as_string(), encoding="utf-8")
        except OSError as exc:
            raise PasswordResetDeliveryError from exc


@dataclass(frozen=True)
class SmtpPasswordResetMailer:
    host: str
    port: int
    sender: str
    use_starttls: bool = False
    username: str | None = None
    password: str | None = None

    def send(self, *, recipient: str, display_name: str, reset_url: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Reset your ShopFilter Eval password"
        message["From"] = self.sender
        message["To"] = recipient
        message.set_content(
            f"Hello {display_name},\n\n"
            "Use the link below to reset your ShopFilter Eval password. "
            "The link is single-use and expires automatically.\n\n"
            f"{reset_url}\n\n"
            "If you did not request this change, you can ignore this email.\n"
        )
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                if self.use_starttls:
                    smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password or "")
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise PasswordResetDeliveryError from exc

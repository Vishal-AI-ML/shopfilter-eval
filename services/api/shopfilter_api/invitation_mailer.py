from __future__ import annotations

import smtplib
import uuid
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol


class InvitationDeliveryError(RuntimeError):
    pass


class InvitationMailer(Protocol):
    def send(self, *, recipient: str, organization_name: str, role: str, invitation_url: str) -> None: ...


@dataclass(frozen=True)
class InvitationMessage:
    recipient: str
    invitation_url: str


@dataclass
class InMemoryInvitationMailer:
    messages: list[InvitationMessage] = field(default_factory=list)

    def send(self, *, recipient: str, organization_name: str, role: str, invitation_url: str) -> None:
        self.messages.append(InvitationMessage(recipient=recipient, invitation_url=invitation_url))


@dataclass(frozen=True)
class FileInvitationMailer:
    directory: Path

    def send(self, *, recipient: str, organization_name: str, role: str, invitation_url: str) -> None:
        message = _message(recipient=recipient, organization_name=organization_name, role=role, invitation_url=invitation_url, sender="no-reply@shopfilter.local")
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / f"organization-invitation-{uuid.uuid4().hex}.eml").write_text(message.as_string(), encoding="utf-8")
        except OSError as exc:
            raise InvitationDeliveryError from exc


@dataclass(frozen=True)
class SmtpInvitationMailer:
    host: str
    port: int
    sender: str
    use_starttls: bool = False
    username: str | None = None
    password: str | None = None

    def send(self, *, recipient: str, organization_name: str, role: str, invitation_url: str) -> None:
        message = _message(recipient=recipient, organization_name=organization_name, role=role, invitation_url=invitation_url, sender=self.sender)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                if self.use_starttls:
                    smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password or "")
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise InvitationDeliveryError from exc


def _message(*, recipient: str, organization_name: str, role: str, invitation_url: str, sender: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"Join {organization_name} on ShopFilter Eval"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"You were invited to join {organization_name} as {role}.\n\n"
        "Use this single-use invitation link. It expires automatically.\n\n"
        f"{invitation_url}\n\n"
        "If you were not expecting this invitation, you can ignore this email.\n"
    )
    return message

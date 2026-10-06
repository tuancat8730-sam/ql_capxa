"""Outgoing e-mail (SPEC 4.10): SMTP for local dev (mailpit), SES in AWS, memory in tests."""

import asyncio
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

import boto3

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str


class Mailer(Protocol):
    async def send(self, email: Email) -> None: ...


@dataclass
class MemoryMailer:
    """Collects messages instead of sending them; `fail_for` simulates a refused recipient."""

    sent: list[Email] = field(default_factory=list)
    fail_for: set[str] = field(default_factory=set)

    async def send(self, email: Email) -> None:
        if email.to in self.fail_for:
            raise RuntimeError(f"refused: {email.to}")
        self.sent.append(email)


@dataclass(frozen=True)
class SmtpMailer:
    host: str
    port: int
    sender: str

    def _send_blocking(self, email: Email) -> None:
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.text)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(msg)

    async def send(self, email: Email) -> None:
        await asyncio.to_thread(self._send_blocking, email)


@dataclass(frozen=True)
class SesMailer:
    sender: str
    region: str

    def _send_blocking(self, email: Email) -> None:
        client = boto3.client("ses", region_name=self.region)
        client.send_email(
            Source=self.sender,
            Destination={"ToAddresses": [email.to]},
            Message={
                "Subject": {"Data": email.subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": email.text, "Charset": "UTF-8"}},
            },
        )

    async def send(self, email: Email) -> None:
        await asyncio.to_thread(self._send_blocking, email)


def build_mailer(settings: Settings | None = None) -> Mailer:
    settings = settings or get_settings()
    backend = settings.mail_backend
    if backend == "ses":
        return SesMailer(settings.ses_sender, settings.aws_region)
    if backend == "smtp":
        return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.ses_sender)
    return MemoryMailer()

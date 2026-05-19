from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any


class EmailSender:
    def send_email(self, to_email: str, subject: str, html: str, smtp_config: dict[str, Any]) -> tuple[bool, str]:
        host = smtp_config.get("smtp_host") or smtp_config.get("host")
        port = int(smtp_config.get("smtp_port") or smtp_config.get("port") or 587)
        user = smtp_config.get("smtp_user") or smtp_config.get("user") or ""
        password = smtp_config.get("smtp_pass") or smtp_config.get("password") or ""
        sender = smtp_config.get("from") or user

        if not host or not sender:
            return False, "SMTP host and sender are required"

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = to_email
        message.set_content("TerminalHub HTML report attached.")
        message.add_alternative(html, subtype="html")
        message.add_attachment(html.encode("utf-8"), maintype="text", subtype="html", filename="terminalhub_report.html")

        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=20) as server:
                    if user:
                        server.login(user, password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(host, port, timeout=20) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    if user:
                        server.login(user, password)
                    server.send_message(message)
            return True, "Email sent successfully"
        except Exception as exc:
            return False, str(exc)

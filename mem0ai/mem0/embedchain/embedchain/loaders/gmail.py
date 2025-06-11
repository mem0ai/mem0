import base64
import hashlib
import logging
import os
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from textwrap import dedent
from typing import Optional

from bs4 import BeautifulSoup

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    raise ImportError(
        'Gmail requires extra dependencies. Install with `pip install --upgrade "embedchain[gmail]"`'
    ) from None

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string

logger = logging.getLogger(__name__)


class GmailReader:
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, query: str, service=None, results_per_page: int = 10):
        self.query = query
        self.service = service or self._initialize_service()
        self.results_per_page = results_per_page

    @staticmethod
    def _initialize_service():
        credentials = GmailReader._get_credentials()
        return build("gmail", "v1", credentials=credentials)

    @staticmethod
    def _get_credentials():
        if not os.path.exists("credentials.json"):
            raise FileNotFoundError("Missing 'credentials.json'. Download it from your Google Developer account.")

        creds = (
            Credentials.from_authorized_user_file("token.json", GmailReader.SCOPES)
            if os.path.exists("token.json")
            else None
        )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", GmailReader.SCOPES)
                creds = flow.run_local_server(port=8080)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return creds

    def load_emails(self) -> list[dict]:
        response = self.service.users().messages().list(userId="me", q=self.query).execute()
        messages = response.get("messages", [])

        return [self._parse_email(self._get_email(message["id"])) for message in messages]

    def _get_email(self, message_id: str):
        raw_message = self.service.users().messages().get(userId="me", id=message_id, format="raw").execute()
        return base64.urlsafe_b64decode(raw_message["raw"])

    def _parse_email(self, raw_email) -> dict:
        mime_msg = message_from_bytes(raw_email)
        return {
            "subject": self._get_header(mime_msg, "Subject"),
            "from": self._get_header(mime_msg, "From"),
            "to": self._get_header(mime_msg, "To"),
            "date": self._format_date(mime_msg),
            "body": self._get_body(mime_msg),
        }

    @staticmethod
    def _get_header(mime_msg, header_name: str) -> str:
        return mime_msg.get(header_name, "")

    @staticmethod
    def _format_date(mime_msg) -> Optional[str]:
        date_header = GmailReader._get_header(mime_msg, "Date")
        return parsedate_to_datetime(date_header).isoformat() if date_header else None

    @staticmethod
    def _get_body(mime_msg) -> str:
        def decode_payload(part):
            charset = part.get_content_charset() or "utf-8"
            try:
                return part.get_payload(decode=True).decode(charset)
            except UnicodeDecodeError:
                return part.get_payload(decode=True).decode(charset, errors="replace")

        if mime_msg.is_multipart():
            for part in mime_msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get("Content-Disposition"))

                if ctype == "text/plain" and "attachment" not in cdispo:
                    return decode_payload(part)
                elif ctype == "text/html":
                    return decode_payload(part)
        else:
            return decode_payload(mime_msg)

        return ""


class GmailLoader(BaseLoader):
    def load_data(self, query: str):
        reader = GmailReader(query=query)
        emails = reader.load_emails()
        logger.info(f"Gmail Loader: {len(emails)} emails found for query '{query}'")

        data = []
        for email in emails:
            content = self._process_email(email)
            data.append({"content": content, "meta_data": email})

        return {"doc_id": self._generate_doc_id(query, data), "data": data}

    @staticmethod
    def _process_email(email: dict) -> str:
        content = BeautifulSoup(email["body"], "html.parser").get_text()
        content = clean_string(content)
        return dedent(
            f"""
            Email from '{email['from']}' to '{email['to']}'
            Subject: {email['subject']}
            Date: {email['date']}
            Content: {content}
        """
        )

    @staticmethod
    def _generate_doc_id(query: str, data: list[dict]) -> str:
        content_strings = [email["content"] for email in data]
        return hashlib.sha256((query + ", ".join(content_strings)).encode()).hexdigest()

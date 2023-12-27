import base64
import hashlib
import logging
import os
import quopri
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from textwrap import dedent

from bs4 import BeautifulSoup

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


class GmailReader:
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, query, service=None, results_per_page=10):
        self.query = query
        self.service = service
        self.results_per_page = results_per_page

    def _get_credentials(self):
        """Get valid user credentials from storage or generate them."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise ImportError(
                'Gmail loader requires extra dependencies. Install with `pip install --upgrade "embedchain[gmail]"`'
            ) from None

        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", self.SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", self.SCOPES)
                creds = flow.run_local_server(port=8080)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return creds

    def load_data(self):
        """Load emails from the user's Gmail account based on the query."""
        try:
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                'Gmail loader requires extra dependencies. Install with `pip install --upgrade "embedchain[gmail]"`'
            ) from None

        if not self.service:
            self.service = build("gmail", "v1", credentials=self._get_credentials())

        results = []
        response = self.service.users().messages().list(userId="me", q=self.query).execute()
        messages = response.get("messages", [])

        for message in messages:
            msg = self.service.users().messages().get(userId="me", id=message["id"], format="raw").execute()
            msg_bytes = base64.urlsafe_b64decode(msg["raw"])
            mime_msg = message_from_bytes(msg_bytes)
            results.append(self.parse_message(mime_msg))

        return results

    def parse_message(self, mime_msg):
        """Parse a MIME message into a more readable format."""
        parsed_email = {
            "subject": self._get_mime_header(mime_msg, "Subject"),
            "from": self._get_mime_header(mime_msg, "From"),
            "to": self._get_mime_header(mime_msg, "To"),
            "date": self._parse_date(mime_msg),
            "body": self._get_mime_body(mime_msg),
        }
        return parsed_email

    def _get_mime_header(self, mime_msg, header_name):
        """Extract a header value from a MIME message."""
        header = mime_msg.get(header_name)
        return header if header else ""

    def _parse_date(self, mime_msg):
        """Parse and format the date from a MIME message."""
        date_header = self._get_mime_header(mime_msg, "Date")
        if date_header:
            try:
                return parsedate_to_datetime(date_header)
            except Exception:
                return ""
        return ""

    def _get_mime_body(self, mime_msg):
        """Extract the body from a MIME message."""
        if mime_msg.is_multipart():
            for part in mime_msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get("Content-Disposition"))

                # skip any text/plain (txt) attachments
                if ctype == "text/plain" and "attachment" not in cdispo:
                    return part.get_payload(decode=True).decode()  # decode
                elif ctype == "text/html":
                    return part.get_payload(decode=True).decode()  # to decode
        else:
            return mime_msg.get_payload(decode=True).decode()

        return ""


def get_header(text: str, header: str) -> str:
    start_string_position = text.find(header)
    pos_start = text.find(":", start_string_position) + 1
    pos_end = text.find("\n", pos_start)
    header = text[pos_start:pos_end]
    return header.strip()


class GmailLoader(BaseLoader):
    def load_data(self, query):
        """Load data from gmail."""
        if not os.path.isfile("credentials.json"):
            raise FileNotFoundError(
                "You must download the valid credentials file from your google \
                dev account. Refer this `https://cloud.google.com/docs/authentication/api-keys`"
            )

        loader = GmailReader(query=query, service=None, results_per_page=20)
        documents = loader.load_data()
        logging.info(f"Gmail Loader: {len(documents)} mails found for query- {query}")

        data = []
        data_contents = []
        logging.info(f"Gmail Loader: {len(documents)} mails found")
        for document in documents:
            original_size = len(document.text)

            snippet = document.metadata.get("snippet")
            meta_data = {
                "url": document.metadata.get("id"),
                "date": get_header(document.text, "Date"),
                "subject": get_header(document.text, "Subject"),
                "from": get_header(document.text, "From"),
                "to": get_header(document.text, "To"),
                "search_query": query,
            }

            # Decode
            decoded_bytes = quopri.decodestring(document.text)
            decoded_str = decoded_bytes.decode("utf-8", errors="replace")

            # Slice
            mail_start = decoded_str.find("<!DOCTYPE")
            email_data = decoded_str[mail_start:]

            # Web Page HTML Processing
            soup = BeautifulSoup(email_data, "html.parser")

            tags_to_exclude = [
                "nav",
                "aside",
                "form",
                "header",
                "noscript",
                "svg",
                "canvas",
                "footer",
                "script",
                "style",
            ]

            for tag in soup(tags_to_exclude):
                tag.decompose()

            ids_to_exclude = ["sidebar", "main-navigation", "menu-main-menu"]
            for id in ids_to_exclude:
                tags = soup.find_all(id=id)
                for tag in tags:
                    tag.decompose()

            classes_to_exclude = [
                "elementor-location-header",
                "navbar-header",
                "nav",
                "header-sidebar-wrapper",
                "blog-sidebar-wrapper",
                "related-posts",
            ]

            for class_name in classes_to_exclude:
                tags = soup.find_all(class_=class_name)
                for tag in tags:
                    tag.decompose()

            content = soup.get_text()
            content = clean_string(content)

            cleaned_size = len(content)
            if original_size != 0:
                logging.info(
                    f"[{id}] Cleaned page size: {cleaned_size} characters, down from {original_size} (shrunk: {original_size-cleaned_size} chars, {round((1-(cleaned_size/original_size)) * 100, 2)}%)"  # noqa:E501
                )

            result = f"""
            email from '{meta_data.get('from')}' to '{meta_data.get('to')}'
            subject: {meta_data.get('subject')}
            date: {meta_data.get('date')}
            preview: {snippet}
            content: f{content}
            """
            data_content = dedent(result)
            data.append({"content": data_content, "meta_data": meta_data})
            data_contents.append(data_content)
        doc_id = hashlib.sha256((query + ", ".join(data_contents)).encode()).hexdigest()
        response_data = {"doc_id": doc_id, "data": data}
        return response_data

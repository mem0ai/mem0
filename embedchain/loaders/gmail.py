import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import logging

from embedchain.constants import GMAIL_ADDRESS_SEPARATOR_IN_APP_INPUT
from embedchain.loaders.base_loader import BaseLoader

from langchain.chat_loaders.gmail import GMailLoader

from langchain.chat_loaders.utils import (
    map_ai_messages,
)

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_user_cred(cred_path):
    if os.path.exists(cred_path):
        creds = Credentials.from_authorized_user_file(cred_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    cred_path, 
                    SCOPES
                    )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(cred_path, 'w') as token:
                token.write(creds.to_json())
        return creds
    else:
        logging.error(f"Error finding the google authentication key.")
        raise FileNotFoundError(f"Cant find the google auth key file. Follow the instructions at `https://docs.embedchain.ai/data-sources/gmail` to setup GMAILLoader Correctly.")

class GMAILLoader(BaseLoader):
    @staticmethod
    def load_date(content):
        email_senders = str(content).split(GMAIL_ADDRESS_SEPARATOR_IN_APP_INPUT)
        cred_path = os.getenv("GOOGLE_CRED_PATH")
        try:
            creds = get_user_cred(cred_path)
            loader = GMailLoader(creds=creds, n=100, raise_error=True)
            data = loader.load()
            training_data = []
            for sender in email_senders:
                training_data.append(list(map_ai_messages(data, sender=sender)))
            print("GMAIL DATA: ", data, training_data)
        except FileNotFoundError as e:
            pass
        except:
            pass
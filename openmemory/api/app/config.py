import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

USER_ID = os.getenv("USER", "default_user")
DEFAULT_APP_ID = "openmemory"
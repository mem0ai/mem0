import os

USER_ID = os.getenv("USER", "default_user")
# Use the username as the default app name to ensure per-user isolation
DEFAULT_APP_ID = USER_ID
"""Reset a user's password by email. Run inside the `mem0` container."""

import os
import sys

from sqlalchemy import select

from auth import hash_password
from db import SessionLocal
from models import User

MIN_PASSWORD_LENGTH = 8


def main() -> int:
    email = os.environ.get("EMAIL", "").strip()
    password = os.environ.get("PASSWORD", "")

    if not email or not password:
        print("error: EMAIL and PASSWORD environment variables are required.", file=sys.stderr)
        return 2

    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"error: password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"error: no user found with email {email}.", file=sys.stderr)
            return 1

        user.password_hash = hash_password(password)
        db.commit()

    print(f"Password reset for {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

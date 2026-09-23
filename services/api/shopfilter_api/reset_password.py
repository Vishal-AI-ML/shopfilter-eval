from __future__ import annotations

import argparse
import getpass
import os
from datetime import UTC, datetime

from sqlalchemy import select

from services.api.shopfilter_api.auth import hash_password, normalize_email
from services.api.shopfilter_api.config import get_settings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.models import AuthSessionRecord, UserRecord


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset a local user password and revoke all existing sessions"
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--password-env", default="SHOPFILTER_RESET_PASSWORD")
    arguments = parser.parse_args()

    password = os.environ.get(arguments.password_env)
    if password is None:
        password = getpass.getpass("New password: ")
        confirmation = getpass.getpass("Confirm new password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match")
    try:
        encoded = hash_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    database = Database(get_settings().database_url)
    try:
        with database.session() as session:
            user = session.scalar(
                select(UserRecord).where(
                    UserRecord.email == normalize_email(arguments.email)
                )
            )
            if user is None:
                raise SystemExit("User not found")
            user.password_hash = encoded
            active_sessions = list(
                session.scalars(
                    select(AuthSessionRecord).where(
                        AuthSessionRecord.user_id == user.id,
                        AuthSessionRecord.revoked_at.is_(None),
                    )
                ).all()
            )
            revoked_at = datetime.now(UTC)
            for record in active_sessions:
                record.revoked_at = revoked_at
            session.commit()
            print(f"Password reset for user: {user.id}")
            print(f"Sessions revoked: {len(active_sessions)}")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import getpass
import os

from sqlalchemy import select

from services.api.shopfilter_api.auth import (
    MembershipRole,
    hash_password,
    normalize_email,
)
from services.api.shopfilter_api.config import get_settings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.models import (
    MembershipRecord,
    Organization,
    UserRecord,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an initial owner without exposing its password on the command line"
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--organization-slug", required=True)
    parser.add_argument("--password-env", default="SHOPFILTER_BOOTSTRAP_PASSWORD")
    arguments = parser.parse_args()
    password = os.environ.get(arguments.password_env)
    if password is None:
        password = getpass.getpass("Bootstrap password: ")

    database = Database(get_settings().database_url)
    try:
        with database.session() as session:
            organization = session.scalar(
                select(Organization).where(Organization.slug == arguments.organization_slug)
            )
            if organization is None:
                raise SystemExit("Organization not found")
            email = normalize_email(arguments.email)
            display_name = arguments.display_name.strip()
            if not display_name:
                raise SystemExit("Display name cannot be blank")
            user = session.scalar(select(UserRecord).where(UserRecord.email == email))
            if user is None:
                user = UserRecord(
                    email=email,
                    display_name=display_name,
                    password_hash=hash_password(password),
                    is_active=True,
                )
                session.add(user)
                session.flush()
            membership = session.scalar(
                select(MembershipRecord).where(
                    MembershipRecord.organization_id == organization.id,
                    MembershipRecord.user_id == user.id,
                )
            )
            if membership is None:
                session.add(
                    MembershipRecord(
                        organization_id=organization.id,
                        user_id=user.id,
                        role=MembershipRole.OWNER.value,
                    )
                )
            elif membership.role != MembershipRole.OWNER.value:
                raise SystemExit("Existing membership is not OWNER; refusing to overwrite it")
            session.commit()
            print(f"Owner user: {user.id}")
            print(f"Organization: {organization.id}")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()

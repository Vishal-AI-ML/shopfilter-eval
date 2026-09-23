
from __future__ import annotations

import uuid

from sqlalchemy import select

from services.api.shopfilter_api.config import get_settings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.models import Organization, Project

DEMO_ORGANIZATION_ID = uuid.UUID("e5150000-0000-4000-8000-000000000001")
DEMO_PROJECT_ID = uuid.UUID("e5150000-0000-4000-8000-000000000002")


def seed_demo() -> None:
    database = Database(get_settings().database_url)
    try:
        with database.session() as session:
            organization = session.scalar(
                select(Organization).where(Organization.slug == "shopfilter-demo")
            )
            if organization is None:
                organization = Organization(
                    id=DEMO_ORGANIZATION_ID,
                    name="ShopFilter Demo",
                    slug="shopfilter-demo",
                )
                session.add(organization)
                session.flush()
            project = session.get(Project, DEMO_PROJECT_ID)
            if project is None:
                session.add(
                    Project(
                        id=DEMO_PROJECT_ID,
                        organization_id=organization.id,
                        name="Demo Search Quality",
                        slug="demo-search-quality",
                    )
                )
            session.commit()
    finally:
        database.dispose()
    print(f"Demo organization: {DEMO_ORGANIZATION_ID}")
    print(f"Demo project: {DEMO_PROJECT_ID}")


if __name__ == "__main__":
    seed_demo()

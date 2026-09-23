from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from services.api.shopfilter_api.database import Base, Database
from services.api.shopfilter_api.models import WorkerHeartbeatRecord
from services.worker.main import _record_heartbeat


def test_worker_heartbeat_is_upserted(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'worker.sqlite3'}")
    try:
        Base.metadata.create_all(database.engine)
        _record_heartbeat(database, "worker-test", redis_connected=True)
        _record_heartbeat(database, "worker-test", redis_connected=False)
        with Session(database.engine) as session:
            heartbeat = session.get(WorkerHeartbeatRecord, "worker-test")
            assert heartbeat is not None
            assert heartbeat.metadata_json == {"redis_connected": False}
            assert heartbeat.last_seen_at is not None
    finally:
        database.dispose()

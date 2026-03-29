import hashlib
import os
from pathlib import Path
import requests
from celery import Celery
from .db import get_conn

celery_app = Celery(
    "worker",
    broker=os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@rabbitmq:5672//"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
)

# Queue routing
celery_app.conf.task_routes = {
    "worker.download_twic_issue": {"queue": "twic.download"},
    "worker.parse_twic_issue": {"queue": "twic.parse"},
    "worker.aggregate_twic_issue": {"queue": "twic.aggregate"},
}

STORAGE = Path(os.getenv("TWIC_STORAGE_DIR", "/data/twic"))
STORAGE.mkdir(parents=True, exist_ok=True)


@celery_app.task(name="worker.download_twic_issue", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def download_twic_issue(issue: int, url: str):
    target = STORAGE / f"twic{issue}g.zip"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    target.write_bytes(r.content)
    checksum = hashlib.sha256(r.content).hexdigest()

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE twic_sources
            SET status='downloaded', downloaded_at=NOW(), checksum=%s, updated_at=NOW()
            WHERE twic_issue_number=%s
            """,
            (checksum, issue),
        )

    parse_twic_issue.delay(issue, str(target))
    return {"issue": issue, "file": str(target), "checksum": checksum}


@celery_app.task(name="worker.parse_twic_issue", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def parse_twic_issue(issue: int, zip_path: str):
    # M1 placeholder: parsing logic to be expanded in M2 with PGN extraction.
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE twic_sources
            SET status='parsed', updated_at=NOW()
            WHERE twic_issue_number=%s
            """,
            (issue,),
        )
    aggregate_twic_issue.delay(issue)
    return {"issue": issue, "zip_path": zip_path, "status": "parsed"}


@celery_app.task(name="worker.aggregate_twic_issue", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def aggregate_twic_issue(issue: int):
    # M1 placeholder: aggregation logic to be expanded when game_positions are populated.
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE twic_sources
            SET status='aggregated', updated_at=NOW()
            WHERE twic_issue_number=%s
            """,
            (issue,),
        )
    return {"issue": issue, "status": "aggregated"}

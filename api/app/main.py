from fastapi import FastAPI
from .db import get_conn
from .twic import discover_twic_sources
from .celery_client import celery_app

app = FastAPI(title="chess-teacher-ai API", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/twic/status")
def twic_status(limit: int = 25):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT twic_issue_number, source_url, status, downloaded_at, updated_at
            FROM twic_sources
            ORDER BY twic_issue_number DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return {
        "count": len(rows),
        "items": [
            {
                "issue": r[0],
                "url": r[1],
                "status": r[2],
                "downloaded_at": r[3].isoformat() if r[3] else None,
                "updated_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ],
    }


@app.post("/api/twic/sync")
def twic_sync(limit: int = 50):
    discovered = discover_twic_sources(limit=limit)
    inserted = 0
    with get_conn() as conn, conn.cursor() as cur:
        for item in discovered:
            cur.execute(
                """
                INSERT INTO twic_sources (twic_issue_number, source_url, status)
                VALUES (%s, %s, 'queued')
                ON CONFLICT (twic_issue_number) DO UPDATE
                SET source_url = EXCLUDED.source_url,
                    updated_at = NOW()
                RETURNING id
                """,
                (item["issue"], item["url"]),
            )
            row = cur.fetchone()
            if row:
                inserted += 1
                celery_app.send_task("worker.download_twic_issue", args=[item["issue"], item["url"]])

    return {
        "discovered": len(discovered),
        "queued": inserted,
        "message": "TWIC sync queued to worker",
    }

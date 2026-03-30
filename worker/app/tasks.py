import hashlib
import io
import os
import shlex
from pathlib import Path
import requests
import chess.pgn
import chess.engine
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
    "worker.analyze_game_lc0": {"queue": "analysis.lc0"},
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


def _score_to_fields(score):
    cp = score.white().score(mate_score=100000)
    mate = score.white().mate()
    if mate is not None:
        return None, int(mate)
    return (int(cp) if cp is not None else None), None


@celery_app.task(name="worker.analyze_game_lc0", autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def analyze_game_lc0(game_id: str, depth: int = 12):
    engine_cmd = os.getenv("LEELAZERO_CMD", "lc0")
    cmd = shlex.split(engine_cmd)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT pgn_text FROM games WHERE id=%s", (game_id,))
        row = cur.fetchone()
        if not row:
            return {"game_id": game_id, "error": "game_not_found"}

        game = chess.pgn.read_game(io.StringIO(row[0]))
        board = game.board()
        ply = 0

        with chess.engine.SimpleEngine.popen_uci(cmd) as engine:
            for move in game.mainline_moves():
                info = engine.analyse(board, chess.engine.Limit(depth=depth))
                score = info.get("score")
                d_out = info.get("depth", depth)
                pv = info.get("pv")
                pv_str = " ".join(m.uci() for m in pv) if pv else None
                cp, mate = _score_to_fields(score) if score else (None, None)

                cur.execute(
                    """
                    INSERT INTO move_evaluations(
                        game_id, ply_index, fen, move_uci, engine_name, depth,
                        score_cp, score_mate, pv
                    ) VALUES (%s,%s,%s,%s,'lc0',%s,%s,%s,%s)
                    ON CONFLICT (game_id, ply_index, engine_name)
                    DO UPDATE SET
                      fen=EXCLUDED.fen,
                      move_uci=EXCLUDED.move_uci,
                      depth=EXCLUDED.depth,
                      score_cp=EXCLUDED.score_cp,
                      score_mate=EXCLUDED.score_mate,
                      pv=EXCLUDED.pv,
                      analyzed_at=NOW()
                    """,
                    (game_id, ply, board.fen(), move.uci(), d_out, cp, mate, pv_str),
                )

                board.push(move)
                ply += 1

        conn.commit()

    return {"game_id": game_id, "plies": ply, "depth": depth, "engine": "lc0"}

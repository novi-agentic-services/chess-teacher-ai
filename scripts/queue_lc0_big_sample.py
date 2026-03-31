#!/usr/bin/env python3
"""
Queue a large LC0 labeling job from TWIC games.

This script selects games that do not yet have LC0 evaluations at the target depth,
then queues worker.analyze_game_lc0 tasks in batches.
"""

import argparse
import os
import time

import psycopg
from celery import Celery


def get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-games", type=int, default=int(get_env("TARGET_GAMES", "50000")))
    ap.add_argument("--depth", type=int, default=int(get_env("ANALYSIS_DEPTH", "20")))
    ap.add_argument("--min-plies", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=1000)
    ap.add_argument("--sleep-ms", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = get_env("DATABASE_URL", "postgresql://app:app@localhost:5432/chess_teacher_ai").replace("postgresql+psycopg", "postgresql")
    broker = get_env("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
    backend = get_env("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    celery_app = Celery("queue-big-sample", broker=broker, backend=backend)

    with psycopg.connect(db) as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH ply_totals AS (
              SELECT game_id, COUNT(*) AS total_plies
              FROM game_positions
              GROUP BY game_id
            ), eval_totals AS (
              SELECT game_id, COUNT(*) AS eval_plies
              FROM move_evaluations
              WHERE engine_name='lc0' AND depth=%s
              GROUP BY game_id
            )
            SELECT g.id
            FROM games g
            JOIN ply_totals p ON p.game_id = g.id
            LEFT JOIN eval_totals e ON e.game_id = g.id
            WHERE p.total_plies >= %s
              AND COALESCE(e.eval_plies, 0) = 0
            ORDER BY g.game_date DESC NULLS LAST, g.id
            LIMIT %s
            """,
            (args.depth, args.min_plies, args.target_games),
        )
        ids = [str(r[0]) for r in cur.fetchall()]

    queued = 0
    if not args.dry_run:
        for i, gid in enumerate(ids, start=1):
            celery_app.send_task("worker.analyze_game_lc0", args=[gid, args.depth], queue="analysis.lc0")
            queued += 1
            if i % args.batch_size == 0:
                print({"progress": i, "queued": queued})
                time.sleep(args.sleep_ms / 1000.0)

    print(
        {
            "target_games": args.target_games,
            "selected_games": len(ids),
            "queued_games": queued,
            "depth": args.depth,
            "min_plies": args.min_plies,
            "dry_run": args.dry_run,
        }
    )


if __name__ == "__main__":
    main()

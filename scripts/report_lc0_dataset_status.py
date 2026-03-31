#!/usr/bin/env python3
import argparse
import os

import psycopg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=int(os.getenv("ANALYSIS_DEPTH", "20")))
    args = ap.parse_args()

    db = os.getenv("DATABASE_URL", "postgresql://app:app@localhost:5432/chess_teacher_ai").replace("postgresql+psycopg", "postgresql")

    with psycopg.connect(db) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM games")
        total_games = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM game_positions")
        total_positions = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM move_evaluations
            WHERE engine_name='lc0' AND depth=%s
            """,
            (args.depth,),
        )
        eval_rows = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(DISTINCT game_id)
            FROM move_evaluations
            WHERE engine_name='lc0' AND depth=%s
            """,
            (args.depth,),
        )
        eval_games = cur.fetchone()[0]

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
            SELECT COUNT(*)
            FROM ply_totals p
            LEFT JOIN eval_totals e ON e.game_id = p.game_id
            WHERE COALESCE(e.eval_plies, 0) = 0
            """,
            (args.depth,),
        )
        remaining_games = cur.fetchone()[0]

    print(
        {
            "depth": args.depth,
            "total_games": int(total_games),
            "total_positions": int(total_positions),
            "lc0_eval_rows": int(eval_rows),
            "lc0_eval_games": int(eval_games),
            "remaining_unlabeled_games": int(remaining_games),
        }
    )


if __name__ == "__main__":
    main()

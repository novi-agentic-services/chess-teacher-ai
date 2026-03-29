#!/usr/bin/env python3
import argparse
import hashlib
import io
import os
import uuid
from pathlib import Path

import chess.pgn
import psycopg

BASE = Path(__file__).resolve().parents[1]
PGN_DIR = BASE / "data" / "pgn"


def db_conn():
    url = os.getenv("DATABASE_URL", "postgresql://app:app@localhost:5432/chess_teacher_ai")
    url = url.replace("postgresql+psycopg", "postgresql")
    return psycopg.connect(url)


def game_hash(game: chess.pgn.Game) -> str:
    key = "|".join([
        game.headers.get("Event", ""),
        game.headers.get("Site", ""),
        game.headers.get("Date", ""),
        game.headers.get("Round", ""),
        game.headers.get("White", ""),
        game.headers.get("Black", ""),
        game.headers.get("Result", ""),
        str(list(game.mainline_moves())),
    ])
    return hashlib.sha256(key.encode()).hexdigest()


def upsert_position(cur, fen: str) -> int:
    cur.execute(
        "INSERT INTO positions (fen) VALUES (%s) ON CONFLICT (fen) DO UPDATE SET fen=EXCLUDED.fen RETURNING id",
        (fen,),
    )
    return cur.fetchone()[0]


def ingest(limit_games: int | None = None, dry_run: bool = False):
    files = sorted(PGN_DIR.glob("*.pgn"))
    inserted = 0
    skipped = 0
    gp_rows = 0

    if dry_run:
        for p in files:
            with p.open("r", errors="ignore") as f:
                while True:
                    if limit_games and (inserted + skipped) >= limit_games:
                        return inserted, skipped, gp_rows
                    game = chess.pgn.read_game(f)
                    if game is None:
                        break
                    _ = game_hash(game)
                    board = game.board()
                    for _m in game.mainline_moves():
                        gp_rows += 1
                        board.push(_m)
                    inserted += 1
        return inserted, skipped, gp_rows

    with db_conn() as conn, conn.cursor() as cur:
        for p in files:
            with p.open("r", errors="ignore") as f:
                while True:
                    if limit_games and (inserted + skipped) >= limit_games:
                        conn.commit()
                        return inserted, skipped, gp_rows
                    game = chess.pgn.read_game(f)
                    if game is None:
                        break

                    gh = game_hash(game)
                    cur.execute("SELECT id FROM games WHERE game_hash=%s", (gh,))
                    if cur.fetchone():
                        skipped += 1
                        continue

                    gid = uuid.uuid4()
                    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
                    pgn_text = game.accept(exporter)

                    date_raw = game.headers.get("Date", "")
                    game_date = None
                    if len(date_raw) >= 10 and date_raw[4] == '.' and date_raw[7] == '.':
                        y, m, d = date_raw.split('.')[:3]
                        if y.isdigit() and m.isdigit() and d.isdigit():
                            game_date = f"{y}-{m}-{d}"

                    cur.execute(
                        """
                        INSERT INTO games (
                          id, game_hash, event, site, round, game_date,
                          white_player, black_player, white_elo, black_elo,
                          result, eco, opening, variation, pgn_text
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            str(gid), gh,
                            game.headers.get("Event"), game.headers.get("Site"), game.headers.get("Round"), game_date,
                            game.headers.get("White"), game.headers.get("Black"),
                            int(game.headers["WhiteElo"]) if game.headers.get("WhiteElo", "").isdigit() else None,
                            int(game.headers["BlackElo"]) if game.headers.get("BlackElo", "").isdigit() else None,
                            game.headers.get("Result"), game.headers.get("ECO"), game.headers.get("Opening"), game.headers.get("Variation"), pgn_text,
                        ),
                    )

                    board = game.board()
                    ply = 0
                    for move in game.mainline_moves():
                        pid = upsert_position(cur, board.fen())
                        san = board.san(move)
                        uci = move.uci()
                        cur.execute(
                            "INSERT INTO game_positions (game_id, ply_index, position_id, move_san, move_uci) VALUES (%s,%s,%s,%s,%s)",
                            (str(gid), ply, pid, san, uci),
                        )
                        gp_rows += 1
                        board.push(move)
                        ply += 1

                    inserted += 1
                    if inserted % 200 == 0:
                        conn.commit()

        conn.commit()
    return inserted, skipped, gp_rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-games", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    i, s, gp = ingest(args.limit_games, args.dry_run)
    print({"inserted_games": i, "skipped_duplicates": s, "game_positions_rows": gp, "dry_run": args.dry_run})

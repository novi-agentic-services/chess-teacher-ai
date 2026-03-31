from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from .db import get_conn
from .twic import discover_twic_sources
from .celery_client import celery_app

app = FastAPI(title="chess-teacher-ai API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/games/search")
def games_search(
    q: Optional[str] = Query(default=None, description="Player/Event text search"),
    white: Optional[str] = None,
    black: Optional[str] = None,
    eco: Optional[str] = None,
    result: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    where = []
    params = []

    if q:
        tokens = [t.strip() for t in q.split() if t.strip()]
        if tokens:
            for t in tokens:
                where.append("(white_player ILIKE %s OR black_player ILIKE %s OR event ILIKE %s)")
                tv = f"%{t}%"
                params.extend([tv, tv, tv])
        else:
            where.append("(white_player ILIKE %s OR black_player ILIKE %s OR event ILIKE %s)")
            qv = f"%{q}%"
            params.extend([qv, qv, qv])
    if white:
        where.append("white_player ILIKE %s")
        params.append(f"%{white}%")
    if black:
        where.append("black_player ILIKE %s")
        params.append(f"%{black}%")
    if eco:
        where.append("eco = %s")
        params.append(eco)
    if result:
        where.append("result = %s")
        params.append(result)
    if year_from:
        where.append("EXTRACT(YEAR FROM game_date) >= %s")
        params.append(year_from)
    if year_to:
        where.append("EXTRACT(YEAR FROM game_date) <= %s")
        params.append(year_to)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    sql = f"""
        SELECT id, event, site, round, game_date, white_player, black_player,
               white_elo, black_elo, result, eco, opening, variation
        FROM games
        {where_sql}
        ORDER BY game_date DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    return {
        "count": len(rows),
        "items": [
            {
                "id": str(r[0]),
                "event": r[1],
                "site": r[2],
                "round": r[3],
                "date": r[4].isoformat() if r[4] else None,
                "white": r[5],
                "black": r[6],
                "white_elo": r[7],
                "black_elo": r[8],
                "result": r[9],
                "eco": r[10],
                "opening": r[11],
                "variation": r[12],
            }
            for r in rows
        ],
    }


@app.get("/api/games/{game_id}")
def game_get(game_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, event, site, round, game_date, white_player, black_player,
                   white_elo, black_elo, result, eco, opening, variation, pgn_text
            FROM games
            WHERE id = %s
            """,
            (game_id,),
        )
        r = cur.fetchone()

    if not r:
        return {"found": False, "id": game_id}

    return {
        "found": True,
        "item": {
            "id": str(r[0]),
            "event": r[1],
            "site": r[2],
            "round": r[3],
            "date": r[4].isoformat() if r[4] else None,
            "white": r[5],
            "black": r[6],
            "white_elo": r[7],
            "black_elo": r[8],
            "result": r[9],
            "eco": r[10],
            "opening": r[11],
            "variation": r[12],
            "pgn": r[13],
        },
    }


@app.post("/api/games/{game_id}/analyze")
def analyze_game(game_id: str, depth: int = Query(default=12, ge=6, le=40)):
    task = celery_app.send_task("worker.analyze_game_lc0", args=[game_id, depth])
    return {"queued": True, "task_id": task.id, "game_id": game_id, "engine": "lc0", "depth": depth}


@app.get("/api/games/{game_id}/evaluations")
def game_evaluations(game_id: str, engine: str = "lc0", limit: int = Query(default=200, le=5000), offset: int = 0):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ply_index, fen, move_uci, depth, score_cp, score_mate, pv, analyzed_at
            FROM move_evaluations
            WHERE game_id=%s AND engine_name=%s
            ORDER BY ply_index ASC
            LIMIT %s OFFSET %s
            """,
            (game_id, engine, limit, offset),
        )
        rows = cur.fetchall()
    return {
        "count": len(rows),
        "game_id": game_id,
        "engine": engine,
        "items": [
            {
                "ply": r[0], "fen": r[1], "move_uci": r[2], "depth": r[3],
                "score_cp": r[4], "score_mate": r[5], "pv": r[6],
                "analyzed_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ],
    }


@app.get("/api/players/profile")
def player_profile(name: str):
    tokens = [t.strip() for t in name.split() if t.strip()]
    if not tokens:
        return {
            "player_query": name,
            "info": {"total_games": 0, "first_game": None, "last_game": None, "distinct_opponents": 0},
            "scores": {"white": {"wins": 0, "draws": 0, "losses": 0}, "black": {"wins": 0, "draws": 0, "losses": 0}},
            "common_openings": [],
            "rating_chart": [],
        }

    clauses = []
    params = []
    for t in tokens:
        like = f"%{t}%"
        clauses.append("(white_player ILIKE %s OR black_player ILIKE %s)")
        params.extend([like, like])
    where_tokens = " AND ".join(clauses)
    p = tuple(params)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
              COUNT(*) AS total_games,
              MIN(game_date) AS first_game,
              MAX(game_date) AS last_game,
              COUNT(DISTINCT CASE WHEN white_player ILIKE %s THEN black_player ELSE white_player END) AS opponents
            FROM games
            WHERE {where_tokens}
            """,
            tuple([f"%{tokens[0]}%"] + list(p)),
        )
        total_games, first_game, last_game, opponents = cur.fetchone()

        cur.execute(
            f"""
            SELECT
              SUM(CASE WHEN white_player ILIKE %s AND result='1-0' THEN 1 ELSE 0 END) AS white_wins,
              SUM(CASE WHEN white_player ILIKE %s AND result='1/2-1/2' THEN 1 ELSE 0 END) AS white_draws,
              SUM(CASE WHEN white_player ILIKE %s AND result='0-1' THEN 1 ELSE 0 END) AS white_losses,
              SUM(CASE WHEN black_player ILIKE %s AND result='0-1' THEN 1 ELSE 0 END) AS black_wins,
              SUM(CASE WHEN black_player ILIKE %s AND result='1/2-1/2' THEN 1 ELSE 0 END) AS black_draws,
              SUM(CASE WHEN black_player ILIKE %s AND result='1-0' THEN 1 ELSE 0 END) AS black_losses
            FROM games
            WHERE {where_tokens}
            """,
            tuple([f"%{tokens[0]}%"] * 6 + list(p)),
        )
        ww, wd, wl, bw, bd, bl = cur.fetchone()

        cur.execute(
            f"""
            SELECT COALESCE(opening, 'Unknown Opening') AS opening, COUNT(*) AS c
            FROM games
            WHERE {where_tokens}
            GROUP BY COALESCE(opening, 'Unknown Opening')
            ORDER BY c DESC
            LIMIT 10
            """,
            p,
        )
        openings = cur.fetchall()

        cur.execute(
            f"""
            WITH r AS (
              SELECT date_trunc('month', game_date) AS m, white_elo AS elo
              FROM games
              WHERE white_elo IS NOT NULL AND game_date IS NOT NULL AND {where_tokens}
              UNION ALL
              SELECT date_trunc('month', game_date) AS m, black_elo AS elo
              FROM games
              WHERE black_elo IS NOT NULL AND game_date IS NOT NULL AND {where_tokens}
            )
            SELECT m::date, ROUND(AVG(elo))::int AS avg_elo, COUNT(*) AS samples
            FROM r
            GROUP BY m
            ORDER BY m
            """,
            p + p,
        )
        ratings = cur.fetchall()

    return {
        "player_query": name,
        "info": {
            "total_games": int(total_games or 0),
            "first_game": first_game.isoformat() if first_game else None,
            "last_game": last_game.isoformat() if last_game else None,
            "distinct_opponents": int(opponents or 0),
        },
        "scores": {
            "white": {"wins": int(ww or 0), "draws": int(wd or 0), "losses": int(wl or 0)},
            "black": {"wins": int(bw or 0), "draws": int(bd or 0), "losses": int(bl or 0)},
        },
        "common_openings": [{"opening": o[0], "games": int(o[1])} for o in openings],
        "rating_chart": [
            {"month": r[0].isoformat() if r[0] else None, "avg_elo": int(r[1] or 0), "samples": int(r[2] or 0)}
            for r in ratings
        ],
    }


@app.get("/api/positions/tree")
def position_tree(fen: str, limit: int = Query(default=40, le=200)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM positions WHERE fen = %s", (fen,))
        row = cur.fetchone()
        if not row:
            return {"found": False, "fen": fen, "moves": []}

        pid = row[0]
        cur.execute(
            """
            SELECT move_uci, games_count, white_wins, draws, black_wins,
                   white_win_pct, draw_pct, black_win_pct
            FROM position_move_stats
            WHERE position_id = %s
            ORDER BY games_count DESC, move_uci ASC
            LIMIT %s
            """,
            (pid, limit),
        )
        rows = cur.fetchall()

    return {
        "found": True,
        "fen": fen,
        "position_id": pid,
        "move_count": len(rows),
        "moves": [
            {
                "move_uci": r[0],
                "games": r[1],
                "white_wins": r[2],
                "draws": r[3],
                "black_wins": r[4],
                "white_win_pct": float(r[5]),
                "draw_pct": float(r[6]),
                "black_win_pct": float(r[7]),
            }
            for r in rows
        ],
    }

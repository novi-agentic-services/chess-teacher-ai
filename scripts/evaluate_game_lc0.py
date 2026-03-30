#!/usr/bin/env python3
import argparse
import os
import shlex
import chess
import chess.pgn
import chess.engine
import psycopg


def get_conn():
    url = os.getenv('DATABASE_URL', 'postgresql://app:app@localhost:5432/chess_teacher_ai')
    url = url.replace('postgresql+psycopg', 'postgresql')
    return psycopg.connect(url)


def score_to_fields(score):
    # score is PovScore from side to move perspective.
    cp = score.white().score(mate_score=100000)
    mate = score.white().mate()
    if mate is not None:
        return None, int(mate)
    return (int(cp) if cp is not None else None), None


def evaluate_game(game_id: str, depth: int, multipv: int = 1):
    engine_cmd = os.getenv('LEELAZERO_CMD', 'lc0')
    cmd = shlex.split(engine_cmd)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute('SELECT pgn_text FROM games WHERE id=%s', (game_id,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f'game not found: {game_id}')
        pgn_text = row[0]

        game = chess.pgn.read_game(io_from_text(pgn_text))
        board = game.board()

        with chess.engine.SimpleEngine.popen_uci(cmd) as engine:
            ply = 0
            for move in game.mainline_moves():
                fen = board.fen()
                info = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
                # multipv=1 returns dict; normalize
                if isinstance(info, list):
                    info = info[0]

                score = info.get('score')
                depth_out = info.get('depth', depth)
                pv = info.get('pv')
                pv_str = ' '.join(m.uci() for m in pv) if pv else None
                cp, mate = score_to_fields(score) if score else (None, None)

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
                    (game_id, ply, fen, move.uci(), depth_out, cp, mate, pv_str),
                )

                board.push(move)
                ply += 1

        conn.commit()
    return ply


def io_from_text(text: str):
    import io
    return io.StringIO(text)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--game-id', required=True)
    ap.add_argument('--depth', type=int, default=12)
    args = ap.parse_args()
    n = evaluate_game(args.game_id, args.depth)
    print({'game_id': args.game_id, 'evaluated_plies': n, 'depth': args.depth})

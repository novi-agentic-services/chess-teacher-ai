#!/usr/bin/env python3
import argparse
import csv
import math
import os
from collections import defaultdict
from datetime import date

import chess
import psycopg


PIECE_TYPES = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]
PIECE_NAMES = {
    chess.PAWN: "pawns",
    chess.KNIGHT: "knights",
    chess.BISHOP: "bishops",
    chess.ROOK: "rooks",
    chess.QUEEN: "queens",
}
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
CENTER = [chess.D4, chess.E4, chess.D5, chess.E5]
EXT_CENTER = [chess.C3, chess.D3, chess.E3, chess.F3, chess.C4, chess.D4, chess.E4, chess.F4,
              chess.C5, chess.D5, chess.E5, chess.F5, chess.C6, chess.D6, chess.E6, chess.F6]


def get_conn():
    url = os.getenv("DATABASE_URL", "postgresql://app:app@localhost:5432/chess_teacher_ai")
    url = url.replace("postgresql+psycopg", "postgresql")
    return psycopg.connect(url)


def count_piece(board, piece_type, color):
    return len(board.pieces(piece_type, color))


def phase_score(board):
    max_non_pawn = 2 * (2 * 320 + 2 * 330 + 2 * 500 + 900)
    cur_non_pawn = 0
    for pt, val in [(chess.KNIGHT, 320), (chess.BISHOP, 330), (chess.ROOK, 500), (chess.QUEEN, 900)]:
        cur_non_pawn += val * (len(board.pieces(pt, chess.WHITE)) + len(board.pieces(pt, chess.BLACK)))
    # 1 = opening-ish, 0 = endgame-ish
    return cur_non_pawn / max_non_pawn if max_non_pawn else 0.0


def mobility(board, color):
    b = board.copy(stack=False)
    b.turn = color
    return b.legal_moves.count()


def control_count(board, color, squares):
    return sum(1 for s in squares if board.is_attacked_by(color, s))


def king_ring(board, color):
    ksq = board.king(color)
    if ksq is None:
        return []
    ring = [ksq]
    ring.extend(chess.SquareSet(chess.BB_KING_ATTACKS[ksq]))
    return ring


def king_attackers(board, color):
    enemy = not color
    ksq = board.king(color)
    if ksq is None:
        return 0
    return len(board.attackers(enemy, ksq))


def king_ring_attacked(board, color):
    enemy = not color
    ring = king_ring(board, color)
    return sum(1 for s in ring if board.is_attacked_by(enemy, s))


def pawn_files(board, color):
    files = defaultdict(int)
    for sq in board.pieces(chess.PAWN, color):
        files[chess.square_file(sq)] += 1
    return files


def doubled_pawns(board, color):
    pf = pawn_files(board, color)
    return sum(max(0, c - 1) for c in pf.values())


def isolated_pawns(board, color):
    pawns = list(board.pieces(chess.PAWN, color))
    pf = pawn_files(board, color)
    isolated = 0
    for sq in pawns:
        f = chess.square_file(sq)
        if pf.get(f - 1, 0) == 0 and pf.get(f + 1, 0) == 0:
            isolated += 1
    return isolated


def pawn_islands(board, color):
    files = sorted(pawn_files(board, color).keys())
    if not files:
        return 0
    islands = 1
    for i in range(1, len(files)):
        if files[i] != files[i - 1] + 1:
            islands += 1
    return islands


def passed_pawns(board, color):
    enemy = not color
    passed = 0
    for sq in board.pieces(chess.PAWN, color):
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        ahead_ranks = range(r + 1, 8) if color == chess.WHITE else range(0, r)
        blocked = False
        for ff in [f - 1, f, f + 1]:
            if ff < 0 or ff > 7:
                continue
            for rr in ahead_ranks:
                if board.piece_at(chess.square(ff, rr)) == chess.Piece(chess.PAWN, enemy):
                    blocked = True
                    break
            if blocked:
                break
        if not blocked:
            passed += 1
    return passed


def hanging_pieces(board, color):
    enemy = not color
    hanging = 0
    for sq, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue
        if board.is_attacked_by(enemy, sq) and not board.is_attacked_by(color, sq):
            hanging += 1
    return hanging


def rooks_open_files(board, color):
    enemy = not color
    own_pf = pawn_files(board, color)
    enemy_pf = pawn_files(board, enemy)
    openf = 0
    semio = 0
    for sq in board.pieces(chess.ROOK, color):
        f = chess.square_file(sq)
        own = own_pf.get(f, 0)
        opp = enemy_pf.get(f, 0)
        if own == 0 and opp == 0:
            openf += 1
        elif own == 0 and opp > 0:
            semio += 1
    return openf, semio


def knight_outposts(board, color):
    enemy = not color
    outposts = 0
    for sq in board.pieces(chess.KNIGHT, color):
        rank = chess.square_rank(sq)
        if color == chess.WHITE and rank < 3:
            continue
        if color == chess.BLACK and rank > 4:
            continue
        defended_by_pawn = any(
            (board.piece_at(s) == chess.Piece(chess.PAWN, color))
            for s in board.attackers(color, sq)
        )
        enemy_pawn_attack = any(
            (board.piece_at(s) == chess.Piece(chess.PAWN, enemy))
            for s in board.attackers(enemy, sq)
        )
        if defended_by_pawn and not enemy_pawn_attack:
            outposts += 1
    return outposts


def best_capture_gain(board, color):
    best = 0
    b = board.copy(stack=False)
    b.turn = color
    for mv in b.legal_moves:
        if not b.is_capture(mv):
            continue
        victim = b.piece_at(mv.to_square)
        attacker = b.piece_at(mv.from_square)
        if victim and attacker:
            gain = PIECE_VALUES[victim.piece_type] - PIECE_VALUES[attacker.piece_type]
            if gain > best:
                best = gain
    return best


def opening_family(opening):
    if not opening:
        return "Unknown"
    return opening.split(",")[0].strip().split(" ")[0].strip() or "Unknown"


def compute_features(fen):
    board = chess.Board(fen)
    row = {}
    row["side_to_move"] = 1 if board.turn == chess.WHITE else 0
    row["phase"] = round(phase_score(board), 6)

    for pt in PIECE_TYPES:
        nm = PIECE_NAMES[pt]
        w = count_piece(board, pt, chess.WHITE)
        b = count_piece(board, pt, chess.BLACK)
        row[f"w_{nm}"] = w
        row[f"b_{nm}"] = b
        row[f"imb_{nm}"] = w - b

    row["bishop_pair_white"] = 1 if row["w_bishops"] >= 2 else 0
    row["bishop_pair_black"] = 1 if row["b_bishops"] >= 2 else 0

    row["legal_moves_total"] = board.legal_moves.count()
    row["white_mobility"] = mobility(board, chess.WHITE)
    row["black_mobility"] = mobility(board, chess.BLACK)

    row["center_control_white"] = control_count(board, chess.WHITE, CENTER)
    row["center_control_black"] = control_count(board, chess.BLACK, CENTER)
    row["extended_center_control_white"] = control_count(board, chess.WHITE, EXT_CENTER)
    row["extended_center_control_black"] = control_count(board, chess.BLACK, EXT_CENTER)

    row["white_in_check"] = 1 if board.turn == chess.WHITE and board.is_check() else 0
    row["black_in_check"] = 1 if board.turn == chess.BLACK and board.is_check() else 0
    row["white_king_attackers"] = king_attackers(board, chess.WHITE)
    row["black_king_attackers"] = king_attackers(board, chess.BLACK)
    row["white_king_ring_attacked"] = king_ring_attacked(board, chess.WHITE)
    row["black_king_ring_attacked"] = king_ring_attacked(board, chess.BLACK)

    row["white_passed_pawns"] = passed_pawns(board, chess.WHITE)
    row["black_passed_pawns"] = passed_pawns(board, chess.BLACK)
    row["white_isolated_pawns"] = isolated_pawns(board, chess.WHITE)
    row["black_isolated_pawns"] = isolated_pawns(board, chess.BLACK)
    row["white_doubled_pawns"] = doubled_pawns(board, chess.WHITE)
    row["black_doubled_pawns"] = doubled_pawns(board, chess.BLACK)
    row["white_pawn_islands"] = pawn_islands(board, chess.WHITE)
    row["black_pawn_islands"] = pawn_islands(board, chess.BLACK)

    row["white_hanging_pieces"] = hanging_pieces(board, chess.WHITE)
    row["black_hanging_pieces"] = hanging_pieces(board, chess.BLACK)
    rwo, rws = rooks_open_files(board, chess.WHITE)
    rbo, rbs = rooks_open_files(board, chess.BLACK)
    row["white_rooks_open_files"] = rwo
    row["white_rooks_semiopen_files"] = rws
    row["black_rooks_open_files"] = rbo
    row["black_rooks_semiopen_files"] = rbs
    row["white_knight_outposts"] = knight_outposts(board, chess.WHITE)
    row["black_knight_outposts"] = knight_outposts(board, chess.BLACK)
    row["best_capture_gain_white"] = best_capture_gain(board, chess.WHITE)
    row["best_capture_gain_black"] = best_capture_gain(board, chess.BLACK)
    return row


def split_dates(rows):
    dated = sorted([r["game_date"] for r in rows if r["game_date"] is not None])
    if not dated:
        for r in rows:
            r["split"] = "train"
        return

    n = len(dated)
    t1 = dated[int(n * 0.8)]
    t2 = dated[int(n * 0.9)]

    for r in rows:
        gd = r["game_date"]
        if gd is None or gd <= t1:
            r["split"] = "train"
        elif gd <= t2:
            r["split"] = "valid"
        else:
            r["split"] = "test"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="data/features")
    ap.add_argument("--limit", type=int, default=200000)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    rows = []
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT me.game_id, me.ply_index, me.fen, me.score_cp, g.game_date, g.eco, g.opening
            FROM move_evaluations me
            JOIN games g ON g.id = me.game_id
            WHERE me.engine_name='lc0' AND me.score_cp IS NOT NULL
            ORDER BY g.game_date NULLS LAST, me.game_id, me.ply_index
            LIMIT %s
            """,
            (args.limit,),
        )
        for game_id, ply, fen, score_cp, game_date, eco, opening in cur.fetchall():
            feat = compute_features(fen)
            cp_raw = int(score_cp)
            cp_clip = max(-1000, min(1000, cp_raw))
            feat.update(
                {
                    "game_id": str(game_id),
                    "ply_index": int(ply),
                    "fen": fen,
                    "game_date": game_date,
                    "eco": eco or "UNK",
                    "opening_family": opening_family(opening),
                    "y_cp_raw": cp_raw,
                    "y_cp_clip": cp_clip,
                    "y_tanh": math.tanh(cp_clip / 400.0),
                }
            )
            rows.append(feat)

    split_dates(rows)
    if not rows:
        print({"rows": 0})
        return

    cols = list(rows[0].keys())
    by_split = {"train": [], "valid": [], "test": []}
    for r in rows:
        by_split[r["split"]].append(r)

    out_files = {}
    for split, vals in by_split.items():
        path = os.path.join(args.out_dir, f"features_{split}.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for row in vals:
                out = row.copy()
                if isinstance(out.get("game_date"), date):
                    out["game_date"] = out["game_date"].isoformat()
                w.writerow(out)
        out_files[split] = path

    print(
        {
            "rows_total": len(rows),
            "train": len(by_split["train"]),
            "valid": len(by_split["valid"]),
            "test": len(by_split["test"]),
            "files": out_files,
        }
    )


if __name__ == "__main__":
    main()

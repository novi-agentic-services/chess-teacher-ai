# LC0 Feature Schema v1

Task: predict Leela Zero centipawn evaluation per position.

## Target columns

- `y_cp_raw`: raw `move_evaluations.score_cp`
- `y_cp_clip`: `clip(y_cp_raw, -1000, 1000)`
- `y_tanh`: `tanh(y_cp_clip / 400)`

## Metadata

- `game_id`
- `ply_index`
- `fen`
- `game_date`
- `eco`
- `opening_family`

## Core features

- `side_to_move` (1=white, 0=black)
- `phase` (0..1, opening to endgame)
- Material counts and imbalances:
  - `w_pawns`,`w_knights`,`w_bishops`,`w_rooks`,`w_queens`
  - `b_pawns`,`b_knights`,`b_bishops`,`b_rooks`,`b_queens`
  - `imb_pawns`,`imb_knights`,`imb_bishops`,`imb_rooks`,`imb_queens`
  - `bishop_pair_white`,`bishop_pair_black`
- Mobility/control:
  - `legal_moves_total`,`white_mobility`,`black_mobility`
  - `center_control_white`,`center_control_black`
  - `extended_center_control_white`,`extended_center_control_black`
- King safety:
  - `white_in_check`,`black_in_check`
  - `white_king_attackers`,`black_king_attackers`
  - `white_king_ring_attacked`,`black_king_ring_attacked`
- Pawn structure:
  - `white_passed_pawns`,`black_passed_pawns`
  - `white_isolated_pawns`,`black_isolated_pawns`
  - `white_doubled_pawns`,`black_doubled_pawns`
  - `white_pawn_islands`,`black_pawn_islands`
- Piece/tactical proxies:
  - `white_hanging_pieces`,`black_hanging_pieces`
  - `white_rooks_open_files`,`black_rooks_open_files`
  - `white_rooks_semiopen_files`,`black_rooks_semiopen_files`
  - `white_knight_outposts`,`black_knight_outposts`
  - `best_capture_gain_white`,`best_capture_gain_black`

## Splits

Time-ordered split by `game_date`:

- Train: oldest 80%
- Valid: next 10%
- Test: newest 10%

Rows with null `game_date` are placed in train by default.

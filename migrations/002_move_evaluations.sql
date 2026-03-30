CREATE TABLE IF NOT EXISTS move_evaluations (
  id BIGSERIAL PRIMARY KEY,
  game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  ply_index INTEGER NOT NULL,
  fen TEXT NOT NULL,
  move_uci TEXT,
  engine_name TEXT NOT NULL DEFAULT 'lc0',
  depth INTEGER,
  score_cp INTEGER,
  score_mate INTEGER,
  pv TEXT,
  analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(game_id, ply_index, engine_name)
);

CREATE INDEX IF NOT EXISTS idx_move_evals_game_engine ON move_evaluations(game_id, engine_name, ply_index);

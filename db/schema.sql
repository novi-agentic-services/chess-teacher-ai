CREATE TABLE IF NOT EXISTS twic_sources (
  id BIGSERIAL PRIMARY KEY,
  twic_issue_number INTEGER UNIQUE NOT NULL,
  source_url TEXT NOT NULL,
  downloaded_at TIMESTAMPTZ,
  checksum TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS games (
  id UUID PRIMARY KEY,
  game_hash TEXT UNIQUE NOT NULL,
  event TEXT,
  site TEXT,
  round TEXT,
  game_date DATE,
  white_player TEXT,
  black_player TEXT,
  white_elo INTEGER,
  black_elo INTEGER,
  result TEXT,
  eco TEXT,
  opening TEXT,
  variation TEXT,
  pgn_text TEXT NOT NULL,
  twic_source_id BIGINT REFERENCES twic_sources(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_games_white_player ON games(white_player);
CREATE INDEX IF NOT EXISTS idx_games_black_player ON games(black_player);
CREATE INDEX IF NOT EXISTS idx_games_game_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_eco ON games(eco);

CREATE TABLE IF NOT EXISTS positions (
  id BIGSERIAL PRIMARY KEY,
  fen TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS game_positions (
  id BIGSERIAL PRIMARY KEY,
  game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  ply_index INTEGER NOT NULL,
  position_id BIGINT NOT NULL REFERENCES positions(id),
  move_san TEXT,
  move_uci TEXT,
  UNIQUE(game_id, ply_index)
);

CREATE INDEX IF NOT EXISTS idx_game_positions_position ON game_positions(position_id, ply_index);

CREATE TABLE IF NOT EXISTS position_move_stats (
  id BIGSERIAL PRIMARY KEY,
  position_id BIGINT NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
  move_uci TEXT NOT NULL,
  games_count INTEGER NOT NULL DEFAULT 0,
  white_wins INTEGER NOT NULL DEFAULT 0,
  draws INTEGER NOT NULL DEFAULT 0,
  black_wins INTEGER NOT NULL DEFAULT 0,
  white_win_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
  draw_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
  black_win_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(position_id, move_uci)
);

INSERT INTO position_move_stats (
  position_id, move_uci, games_count, white_wins, draws, black_wins,
  white_win_pct, draw_pct, black_win_pct, updated_at
)
SELECT
  gp.position_id,
  gp.move_uci,
  COUNT(*) AS games_count,
  SUM(CASE WHEN g.result = '1-0' THEN 1 ELSE 0 END) AS white_wins,
  SUM(CASE WHEN g.result = '1/2-1/2' THEN 1 ELSE 0 END) AS draws,
  SUM(CASE WHEN g.result = '0-1' THEN 1 ELSE 0 END) AS black_wins,
  ROUND((SUM(CASE WHEN g.result='1-0' THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*),0))*100,2) AS white_win_pct,
  ROUND((SUM(CASE WHEN g.result='1/2-1/2' THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*),0))*100,2) AS draw_pct,
  ROUND((SUM(CASE WHEN g.result='0-1' THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*),0))*100,2) AS black_win_pct,
  NOW()
FROM game_positions gp
JOIN games g ON g.id = gp.game_id
GROUP BY gp.position_id, gp.move_uci
ON CONFLICT (position_id, move_uci)
DO UPDATE SET
  games_count = EXCLUDED.games_count,
  white_wins = EXCLUDED.white_wins,
  draws = EXCLUDED.draws,
  black_wins = EXCLUDED.black_wins,
  white_win_pct = EXCLUDED.white_win_pct,
  draw_pct = EXCLUDED.draw_pct,
  black_win_pct = EXCLUDED.black_win_pct,
  updated_at = NOW();

import React from 'react';
import { createRoot } from 'react-dom/client';
import { Chess } from 'chess.js';
import { Chessboard } from 'react-chessboard';
import './styles.css';

type GameSummary = {
  id: string;
  event?: string;
  date?: string;
  white?: string;
  black?: string;
  result?: string;
};

type TreeMove = {
  move_uci: string;
  games: number;
  white_win_pct: number;
  draw_pct: number;
  black_win_pct: number;
};

type PlayerProfile = {
  player_query: string;
  info: { total_games: number; first_game?: string | null; last_game?: string | null; distinct_opponents: number };
  scores: { white: { wins: number; draws: number; losses: number }; black: { wins: number; draws: number; losses: number } };
  common_openings: { opening: string; games: number }[];
  rating_chart: { month: string; avg_elo: number; samples: number }[];
};

const API_BASE = 'http://127.0.0.1:8000';

function App() {
  const [query, setQuery] = React.useState('Roberto de Abreu');
  const [games, setGames] = React.useState<GameSummary[]>([]);
  const [selected, setSelected] = React.useState<any>(null);
  const [chess, setChess] = React.useState(new Chess());
  const [moves, setMoves] = React.useState<string[]>([]);
  const [idx, setIdx] = React.useState(0);
  const [tree, setTree] = React.useState<TreeMove[]>([]);
  const [searching, setSearching] = React.useState(false);
  const [profile, setProfile] = React.useState<PlayerProfile | null>(null);
  const [loadingProfile, setLoadingProfile] = React.useState(false);

  const searchGames = async (q: string) => {
    setSearching(true);
    try {
      const res = await fetch(`${API_BASE}/api/games/search?q=${encodeURIComponent(q)}&limit=50`);
      const data = await res.json();
      setGames(data.items || []);
    } finally {
      setSearching(false);
    }
  };

  const loadGame = async (id: string) => {
    const res = await fetch(`${API_BASE}/api/games/${id}`);
    const data = await res.json();
    if (!data.found) return;
    setSelected(data.item);
    const c = new Chess();
    c.loadPgn(data.item.pgn || '');
    const hist = c.history({ verbose: false });
    const fresh = new Chess();
    setChess(fresh);
    setMoves(hist);
    setIdx(0);
  };

  const applyTo = (target: number) => {
    const c = new Chess();
    for (let i = 0; i < target; i++) c.move(moves[i]);
    setChess(c);
    setIdx(target);
  };

  const playToEnd = () => {
    applyTo(moves.length);
  };

  const slowPlayToEnd = async () => {
    for (let t = idx + 1; t <= moves.length; t++) {
      applyTo(t);
      // 5 moves every 2s => 400ms per move
      // eslint-disable-next-line no-await-in-loop
      await new Promise((r) => setTimeout(r, 400));
    }
  };

  const applyTreeMove = (uci: string) => {
    const c = new Chess(chess.fen());
    const mv = c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci.length > 4 ? (uci[4] as any) : undefined });
    if (mv) setChess(c);
  };

  const loadProfile = async () => {
    setLoadingProfile(true);
    try {
      const res = await fetch(`${API_BASE}/api/players/profile?name=${encodeURIComponent(query)}`);
      const data = await res.json();
      setProfile(data);
    } finally {
      setLoadingProfile(false);
    }
  };

  React.useEffect(() => {
    searchGames(query).catch(console.error);
  }, []);

  React.useEffect(() => {
    const fen = chess.fen();
    fetch(`${API_BASE}/api/positions/tree?fen=${encodeURIComponent(fen)}&limit=20`)
      .then((r) => r.json())
      .then((d) => setTree(d.moves || []))
      .catch(() => setTree([]));
  }, [chess]);

  return (
    <div className="app">
      <aside className="panel">
        <h3>Game Search</h3>
        <div className="search-row">
          <input data-testid="player-search" value={query} onChange={(e) => setQuery(e.target.value)} />
          <button data-testid="search-btn" onClick={() => searchGames(query)} disabled={searching}>{searching ? 'Searching…' : 'Search'}</button>
          <button data-testid="profile-btn" onClick={loadProfile} disabled={loadingProfile}>{loadingProfile ? 'Loading…' : 'Profile'}</button>
        </div>
        <div style={{ marginTop: 12 }}>
          {games.map((g) => (
            <div key={g.id} className="game-card">
              <div className="game-title">{g.white} vs {g.black}</div>
              <div className="game-meta">{g.event} • {g.date} • {g.result}</div>
              <button data-testid={`load-${g.id}`} onClick={() => loadGame(g.id)}>Load</button>
            </div>
          ))}
          {!games.length && <div className="empty">No games loaded yet.</div>}
        </div>
      </aside>

      <main className="panel">
        <h2>Board + Notation</h2>
        <div className="board-wrap">
          <Chessboard id="main-board" position={chess.fen()} arePiecesDraggable={false} />
        </div>
        <div className="controls">
          <button data-testid="prev-move" onClick={() => applyTo(Math.max(0, idx - 1))}>Prev</button>
          <button data-testid="next-move" onClick={() => applyTo(Math.min(moves.length, idx + 1))}>Next</button>
          <button data-testid="play-to-end" onClick={playToEnd}>Play to End</button>
          <button data-testid="slow-play" onClick={slowPlayToEnd}>Slow Play (5/2s)</button>
          <span data-testid="move-progress" className="progress">Move {idx}/{moves.length}</span>
        </div>
        {selected && <p data-testid="loaded-game-id" className="loaded">Loaded: {selected.id}</p>}
      </main>

      <aside className="panel">
        <h3>Opening Tree</h3>
        {tree.map((m) => (
          <div key={m.move_uci} className="tree-row" onClick={() => applyTreeMove(m.move_uci)} title="Click to play this move">
            <div className="tree-top">
              <span><b>{m.move_uci}</b></span>
              <span>{m.games} games</span>
            </div>
            <div style={{ fontSize: 12, color: '#a9b8e4' }}>W {m.white_win_pct}% / D {m.draw_pct}% / B {m.black_win_pct}%</div>
            <div className="bars">
              <div className="bar w" style={{ width: `${m.white_win_pct}%` }} />
              <div className="bar d" style={{ width: `${m.draw_pct}%` }} />
              <div className="bar b" style={{ width: `${m.black_win_pct}%` }} />
            </div>
          </div>
        ))}
        {!tree.length && <div className="empty">No known continuations from this position.</div>}

        <div style={{ marginTop: 14 }}>
          <h3 style={{ marginBottom: 8 }}>Player Profile</h3>
          {!profile && <div data-testid="profile-empty" className="empty">Load a player profile to view score split, openings, rating trend and player info.</div>}
          {profile && (
            <div data-testid="profile-panel">
              <div data-testid="profile-info" className="game-meta">{profile.player_query} • {profile.info.total_games} games • {profile.info.distinct_opponents} opponents</div>
              <div className="game-meta">First: {profile.info.first_game || '-'} • Last: {profile.info.last_game || '-'}</div>

              <div data-testid="profile-score-white" style={{ marginTop: 8, fontSize: 12 }}>
                <b>White</b> W {profile.scores.white.wins} / D {profile.scores.white.draws} / L {profile.scores.white.losses}
              </div>
              <div data-testid="profile-score-black" style={{ fontSize: 12, marginBottom: 8 }}>
                <b>Black</b> W {profile.scores.black.wins} / D {profile.scores.black.draws} / L {profile.scores.black.losses}
              </div>

              <div data-testid="profile-openings" style={{ marginTop: 8 }}>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Most Common Openings</div>
                {profile.common_openings.slice(0, 8).map((o) => (
                  <div key={o.opening} style={{ fontSize: 12, borderBottom: '1px solid #2a3a66', padding: '4px 0' }}>
                    {o.opening} • {o.games}
                  </div>
                ))}
              </div>

              <div data-testid="profile-rating-chart" style={{ marginTop: 10 }}>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Rating Chart (avg by month)</div>
                <div style={{ maxHeight: 120, overflow: 'auto' }}>
                  {profile.rating_chart.slice(-24).map((r) => (
                    <div key={r.month} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 48px', gap: 6, alignItems: 'center', marginBottom: 3 }}>
                      <div style={{ fontSize: 11, color: '#a9b8e4' }}>{r.month.slice(0, 7)}</div>
                      <div style={{ height: 6, background: '#2a3a66', borderRadius: 999 }}>
                        <div style={{ height: '100%', width: `${Math.max(5, Math.min(100, (r.avg_elo - 2000) / 8))}%`, background: '#5da8ff', borderRadius: 999 }} />
                      </div>
                      <div style={{ fontSize: 11 }}>{r.avg_elo}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);

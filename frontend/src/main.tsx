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
      </aside>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);

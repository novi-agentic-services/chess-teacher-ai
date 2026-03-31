import React from 'react';
import { createRoot } from 'react-dom/client';
import { Chess } from 'chess.js';
import { Chessboard } from 'react-chessboard';

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

  const searchGames = async (q: string) => {
    const res = await fetch(`${API_BASE}/api/games/search?q=${encodeURIComponent(q)}&limit=50`);
    const data = await res.json();
    setGames(data.items || []);
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
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr 360px', gap: 12, height: '100vh', padding: 12, fontFamily: 'Arial' }}>
      <aside style={{ border: '1px solid #ccc', borderRadius: 8, padding: 10, overflow: 'auto' }}>
        <h3>Game Search</h3>
        <input data-testid="player-search" value={query} onChange={(e) => setQuery(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
        <button data-testid="search-btn" onClick={() => searchGames(query)}>Search</button>
        <div style={{ marginTop: 12 }}>
          {games.map((g) => (
            <div key={g.id} style={{ border: '1px solid #eee', marginBottom: 6, padding: 6, borderRadius: 6 }}>
              <div style={{ fontWeight: 700 }}>{g.white} vs {g.black}</div>
              <div style={{ fontSize: 12 }}>{g.event} • {g.date} • {g.result}</div>
              <button data-testid={`load-${g.id}`} onClick={() => loadGame(g.id)}>Load</button>
            </div>
          ))}
        </div>
      </aside>

      <main style={{ border: '1px solid #ccc', borderRadius: 8, padding: 10, overflow: 'auto' }}>
        <h2>Board + Notation</h2>
        <div style={{ maxWidth: 560 }}>
          <Chessboard id="main-board" position={chess.fen()} arePiecesDraggable={false} />
        </div>
        <div style={{ marginTop: 8 }}>
          <button data-testid="prev-move" onClick={() => applyTo(Math.max(0, idx - 1))}>Prev</button>
          <button data-testid="next-move" onClick={() => applyTo(Math.min(moves.length, idx + 1))} style={{ marginLeft: 6 }}>Next</button>
          <button data-testid="play-to-end" onClick={playToEnd} style={{ marginLeft: 6 }}>Play to End</button>
          <span data-testid="move-progress" style={{ marginLeft: 10 }}>Move {idx}/{moves.length}</span>
        </div>
        {selected && <p data-testid="loaded-game-id">Loaded: {selected.id}</p>}
      </main>

      <aside style={{ border: '1px solid #ccc', borderRadius: 8, padding: 10, overflow: 'auto' }}>
        <h3>Opening Tree</h3>
        {tree.map((m) => (
          <div key={m.move_uci} style={{ borderBottom: '1px solid #eee', padding: '6px 0' }}>
            <div><b>{m.move_uci}</b> • {m.games} games</div>
            <div style={{ fontSize: 12 }}>W {m.white_win_pct}% / D {m.draw_pct}% / B {m.black_win_pct}%</div>
          </div>
        ))}
      </aside>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);

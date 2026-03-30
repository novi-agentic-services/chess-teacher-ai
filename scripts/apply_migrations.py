#!/usr/bin/env python3
import os
from pathlib import Path
import psycopg

BASE = Path(__file__).resolve().parents[1]
MIG_DIR = BASE / 'migrations'

url = os.getenv('DATABASE_URL', 'postgresql://app:app@localhost:5432/chess_teacher_ai')
url = url.replace('postgresql+psycopg', 'postgresql')

with psycopg.connect(url) as conn, conn.cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    for path in sorted(MIG_DIR.glob('*.sql')):
        version = path.name
        cur.execute('SELECT 1 FROM schema_migrations WHERE version=%s', (version,))
        if cur.fetchone():
            continue
        sql = path.read_text()
        cur.execute(sql)
        cur.execute('INSERT INTO schema_migrations(version) VALUES (%s)', (version,))
        conn.commit()
        print(f'applied {version}')

print('migrations complete')

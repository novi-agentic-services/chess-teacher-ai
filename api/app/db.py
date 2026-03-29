import os
import psycopg
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/chess_teacher_ai")
DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg", "postgresql")

@contextmanager
def get_conn():
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

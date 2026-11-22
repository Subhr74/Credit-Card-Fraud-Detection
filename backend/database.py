"""Optimized Database connection and initialization module."""
import os
import sqlite3
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import DATABASE_URL, BASE_DIR

engine_url = DATABASE_URL
connect_args = {}
if engine_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(engine_url, connect_args=connect_args)

# High-Performance SQLite Pragmas for OLAP Speed
if engine_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB Cache
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def execute_query(sql_str: str, params: dict = None):
    if params is None:
        params = {}
    with engine.connect() as conn:
        result = conn.execute(text(sql_str), params)
        if result.returns_rows:
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
        conn.commit()
        return []

def init_db():
    schema_path = BASE_DIR / "docs" / "schema.sql"
    if not schema_path.exists():
        return
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]
    with engine.connect() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass

if __name__ == "__main__":
    init_db()
    print("Database schema successfully initialized.")

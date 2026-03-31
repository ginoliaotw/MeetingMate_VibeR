"""Database models and session management using SQLAlchemy + SQLite."""

import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from config import DB_PATH

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), default="Untitled Meeting")
    date = Column(String(50), default="")
    participants = Column(Text, default="")  # comma-separated
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Audio
    audio_filename = Column(String(500), default="")
    audio_path = Column(String(1000), default="")
    audio_duration_sec = Column(Float, default=0.0)
    audio_format = Column(String(20), default="")

    # Transcript
    transcript_text = Column(Text, default="")
    transcript_language = Column(String(20), default="")
    transcript_path = Column(String(1000), default="")
    transcript_speakers = Column(Text, default="")  # JSON list of speaker labels

    # Summary
    summary_brief = Column(Text, default="")       # <=200 chars overview
    summary_detailed = Column(Text, default="")     # full detailed summary
    summary_action_items = Column(Text, default="") # action items / todos
    summary_llm_provider = Column(String(50), default="")
    summary_path = Column(String(1000), default="")

    # Status
    status = Column(String(50), default="uploaded")  # uploaded|transcribing|transcribed|summarizing|completed|error
    error_message = Column(Text, default="")

    # External summary (pasted from external LLM)
    external_summary = Column(Text, default="")
    external_summary_path = Column(String(1000), default="")

    # Google Drive
    gdrive_audio_id = Column(String(200), default="")
    gdrive_transcript_id = Column(String(200), default="")
    gdrive_summary_id = Column(String(200), default="")
    gdrive_external_summary_id = Column(String(200), default="")
    gdrive_synced = Column(Boolean, default=False)


def _migrate_add_columns():
    """Add new columns to existing DB if they're missing (simple migration)."""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(meetings)")
    existing = {row[1] for row in cursor.fetchall()}

    new_columns = {
        "external_summary": "TEXT DEFAULT ''",
        "external_summary_path": "VARCHAR(1000) DEFAULT ''",
        "gdrive_external_summary_id": "VARCHAR(200) DEFAULT ''",
        "transcript_speakers": "TEXT DEFAULT ''",
    }
    for col, typedef in new_columns.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE meetings ADD COLUMN {col} {typedef}")
    conn.commit()
    conn.close()


def init_db():
    """Create all tables and run lightweight migration."""
    Base.metadata.create_all(bind=engine)
    try:
        _migrate_add_columns()
    except Exception:
        pass  # table might not exist yet on first run


def get_db() -> Session:
    """Dependency for FastAPI — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

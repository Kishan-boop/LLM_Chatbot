"""
Database models and session management for chatbot service.
Uses SQLAlchemy ORM with SQLite backend.
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Text, CheckConstraint, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from config import settings

Base = declarative_base()


class Conversation(Base):
    """Conversation metadata table."""
    __tablename__ = 'conversations'

    id = Column(String, primary_key=True)
    created_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat())
    user_id = Column(String, nullable=True)
    context_window_size = Column(Integer, nullable=False, default=10)
    model_name = Column(String, nullable=False, default='llama-3.1-70b-versatile')

    __table_args__ = (
        Index('idx_conversations_created_at', 'created_at'),
    )


class Message(Base):
    """Chat message table."""
    __tablename__ = 'messages'

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat())
    token_count = Column(Integer, default=0)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name='check_role'),
        Index('idx_messages_conversation_time', 'conversation_id', 'created_at'),
    )


class InferenceLog(Base):
    """LLM inference metadata - stored locally for reference."""
    __tablename__ = 'inference_logs'

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    message_id = Column(String, ForeignKey('messages.id', ondelete='SET NULL'), nullable=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    request_timestamp = Column(String, nullable=False)
    response_timestamp = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    status = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)
    input_preview = Column(Text, nullable=True)
    output_preview = Column(Text, nullable=True)
    created_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat())

    __table_args__ = (
        CheckConstraint("status IN ('success', 'error', 'timeout')", name='check_status'),
        Index('idx_inference_logs_conversation', 'conversation_id'),
        Index('idx_inference_logs_time_status', 'created_at', 'status'),
        Index('idx_inference_logs_provider_model', 'provider', 'model'),
    )


# Create database engine
engine = create_engine(
    f'sqlite:///{settings.database_path}',
    connect_args={'check_same_thread': False},
    echo=False
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_database():
    """Initialize database schema."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Session:
    """Database session context manager."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

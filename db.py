# db.py
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///emotional_diary.db')

# Handle different database URLs
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    # SQLite specific settings
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    """User model for storing user information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(50), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    timezone = Column(String(50), default='Europe/Moscow')
    language = Column(String(10), default='ru')
    paused = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    entries = relationship("Entry", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", cascade="all, delete-orphan", uselist=False)
    
    def __repr__(self):
        return f"<User(chat_id={self.chat_id}, username={self.username})>"

class Entry(Base):
    """Entry model for storing emotional diary entries"""
    __tablename__ = "entries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Core emotion data
    emotions = Column(JSON, nullable=False)  # List of emotions as JSON
    category = Column(String(100), nullable=True)  # Emotion category
    valence = Column(Float, nullable=False)  # -1 to 1 (negative to positive)
    arousal = Column(Float, nullable=False)  # 0 to 2 (low to high energy)
    
    # Context and details
    cause = Column(Text, nullable=True)  # What triggered the emotion
    body_sensations = Column(Text, nullable=True)  # Physical sensations
    notes = Column(Text, nullable=True)  # Additional notes
    tags = Column(JSON, nullable=True)  # List of tags as JSON
    
    # Metadata
    source = Column(String(20), default='manual')  # manual, scheduled, etc.
    location = Column(String(100), nullable=True)  # Optional location context
    
    # Relationships
    user = relationship("User", back_populates="entries")
    
    def __repr__(self):
        return f"<Entry(user_id={self.user_id}, emotions={self.emotions}, timestamp={self.timestamp})>"

class Schedule(Base):
    """Schedule model for storing user-specific notification schedules"""
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date_local = Column(String(10), nullable=False)  # YYYY-MM-DD in user timezone
    times_local = Column(JSON, nullable=False)  # List of times as JSON ["09:00", "13:00", "17:00", "21:00"]

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
    completed_times = Column(JSON, default=lambda: [])  # Completed notification times
    skipped = Column(Boolean, default=False)  # If user skipped the entire day
    
    # Relationships
    user = relationship("User", back_populates="schedules")
    
    def __repr__(self):
        return f"<Schedule(user_id={self.user_id}, date={self.date_local})>"

class UserSettings(Base):
    """User settings model for customization preferences"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Notification settings
    notification_frequency = Column(String(20), default='normal')  # normal, reduced, minimal
    weekend_notifications = Column(Boolean, default=True)
    daily_ping_times = Column(JSON, default=lambda: ["09:00", "13:00", "17:00", "21:00"])
    
    # Summary settings
    weekly_summary_time = Column(String(5), default='21:00')  # HH:MM
    weekly_summary_day = Column(Integer, default=6)  # 0=Monday, 6=Sunday
    
    # Personal preferences
    preferred_categories = Column(JSON, nullable=True)  # User's frequently used categories
    custom_emotions = Column(JSON, nullable=True)  # User's custom emotion words
    
    # Privacy settings
    data_retention_days = Column(Integer, default=365)  # How long to keep data
    
    # Relationships
    user = relationship("User", back_populates="settings")
    
    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, frequency={self.notification_frequency})>"

# Database session management
@contextmanager
def get_session() -> Session:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()

async def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def get_user_by_chat_id(chat_id: int) -> User:
    """Get user by chat ID"""
    with get_session() as session:
        return session.query(User).filter(User.chat_id == chat_id).first()

def create_user(chat_id: int, username: str = None, first_name: str = None, 
               last_name: str = None, timezone: str = 'Europe/Moscow') -> User:
    """Create a new user"""
    with get_session() as session:
        user = User(
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            timezone=timezone
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Create default settings
        settings = UserSettings(user_id=user.id)
        session.add(settings)
        session.commit()
        
        return user

def update_user_activity(chat_id: int):
    """Update user's last activity timestamp"""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.last_activity = datetime.now(timezone.utc)
            session.commit()

def get_active_users(days: int = 30) -> list:
    """Get users active within specified days"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    with get_session() as session:
        return session.query(User).filter(
            User.last_activity >= cutoff_date,
            User.paused == False
        ).all()

def cleanup_old_data():
    """Clean up old data based on user retention settings"""
    with get_session() as session:
        users_with_settings = session.query(User).join(UserSettings).all()
        
        for user in users_with_settings:
            if user.settings and user.settings.data_retention_days:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=user.settings.data_retention_days)
                
                # Delete old entries
                old_entries = session.query(Entry).filter(
                    Entry.user_id == user.id,
                    Entry.timestamp < cutoff_date
                ).delete()
                
                # Delete old schedules
                old_schedules = session.query(Schedule).filter(
                    Schedule.user_id == user.id,
                    Schedule.date_local < cutoff_date.strftime('%Y-%m-%d')
                ).delete()
                
                if old_entries > 0 or old_schedules > 0:
                    logger.info(f"Cleaned up {old_entries} entries and {old_schedules} schedules for user {user.chat_id}")
        
        session.commit()

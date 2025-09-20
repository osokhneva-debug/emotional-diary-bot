# scheduler.py
import asyncio
import logging
from datetime import datetime, timedelta, timezone  # ИСПРАВЛЕНО: добавлен timedelta
from typing import List, Callable
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from db import get_session, User, Schedule, UserSettings, get_active_users
from i18n import TEXTS

logger = logging.getLogger(__name__)

class EmotionScheduler:
    """Handles all scheduled tasks for the emotion diary bot"""
    
    def __init__(self):
        # Configure scheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz.UTC
        )
        
        # Callbacks to be set by main bot
        self.send_daily_ping_callback: Callable = None
        self.send_weekly_summary_callback: Callable = None
        
    async def start(self):
        """Start the scheduler"""
        try:
            self.scheduler.start()
            
            # Schedule daily tasks
            await self.schedule_daily_pings()
            await self.schedule_weekly_summaries()
            await self.schedule_maintenance_tasks()
            
            logger.info("Emotion scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    async def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Emotion scheduler stopped")
    
    def set_callbacks(self, daily_ping_callback: Callable, weekly_summary_callback: Callable):
        """Set callback functions for sending notifications"""
        self.send_daily_ping_callback = daily_ping_callback
        self.send_weekly_summary_callback = weekly_summary_callback
    
    async def schedule_daily_pings(self):
        """Schedule daily emotion check-ins for all active users"""
        try:
            active_users = get_active_users(days=7)  # Users active in last 7 days
            
            for user in active_users:
                if user.paused:
                    continue
                    
                await self.schedule_user_daily_pings(user)
                
            logger.info(f"Scheduled daily pings for {len(active_users)} active users")
            
        except Exception as e:
            logger.error(f"Error scheduling daily pings: {e}")
    
    async def schedule_user_daily_pings(self, user: User):
        """Schedule daily pings for a specific user"""
        try:
            user_tz = pytz.timezone(user.timezone)
            
            # Get user settings or use defaults
            with get_session() as session:
                settings = session.query(UserSettings).filter(UserSettings.user_id == user.id).first()
                if not settings:
                    ping_times = ["09:00", "13:00", "17:00", "21:00"]
                    weekend_notifications = True
                else:
                    ping_times = settings.daily_ping_times
                    weekend_notifications = settings.weekend_notifications
            
            # Schedule pings for each time
            for ping_time in ping_times:
                hour, minute = map(int, ping_time.split(':'))
                
                # Create cron trigger
                if weekend_notifications:
                    # All days
                    trigger = CronTrigger(
                        hour=hour,
                        minute=minute,
                        timezone=user_tz
                    )
                else:
                    # Weekdays only (Monday=0, Sunday=6)
                    trigger = CronTrigger(
                        hour=hour,
                        minute=minute,
                        day_of_week='0-4',  # Monday to Friday
                        timezone=user_tz
                    )
                
                job_id = f"daily_ping_{user.chat_id}_{ping_time}"
                
                # Remove existing job if it exists
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                
                # Add new job
                self.scheduler.add_job(
                    self.send_daily_ping_to_user,
                    trigger=trigger,
                    args=[user.chat_id],
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=300  # 5 minutes grace period
                )
                
        except Exception as e:
            logger.error(f"Error scheduling daily pings for user {user.chat_id}: {e}")
    
    async def schedule_weekly_summaries(self):
        """Schedule weekly summaries for all active users"""
        try:
            active_users = get_active_users(days=14)  # Users active in last 2 weeks
            
            for user in active_users:
                if user.paused:
                    continue
                    
                await self.schedule_user_weekly_summary(user)
                
            logger.info(f"Scheduled weekly summaries for {len(active_users)} active users")
            
        except Exception as e:
            logger.error(f"Error scheduling weekly summaries: {e}")
    
    async def schedule_user_weekly_summary(self, user: User):
        """Schedule weekly summary for a specific user"""
        try:
            user_tz = pytz.timezone(user.timezone)
            
            # Get user settings or use defaults
            with get_session() as session:
                settings = session.query(UserSettings).filter(UserSettings.user_id == user.id).first()
                if not settings:
                    summary_time = "21:00"
                    summary_day = 6  # Sunday
                else:
                    summary_time = settings.weekly_summary_time
                    summary_day = settings.weekly_summary_day
            
            hour, minute = map(int, summary_time.split(':'))
            
            # Create cron trigger for weekly summary
            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=summary_day,
                timezone=user_tz
            )
            
            job_id = f"weekly_summary_{user.chat_id}"
            
            # Remove existing job if it exists
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # Add new job
            self.scheduler.add_job(
                self.send_weekly_summary_to_user,
                trigger=trigger,
                args=[user.chat_id],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=3600  # 1 hour grace period
            )
            
        except Exception as e:
            logger.error(f"Error scheduling weekly summary for user {user.chat_id}: {e}")
    
    async def schedule_maintenance_tasks(self):
        """Schedule maintenance tasks"""
        # Daily cleanup at 2 AM UTC
        self.scheduler.add_job(
            self.cleanup_old_data,
            CronTrigger(hour=2, minute=0, timezone=pytz.UTC),
            id="daily_cleanup",
            replace_existing=True
        )
        
        # Weekly user reactivation check on Mondays at 1 AM UTC
        self.scheduler.add_job(
            self.reschedule_all_users,
            CronTrigger(hour=1, minute=0, day_of_week=0, timezone=pytz.UTC),
            id="weekly_reschedule",
            replace_existing=True
        )
        
        logger.info("Scheduled maintenance tasks")
    
    async def send_daily_ping_to_user(self, chat_id: int):
        """Send daily ping to specific user"""
        try:
            if self.send_daily_ping_callback:
                await self.send_daily_ping_callback(chat_id)
            else:
                logger.warning("Daily ping callback not set")
                
        except Exception as e:
            logger.error(f"Error sending daily ping to {chat_id}: {e}")
    
    async def send_weekly_summary_to_user(self, chat_id: int):
        """Send weekly summary to specific user"""
        try:
            if self.send_weekly_summary_callback:
                await self.send_weekly_summary_callback(chat_id)
            else:
                logger.warning("Weekly summary callback not set")
                
        except Exception as e:
            logger.error(f"Error sending weekly summary to {chat_id}: {e}")
    
    async def reschedule_user(self, user: User):
        """Reschedule notifications for a specific user"""
        try:
            # Remove existing jobs
            jobs_to_remove = []
            for job in self.scheduler.get_jobs():
                if f"_{user.chat_id}" in job.id:
                    jobs_to_remove.append(job.id)
            
            for job_id in jobs_to_remove:
                self.scheduler.remove_job(job_id)
            
            # Reschedule if user is not paused
            if not user.paused:
                await self.schedule_user_daily_pings(user)
                await self.schedule_user_weekly_summary(user)
                
            logger.info(f"Rescheduled notifications for user {user.chat_id}")
            
        except Exception as e:
            logger.error(f"Error rescheduling user {user.chat_id}: {e}")
    
    async def reschedule_all_users(self):
        """Reschedule notifications for all active users"""
        try:
            active_users = get_active_users(days=30)
            
            for user in active_users:
                await self.reschedule_user(user)
                
            logger.info(f"Rescheduled notifications for {len(active_users)} users")
            
        except Exception as e:
            logger.error(f"Error rescheduling all users: {e}")
    
    async def cleanup_old_data(self):
        """Clean up old data and schedules"""
        try:
            from db import cleanup_old_data
            cleanup_old_data()
            logger.info("Completed daily data cleanup")
            
        except Exception as e:
            logger.error(f"Error during data cleanup: {e}")
    
    async def postpone_user_ping(self, chat_id: int, minutes: int = 15):
        """Postpone next ping for a user by specified minutes"""
        try:
            postpone_time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            
            job_id = f"postponed_ping_{chat_id}_{postpone_time.timestamp()}"
            
            self.scheduler.add_job(
                self.send_daily_ping_to_user,
                DateTrigger(run_date=postpone_time),
                args=[chat_id],
                id=job_id,
                replace_existing=True
            )
            
            logger.info(f"Postponed ping for user {chat_id} by {minutes} minutes")
            
        except Exception as e:
            logger.error(f"Error postponing ping for user {chat_id}: {e}")
    
    async def skip_user_day(self, chat_id: int):
        """Skip all remaining pings for a user today"""
        try:
            # Mark today as skipped in the database
            with get_session() as session:
                user = session.query(User).filter(User.chat_id == chat_id).first()
                if user:
                    user_tz = pytz.timezone(user.timezone)
                    today = datetime.now(user_tz).strftime('%Y-%m-%d')
                    
                    # Find or create today's schedule
                    schedule = session.query(Schedule).filter(
                        Schedule.user_id == user.id,
                        Schedule.date_local == today
                    ).first()
                    
                    if not schedule:
                        schedule = Schedule(
                            user_id=user.id,
                            date_local=today,
                            times_local=["09:00", "13:00", "17:00", "21:00"]
                        )
                        session.add(schedule)
                    
                    schedule.skipped = True
                    session.commit()
                    
                    logger.info(f"Marked day as skipped for user {chat_id}")
                    
        except Exception as e:
            logger.error(f"Error skipping day for user {chat_id}: {e}")
    
    def get_scheduler_status(self) -> dict:
        """Get current scheduler status"""
        return {
            'running': self.scheduler.running,
            'total_jobs': len(self.scheduler.get_jobs()),
            'job_details': [
                {
                    'id': job.id,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                }
                for job in self.scheduler.get_jobs()[:10]  # Show first 10 jobs
            ]
        }

# rate_limiter.py
import functools
import logging
from typing import Callable, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter to prevent spam and abuse"""
    
    def __init__(self):
        # Store request timestamps for each user
        self.user_requests = defaultdict(lambda: deque())
        
        # Rate limits (requests per time window)
        self.limits = {
            'emotion_entry': {'count': 50, 'window': 3600},    # 50 entries per hour
            'summary_request': {'count': 20, 'window': 3600},   # 20 summaries per hour
            'export_request': {'count': 5, 'window': 3600},     # 5 exports per hour
            'general_command': {'count': 100, 'window': 3600},  # 100 commands per hour
            'message': {'count': 200, 'window': 3600}           # 200 messages per hour
        }
    
    def is_allowed(self, user_id: int, action_type: str = 'general_command') -> bool:
        """
        Check if user is allowed to perform action
        
        Args:
            user_id: User identifier
            action_type: Type of action to check
            
        Returns:
            True if allowed, False if rate limited
        """
        try:
            if action_type not in self.limits:
                action_type = 'general_command'
            
            limit_config = self.limits[action_type]
            max_requests = limit_config['count']
            time_window = limit_config['window']
            
            now = datetime.now()
            user_key = f"{user_id}_{action_type}"
            
            # Clean old requests outside the time window
            cutoff_time = now - timedelta(seconds=time_window)
            requests_queue = self.user_requests[user_key]
            
            while requests_queue and requests_queue[0] < cutoff_time:
                requests_queue.popleft()
            
            # Check if under limit
            if len(requests_queue) >= max_requests:
                return False
            
            # Add current request
            requests_queue.append(now)
            return True
            
        except Exception as e:
            logger.error(f"Error in rate limiter: {e}")
            return True  # Allow on error to avoid blocking legitimate users
    
    def get_remaining_quota(self, user_id: int, action_type: str = 'general_command') -> int:
        """
        Get remaining quota for user action
        
        Args:
            user_id: User identifier
            action_type: Type of action to check
            
        Returns:
            Number of remaining requests
        """
        try:
            if action_type not in self.limits:
                action_type = 'general_command'
            
            limit_config = self.limits[action_type]
            max_requests = limit_config['count']
            time_window = limit_config['window']
            
            now = datetime.now()
            user_key = f"{user_id}_{action_type}"
            
            # Clean old requests
            cutoff_time = now - timedelta(seconds=time_window)
            requests_queue = self.user_requests[user_key]
            
            while requests_queue and requests_queue[0] < cutoff_time:
                requests_queue.popleft()
            
            return max(0, max_requests - len(requests_queue))
            
        except Exception as e:
            logger.error(f"Error getting remaining quota: {e}")
            return 0
    
    def reset_user_limits(self, user_id: int):
        """Reset all rate limits for a user"""
        try:
            keys_to_remove = [key for key in self.user_requests.keys() if key.startswith(f"{user_id}_")]
            for key in keys_to_remove:
                del self.user_requests[key]
        except Exception as e:
            logger.error(f"Error resetting user limits: {e}")

# Global rate limiter instance
global_rate_limiter = RateLimiter()

def rate_limit(func: Callable = None, *, action_type: str = 'general_command', error_message: Optional[str] = None):
    """
    Decorator for rate limiting telegram bot handlers
    
    Args:
        action_type: Type of action for rate limiting
        error_message: Custom error message to send when rate limited
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                # Get user ID safely
                user_id = update.effective_user.id if update.effective_user else 0
                
                # Check rate limit
                if not global_rate_limiter.is_allowed(user_id, action_type):
                    # Log rate limit event
                    logger.warning(f"Rate limit exceeded - User: {user_id}, Action: {action_type}")
                    
                    # Send error message
                    message = error_message or "Слишком много запросов. Попробуйте через некоторое время."
                    
                    if update.message:
                        await update.message.reply_text(message)
                    elif update.callback_query:
                        await update.callback_query.answer(message, show_alert=True)
                    
                    return
                
                # Execute original function
                return await func(update, context, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in rate limiter wrapper: {e}")
                # Execute original function even if rate limiter fails
                return await func(update, context, *args, **kwargs)
        
        return wrapper
    
    # Handle both @rate_limit and @rate_limit() syntax
    if func is None:
        return decorator
    else:
        return decorator(func)

# Specific decorators for different action types
def rate_limit_emotion_entry(func: Callable):
    """Rate limit for emotion entry actions"""
    return rate_limit(func, action_type='emotion_entry', error_message="Слишком много записей эмоций. Попробуйте через некоторое время.")

def rate_limit_summary(func: Callable):
    """Rate limit for summary requests"""
    return rate_limit(func, action_type='summary_request', error_message="Слишком много запросов сводок. Подождите немного.")

def rate_limit_export(func: Callable):
    """Rate limit for export requests"""
    return rate_limit(func, action_type='export_request', error_message="Лимит экспорта превышен. Попробуйте позже.")

def rate_limit_message(func: Callable):
    """Rate limit for general messages"""
    return rate_limit(func, action_type='message', error_message="Слишком много сообщений. Сделайте паузу.")

async def check_user_quotas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Command to check current rate limit quotas for user
    """
    user_id = update.effective_user.id
    
    quotas = {}
    for action_type in ['emotion_entry', 'summary_request', 'export_request', 'general_command', 'message']:
        remaining = global_rate_limiter.get_remaining_quota(user_id, action_type)
        quotas[action_type] = remaining
    
    quota_text = "📊 <b>Ваши текущие лимиты:</b>\n\n"
    quota_text += f"📝 Записи эмоций: {quotas['emotion_entry']}/50 в час\n"
    quota_text += f"📈 Сводки: {quotas['summary_request']}/20 в час\n"
    quota_text += f"💾 Экспорт: {quotas['export_request']}/5 в час\n"
    quota_text += f"⌨️ Команды: {quotas['general_command']}/100 в час\n"
    quota_text += f"💬 Сообщения: {quotas['message']}/200 в час\n"
    
    await update.message.reply_text(quota_text, parse_mode='HTML')

def reset_user_rate_limits(user_id: int):
    """Reset rate limits for specific user (admin function)"""
    global_rate_limiter.reset_user_limits(user_id)
    logger.info(f"Rate limits reset for user {user_id}")

class RateLimitMiddleware:
    """Middleware for additional rate limiting checks"""
    
    def __init__(self):
        self.rate_limiter = global_rate_limiter
    
    async def process_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Process update through rate limiting middleware
        
        Returns:
            True if update should be processed, False if rate limited
        """
        try:
            user_id = update.effective_user.id if update.effective_user else 0
            
            # General message rate limiting
            if not self.rate_limiter.is_allowed(user_id, 'message'):
                logger.warning(f"Rate limit exceeded - User: {user_id}, Action: message")
                return False
            
            # Additional checks for specific update types
            if update.message and update.message.text:
                # Basic spam detection
                text = update.message.text.lower()
                
                # Check for excessive repetition
                words = text.split()
                if len(words) > 5:
                    unique_words = set(words)
                    if len(unique_words) / len(words) < 0.3:  # Less than 30% unique words
                        logger.warning(f"Spam detected - User: {user_id}, Content: {text[:50]}")
                        
                        await update.message.reply_text(
                            "Обнаружена подозрительная активность. Пожалуйста, используйте бот по назначению."
                        )
                        return False
                
                # Check for excessive caps
                if len(text) > 10:
                    caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
                    if caps_ratio > 0.7:  # More than 70% caps
                        logger.warning(f"Excessive caps detected - User: {user_id}")
                        
                        await update.message.reply_text(
                            "Пожалуйста, не используйте CAPS LOCK. Общайтесь спокойно."
                        )
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in rate limit middleware: {e}")
            return True  # Allow processing on error
    
    def get_user_stats(self, user_id: int) -> dict:
        """Get rate limiting stats for user"""
        stats = {}
        for action_type in ['emotion_entry', 'summary_request', 'export_request', 'general_command', 'message']:
            remaining = self.rate_limiter.get_remaining_quota(user_id, action_type)
            limit_config = self.rate_limiter.limits[action_type]
            stats[action_type] = {
                'remaining': remaining,
                'limit': limit_config['count'],
                'window': limit_config['window']
            }
        return stats

# Global middleware instance
rate_limit_middleware = RateLimitMiddleware()

# Helper functions for debugging and monitoring
def get_rate_limiter_stats() -> dict:
    """Get overall rate limiter statistics"""
    return {
        'total_users_tracked': len(global_rate_limiter.user_requests),
        'limits_configured': list(global_rate_limiter.limits.keys()),
        'active_users': len([key for key in global_rate_limiter.user_requests.keys() if global_rate_limiter.user_requests[key]])
    }

def cleanup_old_rate_limit_data():
    """Clean up old rate limit data (call periodically)"""
    try:
        now = datetime.now()
        cutoff_time = now - timedelta(hours=2)  # Keep data for 2 hours max
        
        keys_to_clean = []
        for user_key, requests_queue in global_rate_limiter.user_requests.items():
            # Clean old requests
            while requests_queue and requests_queue[0] < cutoff_time:
                requests_queue.popleft()
            
            # If queue is empty, mark for removal
            if not requests_queue:
                keys_to_clean.append(user_key)
        
        # Remove empty queues
        for key in keys_to_clean:
            del global_rate_limiter.user_requests[key]
        
        logger.info(f"Cleaned up rate limit data: removed {len(keys_to_clean)} empty user queues")
        
    except Exception as e:
        logger.error(f"Error cleaning up rate limit data: {e}")

# Export all necessary components
__all__ = [
    'rate_limit',
    'rate_limit_emotion_entry', 
    'rate_limit_summary',
    'rate_limit_export',
    'rate_limit_message',
    'RateLimiter',
    'global_rate_limiter',
    'rate_limit_middleware',
    'check_user_quotas',
    'reset_user_rate_limits',
    'get_rate_limiter_stats',
    'cleanup_old_rate_limit_data'
]

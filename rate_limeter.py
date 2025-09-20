# rate_limiter.py
import functools
import logging
from typing import Callable, Optional
from telegram import Update
from telegram.ext import ContextTypes

from security import RateLimiter, security_logger
from i18n import ERROR_MESSAGES

logger = logging.getLogger(__name__)

# Global rate limiter instance
global_rate_limiter = RateLimiter()

def rate_limit(action_type: str = 'general_command', error_message: Optional[str] = None):
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
                # Get user ID
                user_id = update.effective_user.id if update.effective_user else 0
                
                # Check rate limit
                if not global_rate_limiter.is_allowed(user_id, action_type):
                    # Log rate limit event
                    security_logger.log_rate_limit(user_id, action_type)
                    
                    # Send error message
                    message = error_message or ERROR_MESSAGES.get('rate_limit_exceeded')
                    
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
    return decorator

# Specific decorators for different action types
def rate_limit_emotion_entry(func: Callable):
    """Rate limit for emotion entry actions"""
    return rate_limit('emotion_entry', "Слишком много записей эмоций. Попробуйте через некоторое время.")(func)

def rate_limit_summary(func: Callable):
    """Rate limit for summary requests"""
    return rate_limit('summary_request', "Слишком много запросов сводок. Подождите немного.")(func)

def rate_limit_export(func: Callable):
    """Rate limit for export requests"""
    return rate_limit('export_request', "Лимит экспорта превышен. Попробуйте позже.")(func)

def rate_limit_message(func: Callable):
    """Rate limit for general messages"""
    return rate_limit('message', "Слишком много сообщений. Сделайте паузу.")(func)

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
                security_logger.log_rate_limit(user_id, 'message')
                return False
            
            # Additional checks for specific update types
            if update.message and update.message.text:
                # Check for spam patterns
                from security import detect_spam_patterns
                if detect_spam_patterns(update.message.text):
                    security_logger.log_spam_attempt(user_id, update.message.text)
                    
                    await update.message.reply_text(
                        "Обнаружена подозрительная активность. Пожалуйста, используйте бот по назначению."
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

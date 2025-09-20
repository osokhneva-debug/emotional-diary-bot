# rate_limiter.py
import logging
import functools
from datetime import datetime, timedelta
from collections import defaultdict, deque

logger = logging.getLogger('rate_limiter')

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
        """Check if user is allowed to perform action"""
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

# Global rate limiter instance
global_rate_limiter = RateLimiter()

def rate_limit(action_type: str = 'general_command'):
    """Decorator for rate limiting functions"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # args[0] = self, args[1] = update, args[2] = context
            try:
                if len(args) >= 2:
                    update = args[1]
                    user_id = None
                    
                    # Get user_id from update
                    if hasattr(update, 'effective_user') and update.effective_user:
                        user_id = update.effective_user.id
                    elif hasattr(update, 'message') and update.message and hasattr(update.message, 'from_user'):
                        user_id = update.message.from_user.id
                    
                    if user_id and not global_rate_limiter.is_allowed(user_id, action_type):
                        logger.warning(f"Rate limit exceeded for user {user_id}, action {action_type}")
                        
                        # Try to send rate limit message
                        try:
                            if hasattr(update, 'message') and update.message:
                                await update.message.reply_text(
                                    "⚠️ Слишком много запросов. Пожалуйста, подождите немного."
                                )
                        except:
                            pass  # Ignore errors when sending rate limit message
                        return
                
                # Execute function
                return await func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in rate limiter wrapper: {e}")
                # Execute function without rate limiting on error
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def rate_limit_emotion_entry(func):
    """Rate limiter specifically for emotion entries"""
    return rate_limit('emotion_entry')(func)

def rate_limit_summary(func):
    """Rate limiter specifically for summary requests"""
    return rate_limit('summary_request')(func)

def rate_limit_export(func):
    """Rate limiter specifically for export requests"""
    return rate_limit('export_request')(func)

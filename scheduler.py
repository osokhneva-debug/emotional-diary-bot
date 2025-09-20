# security.py
import re
import html
import logging
from typing import Optional
import bleach
from datetime import datetime, timedelta
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks and limit length
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized and truncated text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    # HTML escape to prevent injection
    text = html.escape(text)
    
    # Remove potentially malicious patterns
    # Remove script tags and similar
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    # Remove excessive special characters that might be used for injection
    text = re.sub(r'[<>"\'{};]', '', text)
    
    # Remove null bytes and control characters except newlines and tabs
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
    
    return text

def validate_emotion_data(emotions: list, category: str, valence: float, arousal: float) -> bool:
    """
    Validate emotion entry data
    
    Args:
        emotions: List of emotion strings
        category: Emotion category
        valence: Valence value (-1 to 1)
        arousal: Arousal value (0 to 2)
        
    Returns:
        True if data is valid, False otherwise
    """
    try:
        # Check emotions list
        if not isinstance(emotions, list) or len(emotions) == 0:
            return False
        
        if len(emotions) > 10:  # Max 10 emotions per entry
            return False
        
        for emotion in emotions:
            if not isinstance(emotion, str) or len(emotion) > 50:
                return False
        
        # Check category
        if not isinstance(category, str) or len(category) > 100:
            return False
        
        # Check valence range
        if not isinstance(valence, (int, float)) or not (-1 <= valence <= 1):
            return False
        
        # Check arousal range
        if not isinstance(arousal, (int, float)) or not (0 <= arousal <= 2):
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating emotion data: {e}")
        return False

def validate_timezone(timezone_str: str) -> bool:
    """
    Validate timezone string
    
    Args:
        timezone_str: Timezone string to validate
        
    Returns:
        True if valid timezone, False otherwise
    """
    try:
        import pytz
        return timezone_str in pytz.all_timezones
    except Exception:
        return False

def validate_time_format(time_str: str) -> bool:
    """
    Validate time format (HH:MM)
    
    Args:
        time_str: Time string to validate
        
    Returns:
        True if valid format, False otherwise
    """
    try:
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return bool(re.match(pattern, time_str))
    except Exception:
        return False

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

def detect_spam_patterns(text: str) -> bool:
    """
    Detect potential spam patterns in text
    
    Args:
        text: Text to analyze
        
    Returns:
        True if spam detected, False otherwise
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Spam indicators
    spam_patterns = [
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',  # URLs
        r'@\w+',  # @ mentions
        r'#\w+',  # Hashtags in excess
        r'(.)\1{10,}',  # Repeated characters (10+ times)
        r'\b(buy|sell|discount|offer|free|money|cash|prize|winner|click|visit)\b',  # Commercial keywords
    ]
    
    # Check for spam patterns
    for pattern in spam_patterns:
        if re.search(pattern, text_lower):
            return True
    
    # Check for excessive repetition
    words = text_lower.split()
    if len(words) > 5:
        unique_words = set(words)
        if len(unique_words) / len(words) < 0.3:  # Less than 30% unique words
            return True
    
    # Check for excessive caps
    if len(text) > 10:
        caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
        if caps_ratio > 0.7:  # More than 70% caps
            return True
    
    return False

def validate_user_settings(settings_data: dict) -> bool:
    """
    Validate user settings data
    
    Args:
        settings_data: Dictionary with user settings
        
    Returns:
        True if valid, False otherwise
    """
    try:
        valid_frequencies = ['normal', 'reduced', 'minimal']
        
        # Check notification frequency
        if 'notification_frequency' in settings_data:
            if settings_data['notification_frequency'] not in valid_frequencies:
                return False
        
        # Check weekend notifications
        if 'weekend_notifications' in settings_data:
            if not isinstance(settings_data['weekend_notifications'], bool):
                return False
        
        # Check daily ping times
        if 'daily_ping_times' in settings_data:
            times = settings_data['daily_ping_times']
            if not isinstance(times, list) or len(times) > 10:
                return False
            
            for time_str in times:
                if not validate_time_format(time_str):
                    return False
        
        # Check summary time
        if 'weekly_summary_time' in settings_data:
            if not validate_time_format(settings_data['weekly_summary_time']):
                return False
        
        # Check summary day
        if 'weekly_summary_day' in settings_data:
            day = settings_data['weekly_summary_day']
            if not isinstance(day, int) or not (0 <= day <= 6):
                return False
        
        # Check data retention
        if 'data_retention_days' in settings_data:
            days = settings_data['data_retention_days']
            if not isinstance(days, int) or not (30 <= days <= 3650):  # 30 days to 10 years
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating user settings: {e}")
        return False

class SecurityLogger:
    """Logger for security events"""
    
    def __init__(self):
        self.security_logger = logging.getLogger('security')
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.security_logger.addHandler(handler)
        self.security_logger.setLevel(logging.WARNING)
    
    def log_rate_limit(self, user_id: int, action: str):
        """Log rate limit event"""
        self.security_logger.warning(f"Rate limit exceeded - User: {user_id}, Action: {action}")
    
    def log_spam_attempt(self, user_id: int, content: str):
        """Log spam attempt"""
        self.security_logger.warning(f"Spam detected - User: {user_id}, Content: {content[:100]}")
    
    def log_invalid_data(self, user_id: int, data_type: str, error: str):
        """Log invalid data submission"""
        self.security_logger.warning(f"Invalid data - User: {user_id}, Type: {data_type}, Error: {error}")
    
    def log_injection_attempt(self, user_id: int, content: str):
        """Log potential injection attempt"""
        self.security_logger.error(f"Injection attempt - User: {user_id}, Content: {content[:100]}")

# Global security logger instance
security_logger = SecurityLogger()

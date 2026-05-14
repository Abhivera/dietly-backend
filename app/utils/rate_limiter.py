import time
import logging
from typing import Dict, Tuple
from fastapi import HTTPException, Request

from app.core.client_ip import get_client_ip
import threading

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = {}
        self.lock = threading.Lock()
        self.cleanup_interval = 3600  # 1 hour
        self.last_cleanup = time.time()
    
    def _cleanup_old_requests(self):
        """Remove requests older than 24 hours"""
        current_time = time.time()
        cutoff_time = current_time - 86400  # 24 hours
        
        with self.lock:
            for ip in list(self.requests.keys()):
                self.requests[ip] = [
                    req_time for req_time in self.requests[ip] 
                    if req_time > cutoff_time
                ]
                if not self.requests[ip]:
                    del self.requests[ip]
        
        self.last_cleanup = current_time
    
    def check_rate_limit(self, ip: str, max_requests: int = 5) -> Tuple[bool, int]:
        """
        Check if IP has exceeded rate limit
        Returns: (allowed, remaining_requests)
        """
        current_time = time.time()
        
        # Cleanup old requests periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_requests()
        
        with self.lock:
            if ip not in self.requests:
                self.requests[ip] = []
            
            # Remove requests older than 24 hours
            cutoff_time = current_time - 86400  # 24 hours
            self.requests[ip] = [
                req_time for req_time in self.requests[ip] 
                if req_time > cutoff_time
            ]
            
            # Count requests in the last 24 hours
            recent_requests = len(self.requests[ip])
            
            if recent_requests >= max_requests:
                return False, 0
            
            # Add current request
            self.requests[ip].append(current_time)
            
            return True, max_requests - recent_requests - 1

# Global rate limiter instance
rate_limiter = RateLimiter()

def check_daily_rate_limit(request: Request, max_requests: int = 5):
    """
    Dependency function to check daily rate limit for an IP
    """
    client_ip = get_client_ip(request)

    # Check rate limit
    allowed, remaining = rate_limiter.check_rate_limit(client_ip, max_requests)

    if not allowed:
        logger.warning(
            "rate_limit_exceeded ip=%s max_requests_per_day=%s",
            client_ip,
            max_requests,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Maximum {max_requests} requests per day exceeded",
                "retry_after": "24 hours",
            },
        )
    
    return {"remaining_requests": remaining} 
# utils/rate_limiter.py
"""Rate limiting utilities for pygallery."""

import time
from collections import defaultdict, deque
from functools import wraps
from typing import Dict, Deque, Tuple, Callable, Any
from flask import request, jsonify, g


class RateLimiter:
    """Simple rate limiter implementation."""
    
    def __init__(self):
        # Store request timestamps per IP
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
        # Store rate limit rules: endpoint -> (requests_per_minute, window_seconds)
        self.rules: Dict[str, Tuple[int, int]] = {}
    
    def add_rule(self, endpoint: str, requests_per_minute: int, window_seconds: int = 60):
        """
        Add a rate limiting rule for an endpoint.
        
        Args:
            endpoint: The endpoint name (e.g., 'api.albums')
            requests_per_minute: Maximum requests allowed per minute
            window_seconds: Time window in seconds (default: 60)
        """
        self.rules[endpoint] = (requests_per_minute, window_seconds)
    
    def is_allowed(self, endpoint: str, client_ip: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a request is allowed based on rate limiting rules.
        
        Args:
            endpoint: The endpoint name
            client_ip: The client's IP address
            
        Returns:
            Tuple of (allowed, info_dict) where info_dict contains rate limit info
        """
        if endpoint not in self.rules:
            return True, {}
        
        max_requests, window_seconds = self.rules[endpoint]
        current_time = time.time()
        
        # Clean old requests outside the window
        client_requests = self.requests[client_ip]
        while client_requests and client_requests[0] < current_time - window_seconds:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) < max_requests:
            client_requests.append(current_time)
            return True, {
                'limit': max_requests,
                'remaining': max_requests - len(client_requests),
                'reset_time': current_time + window_seconds
            }
        else:
            return False, {
                'limit': max_requests,
                'remaining': 0,
                'reset_time': client_requests[0] + window_seconds
            }


# Global rate limiter instance
rate_limiter = RateLimiter()

# Configure default rate limits
rate_limiter.add_rule('api.api_albums', 60)  # 60 requests per minute
rate_limiter.add_rule('api.api_album_photos_nested', 120)  # 120 requests per minute
rate_limiter.add_rule('api.api_album_photos_root', 120)  # 120 requests per minute


def get_client_ip() -> str:
    """Get client IP address, handling proxies."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or 'unknown'


def rate_limit(endpoint: str = None):
    """
    Decorator for rate limiting endpoints.
    
    Args:
        endpoint: Optional endpoint name. If not provided, uses the function name.
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            # Determine endpoint name
            endpoint_name = endpoint or f.__name__
            if hasattr(f, '__module__') and f.__module__:
                endpoint_name = f"{f.__module__}.{endpoint_name}"
            
            # Get client IP
            client_ip = get_client_ip()
            
            # Check rate limit
            allowed, info = rate_limiter.is_allowed(endpoint_name, client_ip)
            
            if not allowed:
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Try again in {int(info["reset_time"] - time.time())} seconds.',
                    'limit': info['limit'],
                    'reset_time': info['reset_time']
                })
                response.status_code = 429
                response.headers['X-RateLimit-Limit'] = str(info['limit'])
                response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
                response.headers['X-RateLimit-Reset'] = str(int(info['reset_time']))
                response.headers['Retry-After'] = str(int(info['reset_time'] - time.time()))
                return response
            
            # Add rate limit headers to successful responses
            g.rate_limit_info = info
            
            # Call the original function
            response = f(*args, **kwargs)
            
            # Add rate limit headers if we have info
            if hasattr(g, 'rate_limit_info') and g.rate_limit_info:
                if hasattr(response, 'headers'):
                    response.headers['X-RateLimit-Limit'] = str(g.rate_limit_info.get('limit', ''))
                    response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_info.get('remaining', ''))
                    response.headers['X-RateLimit-Reset'] = str(int(g.rate_limit_info.get('reset_time', 0)))
            
            return response
        
        return decorated_function
    return decorator 
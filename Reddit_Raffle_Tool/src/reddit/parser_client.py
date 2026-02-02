"""
Reddit API parser module - Client version that connects to backend proxy.
This version doesn't require Reddit API credentials on the client side.
"""

import requests
from typing import Dict, Optional
from datetime import datetime


class RedditParser:
    def __init__(self, backend_url: str = "http://localhost:8000"):
        """
        Initialize Reddit API client that connects to backend proxy.
        
        Args:
            backend_url: URL of the backend proxy server
        """
        self.backend_url = backend_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'RedditRaffleTool-Client/1.0'
        })
        print(f"Reddit API client initialized (backend: {self.backend_url})")

    def check_backend_health(self) -> bool:
        """Check if backend is accessible."""
        try:
            response = self.session.get(f"{self.backend_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def extract_post_id_from_url(self, url: str) -> Optional[str]:
        """Extract Reddit post ID from URL."""
        if '/comments/' in url:
            parts = url.split('/comments/')
            if len(parts) > 1:
                post_id = parts[1].split('/')[0]
                return post_id
        return None

    def get_post_comments(self, post_url: str) -> Dict:
        """
        Get comments from a Reddit post via backend proxy.
        Returns dictionary with post info and comments.
        """
        try:
            # Check if backend is available
            if not self.check_backend_health():
                return {"error": "Backend server is not accessible. Please check if it's running."}
            
            # Make request to backend
            response = self.session.post(
                f"{self.backend_url}/api/post/comments",
                json={"post_url": post_url},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                return {"error": "Rate limit exceeded. Please wait a moment and try again."}
            elif response.status_code == 400:
                return {"error": "Invalid Reddit URL"}
            elif response.status_code == 503:
                return {"error": "Backend Reddit API not configured"}
            else:
                return {"error": f"Backend error: {response.status_code}"}
                
        except requests.exceptions.Timeout:
            return {"error": "Request timeout. The post may be too large or the server is slow."}
        except requests.exceptions.ConnectionError:
            return {"error": "Cannot connect to backend server. Make sure it's running."}
        except Exception as e:
            return {"error": f"Failed to fetch post: {e}"}

    def get_post_with_validation(self, post_url: str) -> Dict:
        """
        Get post comments (wrapper for compatibility).
        The validation logic is handled by the backend.
        """
        return self.get_post_comments(post_url)

    def format_timestamp(self, utc_timestamp: float) -> str:
        """Convert UTC timestamp to readable format."""
        dt = datetime.fromtimestamp(utc_timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def is_api_ready(self) -> bool:
        """Check if the backend API is ready."""
        return self.check_backend_health()


def test_reddit_parser():
    """Test the Reddit parser with backend."""
    parser = RedditParser()
    
    # Check backend health
    print(f"Backend healthy: {parser.check_backend_health()}")
    
    # Test URL
    test_url = "https://www.reddit.com/r/test/comments/example/"
    result = parser.get_post_comments(test_url)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Title: {result['title']}")
        print(f"Comments: {len(result['comments'])}")


if __name__ == "__main__":
    test_reddit_parser()

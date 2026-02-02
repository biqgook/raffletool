"""
Reddit Raffle Tool - Backend Proxy API
A FastAPI backend that proxies Reddit API requests to protect credentials.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, Optional
import praw
import configparser
import os
from datetime import datetime
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize rate limiter (10 requests per minute per IP)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Reddit Raffle Tool API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - restrict this in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, change to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Reddit API
reddit_client = None

def initialize_reddit():
    """Initialize Reddit API with credentials from config file."""
    global reddit_client
    
    config_path = os.path.join(os.path.dirname(__file__), "config.ini")
    if not os.path.exists(config_path):
        logger.error(f"Config file not found at {config_path}")
        return False
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    try:
        reddit_client = praw.Reddit(
            client_id=config['reddit']['client_id'],
            client_secret=config['reddit']['client_secret'],
            user_agent=config['reddit']['user_agent']
        )
        logger.info("Reddit API initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Reddit API: {e}")
        return False

# Initialize on startup
@app.on_event("startup")
async def startup_event():
    if not initialize_reddit():
        logger.warning("Reddit API not initialized - check config.ini")

# Request models
class PostRequest(BaseModel):
    post_url: str

# Health check endpoint
@app.get("/")
async def root():
    return {
        "service": "Reddit Raffle Tool API",
        "status": "online",
        "reddit_api": "ready" if reddit_client else "not configured"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Main endpoint to fetch post comments
@app.post("/api/post/comments")
@limiter.limit("10/minute")
async def get_post_comments(request: Request, post_request: PostRequest):
    """
    Fetch comments from a Reddit post.
    Rate limited to 10 requests per minute per IP.
    """
    if not reddit_client:
        raise HTTPException(status_code=503, detail="Reddit API not initialized")
    
    post_url = post_request.post_url
    logger.info(f"Fetching comments for: {post_url}")
    
    # Extract post ID
    post_id = extract_post_id_from_url(post_url)
    if not post_id:
        raise HTTPException(status_code=400, detail="Invalid Reddit URL")
    
    try:
        submission = reddit_client.submission(id=post_id)
        submission.comments.replace_more(limit=None)
        
        post_info = {
            "title": submission.title,
            "author": submission.author.name if submission.author else "[deleted]",
            "created_utc": submission.created_utc,
            "url": post_url,
            "body": submission.selftext,
            "comments": []
        }
        
        # Process comments (same logic as original parser)
        author_spot_assignments = {}
        removed_users = set()
        
        # First pass: Find spot assignments and removed users
        for comment in submission.comments.list():
            if comment.author and comment.author.name == post_info["author"]:
                comment_body = comment.body.lower().strip()
                
                # Check for removal patterns
                if any(pattern in comment_body for pattern in [
                    "unpaid participants: your unpaid slots have been removed",
                    "removed due to lack of payment",
                    "slots have been removed",
                    "attention unpaid participants"
                ]):
                    mentioned_users = re.findall(r'u/(\w+)', comment.body)
                    removed_users.update(mentioned_users)
                
                # Username-only mentions
                username_match = re.match(r'^/?u/(\w+)$', comment.body.strip())
                if username_match:
                    removed_users.add(username_match.group(1))
                
                # Spot assignments
                spots = extract_spots_from_author_reply(comment.body)
                if spots > 0:
                    try:
                        parent_comment = comment.parent()
                        if hasattr(parent_comment, 'author') and parent_comment.author:
                            if parent_comment.author.name not in removed_users:
                                author_spot_assignments[parent_comment.id] = spots
                    except:
                        pass
        
        # Second pass: Extract user comments
        for comment in submission.comments.list():
            if comment.author and comment.author.name != post_info["author"]:
                if comment.author.name in removed_users:
                    continue
                
                spots_assigned = author_spot_assignments.get(comment.id, 0)
                comment_data = {
                    "author": comment.author.name,
                    "body": comment.body,
                    "created_utc": comment.created_utc,
                    "score": comment.score,
                    "id": comment.id,
                    "spots": spots_assigned
                }
                post_info["comments"].append(comment_data)
        
        # Sort by time
        post_info["comments"].sort(key=lambda x: x["created_utc"])
        
        logger.info(f"Successfully fetched {len(post_info['comments'])} comments")
        return post_info
        
    except Exception as e:
        logger.error(f"Error fetching post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch post: {str(e)}")

# Helper functions
def extract_post_id_from_url(url: str) -> Optional[str]:
    """Extract Reddit post ID from URL."""
    if '/comments/' in url:
        parts = url.split('/comments/')
        if len(parts) > 1:
            return parts[1].split('/')[0]
    return None

def extract_spots_from_author_reply(reply_text: str) -> int:
    """Extract number of spots from author's reply."""
    text = reply_text.lower().strip()
    
    # Explicit "X spots" pattern
    spots_match = re.search(r'you got (\d+) spots?', text)
    if spots_match:
        return int(spots_match.group(1))
    
    # Count individual numbers after "you got"
    if "you got" in text:
        lines = text.split('\n')
        you_got_line = None
        for line in lines:
            if "you got" in line:
                you_got_line = line.strip()
                break
        
        if you_got_line:
            after_you_got = you_got_line.split("you got", 1)[1]
            stop_markers = ["please follow", "send payment", "after payment", "if you", "\n"]
            for marker in stop_markers:
                if marker in after_you_got:
                    after_you_got = after_you_got.split(marker)[0]
                    break
            
            # Count numbers
            numbers = re.findall(r'\b\d+\b', after_you_got)
            if numbers:
                return len(numbers)
    
    return 0

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

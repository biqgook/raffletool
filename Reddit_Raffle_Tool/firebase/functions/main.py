"""
Reddit Raffle Tool - Firebase Cloud Functions Backend
Serverless backend that proxies Reddit API requests.
"""

from firebase_functions import https_fn, options
from firebase_admin import initialize_app
import praw
import re
from typing import Dict, Optional

# Initialize Firebase
initialize_app()

# Initialize Reddit client (loaded from environment variables)
reddit_client = None

def get_reddit_client():
    """Lazy load Reddit client with credentials from environment."""
    global reddit_client
    if reddit_client is None:
        import os
        reddit_client = praw.Reddit(
            client_id=os.environ.get('REDDIT_CLIENT_ID'),
            client_secret=os.environ.get('REDDIT_CLIENT_SECRET'),
            user_agent=os.environ.get('REDDIT_USER_AGENT', 'RedditRaffleTool/1.0')
        )
    return reddit_client

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
            
            numbers = re.findall(r'\b\d+\b', after_you_got)
            if numbers:
                return len(numbers)
    
    return 0

@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins=["*"],  # In production, specify your domains
        cors_methods=["get", "post"],
    ),
    memory=options.MemoryOption.MB_256,
    timeout_sec=60
)
def get_post_comments(req: https_fn.Request) -> https_fn.Response:
    """
    Cloud Function to fetch Reddit post comments.
    
    Request body:
        {
            "post_url": "https://www.reddit.com/r/..."
        }
    
    Response:
        {
            "title": "...",
            "author": "...",
            "created_utc": 123456789,
            "url": "...",
            "body": "...",
            "comments": [...]
        }
    """
    
    # Handle preflight
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)
    
    # Only accept POST
    if req.method != "POST":
        return https_fn.Response(
            {"error": "Method not allowed"}, 
            status=405,
            headers={"Content-Type": "application/json"}
        )
    
    try:
        # Parse request
        data = req.get_json()
        if not data or 'post_url' not in data:
            return https_fn.Response(
                {"error": "Missing post_url in request body"},
                status=400,
                headers={"Content-Type": "application/json"}
            )
        
        post_url = data['post_url']
        
        # Validate URL
        post_id = extract_post_id_from_url(post_url)
        if not post_id:
            return https_fn.Response(
                {"error": "Invalid Reddit URL"},
                status=400,
                headers={"Content-Type": "application/json"}
            )
        
        # Get Reddit client
        reddit = get_reddit_client()
        
        # Fetch submission
        submission = reddit.submission(id=post_id)
        submission.comments.replace_more(limit=None)
        
        post_info = {
            "title": submission.title,
            "author": submission.author.name if submission.author else "[deleted]",
            "created_utc": submission.created_utc,
            "url": post_url,
            "body": submission.selftext,
            "comments": []
        }
        
        # Process comments
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
        
        return https_fn.Response(
            post_info,
            status=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        return https_fn.Response(
            {"error": f"Failed to fetch post: {str(e)}"},
            status=500,
            headers={"Content-Type": "application/json"}
        )

@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins=["*"],
        cors_methods=["get"],
    )
)
def health(req: https_fn.Request) -> https_fn.Response:
    """Health check endpoint."""
    import datetime
    return https_fn.Response(
        {
            "status": "healthy",
            "service": "Reddit Raffle Tool API",
            "timestamp": datetime.datetime.utcnow().isoformat()
        },
        status=200,
        headers={"Content-Type": "application/json"}
    )

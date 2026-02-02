# Reddit Raffle Tool - Backend Proxy Setup

This guide explains how to deploy the backend proxy service to protect your Reddit API credentials.

## Architecture Overview

- **Backend** (FastAPI): Hosts your Reddit API credentials securely, exposes REST endpoints
- **Client** (Your app): Makes requests to backend instead of directly to Reddit

## Setup Instructions

### 1. Backend Setup (Your Server)

1. Navigate to the backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy config file and add your Reddit credentials:
```bash
copy config.ini.example config.ini
```
Edit `config.ini` with your Reddit API credentials.

4. Run the server:
```bash
python main.py
```

The server will start on `http://localhost:8000`

### 2. Client Setup (For Users)

Users need to update their app to use the backend. Modify the import in their code:

**Option A: Update existing code**
```python
# In src/reddit/parser.py or wherever RedditParser is imported
from reddit.parser_client import RedditParser  # Changed from parser to parser_client

# Then use it normally:
parser = RedditParser(backend_url="https://your-deployed-backend.com")
```

**Option B: Use environment variable**
Create a `config.ini` in the client with:
```ini
[backend]
url = https://your-deployed-backend.com
```

### 3. Deploy Backend to Cloud

#### Option A: Railway (Easiest)
1. Go to [Railway.app](https://railway.app)
2. Create new project from GitHub repo
3. Add environment variables (or upload config.ini as secret)
4. Deploy - you'll get a public URL

#### Option B: Heroku
```bash
# Install Heroku CLI, then:
cd backend
heroku create your-app-name
git init
git add .
git commit -m "Initial commit"
git push heroku main
```

#### Option C: DigitalOcean/AWS/VPS
```bash
# SSH into your server
git clone your-repo
cd backend
pip install -r requirements.txt

# Run with systemd or use screen/tmux
uvicorn main:app --host 0.0.0.0 --port 8000
```

For production, use a process manager like systemd or PM2.

### 4. Security Considerations

1. **Rate Limiting**: Already implemented (10 req/min per IP)
2. **CORS**: Update `allow_origins` in `backend/main.py` to your domain
3. **HTTPS**: Use a reverse proxy (nginx) with SSL certificate
4. **API Keys**: Consider adding API key authentication for additional security

Example with API key middleware:
```python
# In backend/main.py
from fastapi import Header, HTTPException

@app.post("/api/post/comments")
async def get_post_comments(
    request: Request, 
    post_request: PostRequest,
    x_api_key: str = Header(...)
):
    if x_api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    # ... rest of code
```

### 5. Testing

Test the backend locally:
```bash
# Terminal 1: Start backend
cd backend
python main.py

# Terminal 2: Test endpoint
curl -X POST http://localhost:8000/api/post/comments \
  -H "Content-Type: application/json" \
  -d '{"post_url": "https://www.reddit.com/r/test/comments/..."}'
```

### 6. Monitoring

Add basic logging and monitoring:
- Check logs: `tail -f logs/app.log`
- Monitor with Railway/Heroku dashboard
- Set up alerts for downtime

## API Endpoints

### GET /
Health check - returns service status

### GET /health
Health check with timestamp

### POST /api/post/comments
Fetch Reddit post comments

**Request:**
```json
{
  "post_url": "https://www.reddit.com/r/subreddit/comments/..."
}
```

**Response:**
```json
{
  "title": "Post title",
  "author": "username",
  "created_utc": 1234567890,
  "url": "...",
  "body": "Post body text",
  "comments": [
    {
      "author": "commenter",
      "body": "Comment text",
      "created_utc": 1234567890,
      "score": 5,
      "id": "abc123",
      "spots": 2
    }
  ]
}
```

## Cost Estimates

- **Railway**: Free tier available, ~$5/month for hobby
- **Heroku**: Free tier deprecated, ~$7/month for basic
- **DigitalOcean**: $5/month for basic droplet
- **AWS/GCP**: Varies, can use free tier

## Distribution

When distributing your app to users:

1. Point them to your deployed backend URL
2. They don't need Reddit API credentials
3. Include `parser_client.py` instead of `parser.py`
4. Update requirements.txt to include `requests` instead of `praw`

## Troubleshooting

**Backend not starting:**
- Check config.ini exists and has valid credentials
- Verify port 8000 is not in use: `netstat -ano | findstr :8000`

**Client can't connect:**
- Check backend URL is correct
- Verify firewall allows outbound connections
- Test with curl first

**Rate limiting too strict:**
- Adjust `@limiter.limit("10/minute")` in backend/main.py
- Consider implementing user-specific rate limits

**Reddit API errors:**
- Check credentials in backend config.ini
- Verify Reddit app is active at reddit.com/prefs/apps
- Check rate limits on Reddit's side

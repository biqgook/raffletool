# Deploy Reddit Raffle Tool to Firebase

Complete guide to deploy your backend as a serverless Firebase Cloud Function.

## Why Firebase?

- **Free Tier**: 2 million invocations/month, 400K GB-seconds
- **Auto-scaling**: Handles traffic spikes automatically
- **Zero DevOps**: No servers to manage
- **Global CDN**: Fast response times worldwide
- **Easy Setup**: Deploy in 5 minutes

## Prerequisites

1. Google Account
2. Node.js installed (for Firebase CLI)
3. Python 3.9+ (for Cloud Functions)

## Step-by-Step Setup

### 1. Install Firebase CLI

```powershell
npm install -g firebase-tools
```

### 2. Login to Firebase

```powershell
firebase login
```

### 3. Create Firebase Project

Go to [Firebase Console](https://console.firebase.google.com):
1. Click "Add Project"
2. Enter project name (e.g., "reddit-raffle-tool")
3. Disable Google Analytics (optional)
4. Wait for project creation

### 4. Initialize Firebase in Your Project

```powershell
cd "c:\Users\-\Desktop\Discord Projects\Reddit_Raffle_Tool\firebase"
firebase init functions
```

Select:
- Use existing project → Select your project
- Language → Python
- Install dependencies → Yes

### 5. Set Reddit API Credentials

```powershell
firebase functions:config:set reddit.client_id="YOUR_CLIENT_ID"
firebase functions:config:set reddit.client_secret="YOUR_CLIENT_SECRET"
firebase functions:config:set reddit.user_agent="RedditRaffleTool/1.0"
```

Verify:
```powershell
firebase functions:config:get
```

### 6. Deploy Functions

```powershell
firebase deploy --only functions
```

After deployment, you'll get URLs like:
```
https://us-central1-your-project-id.cloudfunctions.net/get_post_comments
https://us-central1-your-project-id.cloudfunctions.net/health
```

### 7. Test Your Function

```powershell
# Test health check
curl https://us-central1-your-project-id.cloudfunctions.net/health

# Test post fetching
curl -X POST https://us-central1-your-project-id.cloudfunctions.net/get_post_comments `
  -H "Content-Type: application/json" `
  -d '{\"post_url\": \"https://www.reddit.com/r/test/comments/example/\"}'
```

### 8. Update Client Code

Update your client to use the Firebase function URL:

```python
# In your distributed app
from reddit.parser_client import RedditParser

parser = RedditParser(
    backend_url="https://us-central1-your-project-id.cloudfunctions.net"
)

# Use normally
result = parser.get_post_comments("https://www.reddit.com/r/...")
```

## Local Development & Testing

### Run Functions Locally

```powershell
cd firebase\functions

# Set local environment variables
$env:REDDIT_CLIENT_ID="your_id"
$env:REDDIT_CLIENT_SECRET="your_secret"
$env:REDDIT_USER_AGENT="RedditRaffleTool/1.0"

# Start emulator
firebase emulators:start --only functions
```

Functions will be available at:
```
http://localhost:5001/your-project-id/us-central1/get_post_comments
http://localhost:5001/your-project-id/us-central1/health
```

### Test Locally

```powershell
# Test with PowerShell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:5001/your-project-id/us-central1/get_post_comments" `
  -ContentType "application/json" `
  -Body '{"post_url": "https://www.reddit.com/r/test/comments/..."}'
```

## Security & Production Setup

### 1. Restrict CORS Origins

Edit [functions/main.py](c:\Users\-\Desktop\Discord Projects\Reddit_Raffle_Tool\firebase\functions\main.py):

```python
@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins=["https://yourdomain.com"],  # Your specific domain
        cors_methods=["post"],
    ),
    # ...
)
```

### 2. Add Authentication (Optional)

```python
from firebase_admin import auth

@https_fn.on_request()
def get_post_comments(req: https_fn.Request):
    # Verify Firebase Auth token
    id_token = req.headers.get('Authorization', '').replace('Bearer ', '')
    
    try:
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token['uid']
    except:
        return https_fn.Response({"error": "Unauthorized"}, status=401)
    
    # ... rest of function
```

### 3. Add Rate Limiting with Firestore

```python
from firebase_admin import firestore

@https_fn.on_request()
def get_post_comments(req: https_fn.Request):
    db = firestore.client()
    
    # Get client IP
    client_ip = req.headers.get('X-Forwarded-For', 'unknown')
    
    # Check rate limit
    rate_doc = db.collection('rate_limits').document(client_ip).get()
    if rate_doc.exists:
        data = rate_doc.to_dict()
        if data['count'] >= 10:  # 10 requests
            return https_fn.Response(
                {"error": "Rate limit exceeded"}, 
                status=429
            )
    
    # Update counter
    db.collection('rate_limits').document(client_ip).set({
        'count': firestore.Increment(1),
        'timestamp': firestore.SERVER_TIMESTAMP
    }, merge=True)
    
    # ... rest of function
```

## Monitoring & Logs

### View Logs

```powershell
firebase functions:log
```

Or visit: [Firebase Console](https://console.firebase.google.com) → Functions → Logs

### Monitor Usage

Firebase Console → Functions → Dashboard shows:
- Invocations per minute
- Execution time
- Memory usage
- Error rate

### Set Up Alerts

Firebase Console → Alerts → Create Alert:
- Error rate > 5%
- Function timeout
- High memory usage

## Cost Estimation

### Free Tier (Spark Plan)
- 2M invocations/month
- 400K GB-seconds compute
- 200K CPU-seconds
- 5GB network egress

**Typical usage**: ~10,000 requests/month = **FREE**

### Paid Tier (Blaze Plan)
After free tier:
- $0.40 per million invocations
- $0.0000025 per GB-second
- $0.10 per GB network egress

**Example**: 100K requests/month ≈ **$0.50/month**

## Deployment Best Practices

### 1. Use Environment-Specific Configs

```powershell
# Development
firebase use dev-project
firebase deploy --only functions

# Production
firebase use prod-project
firebase deploy --only functions
```

### 2. Deploy Only Changed Functions

```powershell
firebase deploy --only functions:get_post_comments
```

### 3. Set Function Memory & Timeout

In [functions/main.py](c:\Users\-\Desktop\Discord Projects\Reddit_Raffle_Tool\firebase\functions\main.py):

```python
@https_fn.on_request(
    memory=options.MemoryOption.MB_512,  # Increase if needed
    timeout_sec=120,  # Max 540 seconds
)
```

### 4. Version Your Functions

```powershell
# Tag releases
git tag -a v1.0.0 -m "Initial release"
git push origin v1.0.0

# Deploy with version in name
firebase deploy --only functions
```

## Troubleshooting

### Function Times Out
- Increase timeout: `timeout_sec=120`
- Optimize: Cache Reddit client, reduce comment processing

### CORS Errors
- Check `cors_origins` in function decorator
- Ensure client sends proper headers

### Cold Start Delays
- Use minimum instances (paid feature):
  ```python
  @https_fn.on_request(
      min_instances=1  # Keep 1 instance warm
  )
  ```

### Environment Variables Not Working
```powershell
# Check config
firebase functions:config:get

# Re-deploy after config change
firebase deploy --only functions
```

## Distribution

When sharing your app:

1. **Give users the Firebase function URL**:
   ```
   https://us-central1-your-project-id.cloudfunctions.net
   ```

2. **They use parser_client.py**:
   ```python
   parser = RedditParser(backend_url="YOUR_FIREBASE_URL")
   ```

3. **No credentials needed** on their end!

4. **Optional**: Create a custom domain:
   - Firebase Console → Hosting
   - Connect domain
   - Use `https://api.yourdomain.com`

## Updating Functions

```powershell
# 1. Make changes to functions/main.py
# 2. Test locally
firebase emulators:start --only functions

# 3. Deploy
firebase deploy --only functions

# 4. Verify
curl https://your-function-url/health
```

## Backup & Rollback

```powershell
# View deployment history
firebase functions:list

# Rollback to previous version
firebase rollback functions:get_post_comments
```

## Additional Resources

- [Firebase Functions Docs](https://firebase.google.com/docs/functions)
- [Python Functions Guide](https://firebase.google.com/docs/functions/get-started?gen=2nd#python)
- [Firebase Pricing](https://firebase.google.com/pricing)
- [Cloud Functions Quotas](https://cloud.google.com/functions/quotas)

## Quick Reference

```powershell
# Deploy
firebase deploy --only functions

# View logs
firebase functions:log

# Check config
firebase functions:config:get

# Test locally
firebase emulators:start --only functions

# Delete function
firebase functions:delete get_post_comments
```

# Railway Deployment Guide for appElectrisimBackend

## Prerequisites
- GitHub account with your repository
- Railway account (https://railway.app)
- Git installed locally

## Step 1: Push Your Code to GitHub

If you haven't already pushed this project to GitHub:

```bash
# Navigate to your project directory
cd C:\Users\DELL\.vscode\appElectrisimBackend\appElectrisimBackend

# Initialize git if not already done
git init

# Add all files (respecting .gitignore)
git add .

# Commit your changes
git commit -m "Prepare for Railway deployment"

# Add your GitHub repository as remote (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/appElectrisimBackend.git

# Push to GitHub
git push -u origin main
```

## Step 2: Deploy to Railway

### Option A: Deploy via Railway Dashboard (Recommended)

1. **Login to Railway**: Go to https://railway.app and login

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Authorize Railway to access your GitHub if prompted
   - Select your `appElectrisimBackend` repository

3. **Railway will automatically**:
   - Detect it's a Python project
   - Read your `requirements.txt`
   - Use `Procfile` for the start command
   - Build and deploy your app

4. **Configure Environment Variables** (if needed):
   - Click on your service
   - Go to "Variables" tab
   - Add any environment variables (optional):
     ```
     FLASK_ENV=production
     CORS_ORIGINS=https://app.electrisim.com,https://www.electrisim.com
     ```

5. **Get Your Deployment URL**:
   - Railway will provide a URL like: `https://your-app.railway.app`
   - Click "Settings" → "Generate Domain" if not auto-generated

### Option B: Deploy via Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login to Railway
railway login

# Link to your project or create new one
railway link

# Deploy
railway up
```

## Step 3: Enable GitHub Auto-Deploy

Railway automatically enables GitHub auto-deploy by default! 

**How it works:**
- Every time you push to your `main` branch, Railway will:
  1. Detect the changes
  2. Build the new version
  3. Deploy it automatically
  4. Zero-downtime deployment

**To verify:**
- Go to your Railway project
- Click on "Deployments" tab
- You should see "Connected to GitHub" with auto-deploy enabled

## Step 4: Test Your Deployment

1. Get your Railway URL (e.g., `https://your-app.railway.app`)

2. Test the endpoint:
```bash
curl https://your-app.railway.app/
```

You should see: "Please send data to backend"

3. Test with your frontend by updating the API URL to your Railway URL

## Step 5: Update Frontend CORS Origins (if needed)

If your frontend needs to connect from a new domain, add it to environment variables:

In Railway Dashboard:
- Variables → Add Variable
- Name: `CORS_ORIGINS`
- Value: `https://your-frontend-domain.com,https://app.electrisim.com`

## Monitoring & Logs

- **View Logs**: Railway Dashboard → Your Service → "Logs" tab
- **View Metrics**: Dashboard shows CPU, Memory, Network usage
- **Deployments**: See all deployment history and rollback if needed

## Cost Estimation

Railway pricing (as of 2024):
- **$5/month** includes:
  - $5 worth of usage credits
  - ~500 hours of runtime for small apps
  - Typically enough for 1-2 backends running 24/7

Monitor your usage in: Dashboard → Account → Usage

## Troubleshooting

### Build Fails
- Check the build logs in Railway
- Verify `requirements.txt` has all dependencies
- Ensure Python version matches `runtime.txt`

### App Crashes
- Check logs for errors
- Verify `Procfile` command: `web: gunicorn app:app`
- Check memory usage (upgrade plan if needed)

### Cannot Connect
- Verify the app is running: Check logs
- Check CORS settings if getting CORS errors
- Ensure Railway domain is generated and active

## Useful Commands

```bash
# View logs locally
railway logs

# Run commands in Railway environment
railway run python app.py

# Check service status
railway status

# Redeploy
railway up --detach
```

## Next Steps

1. ✅ Configure custom domain (optional)
2. ✅ Set up monitoring/alerts
3. ✅ Add database if needed (Railway has PostgreSQL, MongoDB, etc.)
4. ✅ Set up staging environment (create another Railway service)

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- GitHub Issues: Create issues in your repo


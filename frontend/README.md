# Gameplay Analysis - Frontend

React-based web application for video gameplay analysis with AI-powered chat interface.

## 🎯 Overview

A modern, responsive chat interface that allows users to:
- Upload gameplay videos via drag-and-drop
- Automatically analyze videos using AWS Bedrock
- Ask questions about analyzed videos in natural language
- View real-time analysis results and insights

## 🛠️ Tech Stack

- **React 18+** with TypeScript
- **Material-UI (MUI)** for UI components
- **Axios** for API communication
- **React Hooks** for state management
- **AWS Amplify** for deployment

## 📋 Prerequisites

- **Node.js 16+** and npm
- **Backend API** running (see backend README)
- **AWS Account** (for deployment)

## 🚀 Local Development Setup

### 1. Install Dependencies

```bash
cd bedrock-agent/frontend
npm install
```

### 2. Configure Environment Variables

Create `.env.local` file:

```bash
# Backend API URL
REACT_APP_API_URL=http://localhost:8000

# Optional: Enable debug mode
REACT_APP_DEBUG=true
```

**Environment Files:**
- `.env.local` - Local development
- `.env.production` - Production build (used by Amplify)

### 3. Start Development Server

```bash
npm start
```

The app will open at `http://localhost:3000`

### 4. Build for Production

```bash
npm run build
```

Build output will be in the `build/` directory.

## 🌐 AWS Amplify Deployment

### Prerequisites

1. **Backend deployed** and accessible (see backend README)
2. **AWS Account** with Amplify access
3. **Git repository** connected to AWS Amplify

### Deployment Steps

#### Option 1: AWS Amplify Console (Recommended)

1. **Connect Repository**
   - Go to [AWS Amplify Console](https://console.aws.amazon.com/amplify/)
   - Click **New app** → **Host web app**
   - Connect your Git repository (GitHub, GitLab, etc.)
   - Select branch (e.g., `main`)

2. **Configure Build Settings**
   - Amplify will auto-detect `amplify.yml` in the root
   - Build settings are pre-configured:
     ```yaml
     version: 1
     frontend:
       phases:
         preBuild:
           commands:
             - cd bedrock-agent/frontend
             - npm ci
         build:
           commands:
             - npm run build
       artifacts:
         baseDirectory: bedrock-agent/frontend/build
         files:
           - '**/*'
     ```

3. **Add Environment Variables**
   - In Amplify Console → **Environment variables**
   - Add:
     ```
     REACT_APP_API_URL=https://your-backend-url.elasticbeanstalk.com
     ```
   - Replace with your actual backend URL

4. **Deploy**
   - Click **Save and deploy**
   - Deployment takes 3-5 minutes
   - You'll get a URL like: `https://main.d1234567890.amplifyapp.com`

#### Option 2: Amplify CLI

```bash
# Install Amplify CLI
npm install -g @aws-amplify/cli

# Configure Amplify
amplify configure

# Initialize Amplify in your project
cd bedrock-agent/frontend
amplify init

# Add hosting
amplify add hosting
# Choose: Hosting with Amplify Console (Managed hosting)

# Publish
amplify publish
```

### Update Backend URL

After backend deployment, update the environment variable:

1. Go to **Amplify Console** → Your App
2. **Environment variables** → Edit
3. Update `REACT_APP_API_URL` with your backend URL
4. **Redeploy** the app

## 📁 Project Structure

```
frontend/
├── public/
│   └── index.html              # HTML template
├── src/
│   ├── components/             # React components
│   │   ├── VideoUpload.tsx     # Video upload interface
│   │   ├── ChatInterface.tsx   # Chat UI
│   │   ├── VideoPlayer.tsx     # Video playback
│   │   └── AnalysisDisplay.tsx # Analysis results
│   ├── hooks/                  # Custom React hooks
│   │   ├── useVideoUpload.ts   # Video upload logic
│   │   └── useChat.ts          # Chat functionality
│   ├── services/               # API services
│   │   └── api.ts              # Backend API client
│   ├── assets/                 # Images and static files
│   ├── App.tsx                 # Main app component
│   └── index.tsx               # Entry point
├── package.json                # Dependencies
├── tsconfig.json               # TypeScript config
└── README.md                   # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `REACT_APP_API_URL` | Backend API URL | Yes | - |
| `REACT_APP_DEBUG` | Enable debug logging | No | `false` |

### CORS Configuration

The frontend expects the backend to allow CORS from:
- `http://localhost:3000` (development)
- Your Amplify domain (production)

Backend CORS is configured in `backend/api_server.py`.

## 🧪 Testing

### Manual Testing

1. **Start backend** (see backend README)
2. **Start frontend**: `npm start`
3. **Test workflow**:
   - Upload a video
   - Wait for analysis
   - Ask questions in chat
   - Verify responses

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Test CORS
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS http://localhost:8000/upload
```

## 🐛 Troubleshooting

### Issue: "Network Error" when uploading

**Cause:** Backend not running or CORS misconfigured

**Fix:**
```bash
# Check backend is running
curl http://localhost:8000/health

# Verify REACT_APP_API_URL in .env.local
cat .env.local
```

### Issue: "Failed to fetch" in production

**Cause:** Incorrect backend URL in Amplify environment variables

**Fix:**
1. Go to Amplify Console → Environment variables
2. Verify `REACT_APP_API_URL` is correct
3. Redeploy the app

### Issue: Build fails in Amplify

**Cause:** Missing dependencies or build errors

**Fix:**
```bash
# Test build locally
npm run build

# Check Amplify build logs in console
# Common issues:
# - TypeScript errors
# - Missing environment variables
# - Node version mismatch
```

### Issue: Video upload stuck at "Processing"

**Cause:** Backend Lambda function error or timeout

**Fix:**
1. Check backend logs (see backend README)
2. Verify AWS credentials and permissions
3. Check S3 bucket access

### Issue: Chat not responding

**Cause:** Bedrock Agent not configured or API error

**Fix:**
1. Verify `BEDROCK_AGENT_ID` in backend `.env`
2. Check backend logs for errors
3. Test backend `/chat` endpoint directly:
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "test", "session_id": "test123"}'
   ```

## 📊 Performance Optimization

### Production Build Optimizations

The build process automatically:
- Minifies JavaScript and CSS
- Optimizes images
- Generates source maps
- Enables code splitting

### Amplify Optimizations

Amplify automatically provides:
- **CDN distribution** via CloudFront
- **HTTPS** by default
- **Automatic caching** for static assets
- **Gzip compression**

## 🔒 Security Considerations

### Environment Variables

- Never commit `.env.local` or `.env.production` to Git
- Use Amplify environment variables for sensitive data
- Backend URL should use HTTPS in production

### CORS

- Configure backend to allow only your Amplify domain
- Don't use `allow_origins=["*"]` in production

### API Security

- Backend should validate all requests
- Use authentication tokens (if implemented)
- Rate limiting on backend endpoints

## 📚 Additional Resources

- [React Documentation](https://react.dev/)
- [Material-UI Documentation](https://mui.com/)
- [AWS Amplify Documentation](https://docs.amplify.aws/)
- [TypeScript Documentation](https://www.typescriptlang.org/)

## 🆘 Support

**Common Issues:**
- Backend connection errors → Check backend README
- Upload failures → Verify S3 permissions
- Chat not working → Check Bedrock Agent configuration

**Logs:**
- Browser console: `F12` → Console tab
- Network requests: `F12` → Network tab
- Backend logs: See backend README

## 📝 Development Workflow

1. **Make changes** to components/hooks
2. **Test locally** with `npm start`
3. **Build** with `npm run build`
4. **Commit** changes to Git
5. **Push** to trigger Amplify deployment
6. **Verify** deployment in Amplify Console

## 🎉 Next Steps

After frontend deployment:
1. ✅ Test video upload functionality
2. ✅ Verify chat interface works
3. ✅ Test on mobile devices
4. ✅ Set up custom domain (optional)
5. ✅ Configure monitoring and alerts

---

**Frontend Status**: Ready to deploy! 🚀

For backend setup and deployment, see [Backend README](../backend/README.md)

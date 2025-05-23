# Deployment Guide for Jonathan's Memory

## Environment Variables Required

Before deploying to Render, you'll need to gather the following credentials:

### 1. Supabase Configuration
- **SUPABASE_URL**: Your Supabase project URL (e.g., https://xxxxx.supabase.co)
- **SUPABASE_SERVICE_KEY**: Service role key from Supabase Dashboard > Settings > API
- **NEXT_PUBLIC_SUPABASE_URL**: Same as SUPABASE_URL (for frontend)
- **NEXT_PUBLIC_SUPABASE_ANON_KEY**: Anon/public key from Supabase Dashboard > Settings > API

### 2. OpenAI Configuration
- **OPENAI_API_KEY**: Your OpenAI API key from https://platform.openai.com/api-keys

### 3. Qdrant Configuration (Choose one option)

#### Option A: Qdrant Cloud (Recommended for production)
1. Create a free cluster at https://cloud.qdrant.io
2. Get your credentials:
   - **QDRANT_HOST**: Your cluster URL (e.g., xxxxx.cloud.qdrant.io)
   - **QDRANT_API_KEY**: Your cluster API key

#### Option B: Use Render's Qdrant Service (Alternative)
If you don't want to use Qdrant Cloud, you can add a Qdrant service to your render.yaml:

```yaml
  # Add this to your services section in render.yaml
  - type: pserv
    name: qdrant
    runtime: docker
    plan: starter
    dockerContext: .
    dockerfilePath: ./qdrant.Dockerfile
    disk:
      name: qdrant-storage
      mountPath: /qdrant/storage
      sizeGB: 10
    envVars:
      - key: QDRANT__SERVICE__HTTP_PORT
        value: "6333"
```

And create a `qdrant.Dockerfile`:
```dockerfile
FROM qdrant/qdrant:latest
```

Then set:
- **QDRANT_HOST**: qdrant (internal service name)
- **QDRANT_API_KEY**: (leave empty for internal connection)

## Deployment Steps

1. **Via Render Dashboard:**
   - Go to https://dashboard.render.com
   - Click "New > Blueprint"
   - Connect your repository
   - Fill in the environment variables when prompted
   - Click "Apply"

2. **Monitor Deployment:**
   - Backend API: Will be available at `https://jonathans-memory-api.onrender.com`
   - Frontend UI: Will be available at `https://jonathans-memory-ui.onrender.com`
   - Database: PostgreSQL will be provisioned automatically

3. **Post-Deployment:**
   - The frontend will automatically use the backend API URL
   - Test the health endpoint: `https://jonathans-memory-api.onrender.com/health`
   - Access your UI at the frontend URL
   - Users can install the MCP integration using:
     ```bash
     npx install-mcp i https://jonathans-memory-api.onrender.com/mcp/[client]/sse/[user-id] --client [client]
     ```

## Important Notes

- The first deployment may take 10-15 minutes
- Free tier services may spin down after inactivity
- Make sure your Supabase database has the proper tables/schema set up
- Render will automatically set up SSL certificates for your domains

## Troubleshooting

If you encounter issues:
1. Check the service logs in Render Dashboard
2. Verify all environment variables are set correctly
3. Ensure your Supabase project is properly configured
4. Check that Qdrant connection is working (if using external Qdrant)

## Costs

With the current configuration:
- Backend API: $7/month (Starter tier)
- Frontend UI: $7/month (Starter tier)  
- PostgreSQL: $7/month (Starter tier)
- Total: ~$21/month

You can start with free tiers for testing, but they have limitations (services sleep after 15 minutes of inactivity). 
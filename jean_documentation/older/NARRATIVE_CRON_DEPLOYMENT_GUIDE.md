# Jean Memory - Narrative Caching & Weekly Regeneration Deployment Guide

## 🎯 **Overview**

This guide explains how to deploy and manage the automatic narrative caching system that:
1. **Backfills narratives** for existing users with 5+ memories
2. **Runs weekly regeneration** to keep narratives fresh
3. **Provides instant responses** for new conversations

---

## 🚀 **Step 1: Deploy Updated Render Configuration**

### **Update render.yaml with Cron Job**

The `render.yaml` has been updated to include a weekly cron job. Deploy this configuration:

```bash
# 1. Commit the updated render.yaml
git add render.yaml
git commit -m "Add weekly narrative regeneration cron job"
git push origin main

# 2. Deploy via Render Dashboard or CLI
render blueprint launch
```

### **Cron Job Configuration Details**

The cron job runs with these specifications:
- **Schedule**: `"0 2 * * 0"` (Every Sunday at 2 AM UTC)
- **Region**: Virginia (same as main services)
- **Plan**: Starter ($7/month)
- **Command**: `python -m scripts.utils.backfill_user_narratives`

---

## 🧪 **Step 2: Test the System Locally**

Before deploying to production, test the system thoroughly:

### **Run the Test Suite**

```bash
# Navigate to project root
cd /path/to/mem0

# Run comprehensive tests
python scripts/test_narrative_backfill.py
```

**Expected Output:**
```
🧪 JEAN MEMORY NARRATIVE BACKFILL TEST SUITE
============================================================
🔍 Testing database connection...
✅ Database connection successful. Found 4 users.
🔍 Testing Gemini API connection...
✅ Gemini API connection successful. Response length: 45
🔍 Finding test user with sufficient memories...
✅ Found test user: Jonathan Politzki (66d3d5d1-fc48-44a7-bbc0-1efa2e164fad) with 8 memories
🔍 Testing narrative generation for user 66d3d5d1-fc48-44a7-bbc0-1efa2e164fad...
✅ Narrative generation successful (duration: 15.42s, length: 1247 chars)
✅ Database save successful
🔍 Testing narrative retrieval for user 66d3d5d1-fc48-44a7-bbc0-1efa2e164fad...
✅ Narrative found in database (length: 1247 chars)

📊 TEST RESULTS SUMMARY
============================================================
  DATABASE: ✅ PASS
  GEMINI_API: ✅ PASS
  GENERATION: ✅ PASS
  RETRIEVAL: ✅ PASS

🎯 OVERALL RESULT: 4/4 tests passed
🎉 ALL TESTS PASSED - System ready for cron job deployment!
```

### **Manual Backfill Test (Optional)**

```bash
# Run manual backfill for immediate population
python -m scripts.utils.backfill_user_narratives
```

---

## 🔧 **Step 3: Deploy to Production**

### **Environment Variables Required**

Ensure these environment variables are set in Render Dashboard:

**Required for Cron Job:**
- `DATABASE_URL` - Supabase PostgreSQL connection
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_KEY` - Service role key
- `GEMINI_API_KEY` - Google Gemini API key
- `OPENAI_API_KEY` - OpenAI API key (for embeddings)
- `QDRANT_HOST` - Qdrant Cloud endpoint
- `QDRANT_API_KEY` - Qdrant Cloud API key

### **Deploy Steps**

1. **Commit and Push Updated Code**
   ```bash
   git add .
   git commit -m "Deploy narrative caching system with weekly cron job"
   git push origin main
   ```

2. **Deploy via Render**
   - Option A: Automatic deployment (if auto-deploy enabled)
   - Option B: Manual deployment via Render Dashboard
   - Option C: Using Render CLI: `render blueprint launch`

3. **Monitor Deployment**
   - Backend API: Should deploy with enhanced background task logging
   - Cron Job: New service `narrative-backfill-weekly` will be created

---

## 📊 **Step 4: Monitor and Validate**

### **Check Cron Job Status**

1. **Render Dashboard**
   - Go to Services → `narrative-backfill-weekly`
   - Check "Recent Deployments" and "Logs"

2. **Verify Schedule**
   - Cron job should show "Next run: Sunday at 02:00 UTC"

### **Monitor Background Tasks (Real-time)**

Check the main API logs for background task execution:

```bash
# Watch live logs for background task debugging
render logs --follow jean-memory-api-virginia
```

**Expected Log Patterns:**
```
INFO     🔄 [Smart Cache] Started background narrative generation for user 66d3d5d1-fc48-44a7-bbc0-1efa2e164fad
INFO     🤖 [Background Task] Starting narrative generation for user 66d3d5d1-fc48-44a7-bbc0-1efa2e164fad
INFO     ✅ [Background Task] Gemini API successful for user 66d3d5d1-fc48-44a7-bbc0-1efa2e164fad (duration: 12.3s)
INFO     ✅ [Background Task] Database save completed for user 66d3d5d1-fc48-44a7-bbc0-1efa2e164fad
INFO     🎉 [Background Task] COMPLETED successfully for user 66d3d5d1-fc48-44a7-bbc0-1efa2e164fad
```

### **Database Validation**

Check that narratives are being created:

```sql
-- Connect to Supabase SQL Editor
SELECT 
    u.name,
    u.user_id,
    un.generated_at,
    LENGTH(un.narrative_content) as narrative_length,
    un.version
FROM user_narratives un
JOIN users u ON u.id = un.user_id
ORDER BY un.generated_at DESC;
```

---

## 🛠️ **Step 5: Troubleshooting Common Issues**

### **Issue 1: Background Tasks Not Completing**

**Symptoms:**
- Logs show "Started background narrative generation" but no completion messages
- `user_narratives` table remains empty

**Debugging Steps:**
1. Check enhanced background task logs in API service
2. Verify Gemini API key is correctly set
3. Check database connection permissions
4. Look for timeout issues in long-running tasks

**Solutions:**
```bash
# Check API service logs with focus on background tasks
render logs jean-memory-api-virginia | grep "Background Task"

# Manually run backfill to test outside background tasks
python -m scripts.utils.backfill_user_narratives
```

### **Issue 2: Cron Job Fails to Start**

**Symptoms:**
- Cron service shows "Failed" status
- No logs in cron job service

**Debugging Steps:**
1. Check cron job logs in Render Dashboard
2. Verify all environment variables are set
3. Check build command execution

**Solutions:**
```bash
# Check cron job specific logs
render logs narrative-backfill-weekly

# Test the command locally first
python -m scripts.utils.backfill_user_narratives
```

### **Issue 3: Database Connection Issues**

**Symptoms:**
- "Database connection failed" errors
- SSL/authentication errors

**Solutions:**
1. Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/db`
2. Check Supabase connection limits
3. Ensure service key has necessary permissions

---

## 📈 **Step 6: Performance Monitoring**

### **Key Metrics to Watch**

1. **Success Rate**
   - Target: >90% successful narrative generations
   - Monitor via cron job logs and database counts

2. **Response Times**
   - Narrative generation: 10-30 seconds typical
   - Database saves: <1 second typical

3. **API Usage**
   - Gemini API calls: ~1 per user per week
   - Cost estimate: $0.01-0.05 per user per week

### **Weekly Cron Job Monitoring**

**Expected Weekly Output:**
```
🎉 JEAN MEMORY - USER NARRATIVE BACKFILL PROCESS COMPLETE
📊 FINAL RESULTS:
   • Total users processed: 25
   • ✅ Successful: 23
   • ❌ Failed: 1
   • ⚠️ Skipped: 1
   • 💾 Success rate: 92.0%
```

---

## 🔄 **Step 7: Manual Operations**

### **Force Immediate Backfill**

```bash
# Run manual backfill (one-time)
render run python -m scripts.utils.backfill_user_narratives --service narrative-backfill-weekly
```

### **Test Single User**

```bash
# Test narrative generation for specific user
python scripts/test_narrative_backfill.py
```

### **Clear All Narratives (Reset)**

```sql
-- ⚠️ DANGER: This will delete all cached narratives
-- Only use for testing or emergency reset
DELETE FROM user_narratives;
```

---

## 💰 **Cost Analysis**

### **Additional Monthly Costs**

- **Cron Job Service**: $7/month (Render Starter plan)
- **Gemini API Usage**: ~$5-15/month (depends on user count)
- **Total Additional Cost**: ~$12-22/month

### **Cost Benefits**

- **Reduced API calls**: 90% reduction in on-demand generation
- **Improved user experience**: Instant responses vs 15-20s delays
- **Scalability**: System handles growth automatically

---

## ✅ **Step 8: Success Validation Checklist**

- [ ] Render deployment successful with cron job service
- [ ] Test suite passes locally and in production
- [ ] Background tasks completing with full logging
- [ ] Database contains generated narratives
- [ ] Cron job scheduled and ready for weekly execution
- [ ] New conversations use cached narratives (< 1s response)
- [ ] Monitoring and alerting configured

---

## 🎯 **Expected Production Behavior**

### **For New Conversations:**
1. User starts new Claude conversation
2. System checks `user_narratives` table (~1ms)
3. **Cache Hit**: Returns cached narrative instantly
4. **Cache Miss**: Falls back to deep analysis + starts background generation
5. Next conversation will be instant

### **Weekly Maintenance:**
1. Every Sunday 2 AM UTC: Cron job runs automatically
2. Processes all users with stale/missing narratives
3. Updates existing narratives with fresh content
4. Logs completion status and metrics

### **Operational Excellence:**
- Zero downtime deployments
- Graceful fallbacks if caching fails
- Comprehensive logging for debugging
- Scalable architecture for user growth

---

**🎉 Deployment Complete! Your narrative caching system is now running in production with automatic weekly regeneration.** 
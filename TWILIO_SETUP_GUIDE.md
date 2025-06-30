# Twilio SMS Setup Guide - Jean Memory

## 🎉 Congratulations! Your A2P 10DLC Campaign is Verified!

Your Twilio campaign is approved and ready to go. Here's how to complete the setup:

**Campaign Details:**
- Campaign SID: `CMa0bccc44287968bb1a25de800985512b`
- Phone Number: `+13648889368`
- Status: ✅ **Verified**
- Use Case: Low Volume Mixed

## Step 1: Set Environment Variables in Render

1. Go to your [Render Dashboard](https://dashboard.render.com)
2. Find your `jean-memory-api-virginia` service
3. Go to **Environment** tab
4. Add/Update these variables:

```
TWILIO_ACCOUNT_SID = [Your Account SID from Twilio Console]
TWILIO_AUTH_TOKEN = [Your Auth Token from Twilio Console] 
```

**Note:** The phone number `+13648889368` is already configured in your `render.yaml`

**To find your Twilio credentials:**
- Go to [Twilio Console](https://console.twilio.com)
- Your Account SID and Auth Token are on the main dashboard

## Step 2: Deploy Updated Configuration

After updating the environment variables, your service will automatically redeploy with the new Twilio configuration.

## Step 3: Test the SMS Integration

### Option A: Test via Your Dashboard
1. Go to `https://jean-memory-ui-virginia.onrender.com/dashboard-new`
2. Find the SMS integration card
3. Click "Connect" and enter your phone number
4. Complete the verification flow

### Option B: Test the Webhook Directly

The webhook URL is already configured in Twilio:
```
https://jean-memory-api-virginia.onrender.com/webhooks/sms
```

You can test by sending an SMS to `+13648889368` from your verified phone number.

## Step 4: SMS Commands You Can Use

Once your phone is verified, you can text the number with commands like:

- `"Remember to buy groceries this weekend"` → Adds memory
- `"What should I buy?"` → Searches memories  
- `"Show my recent memories"` → Lists recent memories
- `"help"` → Shows available commands

## Troubleshooting

### Check Service Logs
1. Go to Render Dashboard → `jean-memory-api-virginia` → Logs
2. Look for SMS-related log entries
3. Check for any Twilio errors

### Common Issues

**SMS not delivered:**
- Verify your phone number is in E.164 format (+1234567890)
- Check that you're texting FROM a verified number TO the Twilio number
- Look for delivery errors in Twilio Console → Messaging → Logs

**Webhook errors:**
- Check that the webhook URL is responding: `https://jean-memory-api-virginia.onrender.com/health`
- Verify Twilio signature validation is working
- Check service logs for webhook processing errors

### Test Webhook Health

```bash
curl https://jean-memory-api-virginia.onrender.com/health
```

Should return `{"status": "healthy"}`

## Features Enabled

With SMS integration, your users can:

✅ **Add memories** via text message  
✅ **Search memories** with natural language  
✅ **List recent memories**  
✅ **Get help** with available commands  
✅ **Conversation context** - SMS remembers recent exchanges  
✅ **Pro/Enterprise features** - Rate limiting and premium access  

## Security Features

✅ **Twilio signature validation** - Prevents spoofed messages  
✅ **Phone verification required** - Users must verify their number  
✅ **Pro subscription gating** - SMS is a premium feature  
✅ **Rate limiting** - 50/day for Pro, 200/day for Enterprise  

## Next Steps

1. **Set the environment variables** in Render
2. **Test the integration** with your own phone number
3. **Monitor the logs** to ensure everything is working
4. **Enable SMS integration** in your dashboard UI for users

Your Twilio integration is now ready for production! 🚀 
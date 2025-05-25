#!/usr/bin/env python3
"""
Test script for Twitter integration with Apify
"""
import asyncio
import sys
import os
import logging
from app.integrations.twitter_service import TwitterService

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_twitter_fetch():
    """Test fetching tweets"""
    service = TwitterService()
    
    # Test username
    username = sys.argv[1] if len(sys.argv) > 1 else "elonmusk"
    
    print(f"Testing Twitter integration for @{username}...")
    
    # Check if APIFY_TOKEN is set
    apify_token = os.getenv('APIFY_TOKEN')
    if apify_token:
        print(f"✅ APIFY_TOKEN found: {apify_token[:10]}...")
    else:
        print("⚠️  No APIFY_TOKEN found, will use demo tweets")
    
    try:
        # Test Apify integration
        tweets = await service.fetch_tweets_apify(username, max_tweets=5)
        
        print(f"\nFound {len(tweets)} tweets:")
        for i, tweet in enumerate(tweets, 1):
            print(f"\n{i}. {tweet['text'][:100]}...")
            if tweet.get('created_at'):
                print(f"   Date: {tweet['created_at']}")
            print(f"   Source: {tweet.get('source', 'unknown')}")
            if tweet.get('url'):
                print(f"   URL: {tweet['url']}")
        
        # Test formatting
        memories = service.format_tweets_for_memory(tweets, username)
        print(f"\n\nFormatted as {len(memories)} memories:")
        for i, memory in enumerate(memories[:3], 1):
            print(f"{i}. {memory[:100]}...")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_twitter_fetch())
    sys.exit(0 if success else 1) 
#!/usr/bin/env python3
"""
Test script for Twitter integration
"""
import asyncio
import sys
from app.integrations.twitter_service import TwitterService

async def test_twitter_fetch():
    """Test fetching tweets"""
    service = TwitterService()
    
    # Test username
    username = sys.argv[1] if len(sys.argv) > 1 else "elonmusk"
    
    print(f"Testing Twitter integration for @{username}...")
    
    try:
        tweets = await service.fetch_tweets_nitter(username, max_tweets=5)
        
        print(f"\nFound {len(tweets)} tweets:")
        for i, tweet in enumerate(tweets, 1):
            print(f"\n{i}. {tweet['text'][:100]}...")
            if tweet.get('created_at'):
                print(f"   Date: {tweet['created_at']}")
        
        # Test formatting
        memories = service.format_tweets_for_memory(tweets, username)
        print(f"\n\nFormatted as {len(memories)} memories")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_twitter_fetch())
    sys.exit(0 if success else 1) 
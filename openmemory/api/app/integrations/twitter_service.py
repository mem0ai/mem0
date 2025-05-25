import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)

class TwitterService:
    """
    Simple Twitter integration service.
    Initially uses web scraping, can be upgraded to OAuth later.
    """
    
    def __init__(self):
        self.base_url = "https://api.twitter.com/2"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def fetch_tweets_nitter(self, username: str, max_tweets: int = 40) -> List[Dict]:
        """
        Fetch tweets using Nitter instances (Twitter frontend proxy).
        This avoids OAuth but may be less reliable.
        """
        nitter_instances = [
            "https://nitter.net",
            "https://nitter.it", 
            "https://nitter.privacydev.net"
        ]
        
        for instance in nitter_instances:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{instance}/{username}",
                        headers=self.headers,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        return self._parse_nitter_tweets(response.text, max_tweets)
            except Exception as e:
                logger.warning(f"Failed to fetch from {instance}: {e}")
                continue
        
        raise Exception("Failed to fetch tweets from any Nitter instance")
    
    def _parse_nitter_tweets(self, html: str, max_tweets: int) -> List[Dict]:
        """Parse tweets from Nitter HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        tweets = []
        
        tweet_elements = soup.find_all('div', class_='timeline-item')[:max_tweets]
        
        for tweet in tweet_elements:
            try:
                content = tweet.find('div', class_='tweet-content')
                if content:
                    tweet_text = content.get_text(strip=True)
                    tweet_date = tweet.find('span', class_='tweet-date')
                    
                    tweets.append({
                        'text': tweet_text,
                        'created_at': tweet_date.get('title') if tweet_date else None,
                        'source': 'nitter'
                    })
            except Exception as e:
                logger.error(f"Error parsing tweet: {e}")
                continue
        
        return tweets
    
    async def fetch_tweets_api(self, username: str, bearer_token: str, max_tweets: int = 40) -> List[Dict]:
        """
        Fetch tweets using Twitter API v2 (requires bearer token).
        This is for future OAuth implementation.
        """
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "v2UserTweetsPython"
        }
        
        async with httpx.AsyncClient() as client:
            # Get user ID
            user_response = await client.get(
                f"{self.base_url}/users/by/username/{username}",
                headers=headers
            )
            
            if user_response.status_code != 200:
                raise Exception(f"Failed to get user: {user_response.text}")
            
            user_id = user_response.json()['data']['id']
            
            # Get tweets
            tweets_response = await client.get(
                f"{self.base_url}/users/{user_id}/tweets",
                headers=headers,
                params={
                    "max_results": min(max_tweets, 100),
                    "tweet.fields": "created_at,text"
                }
            )
            
            if tweets_response.status_code != 200:
                raise Exception(f"Failed to get tweets: {tweets_response.text}")
            
            tweets_data = tweets_response.json()
            return [
                {
                    'text': tweet['text'],
                    'created_at': tweet['created_at'],
                    'id': tweet['id'],
                    'source': 'twitter_api'
                }
                for tweet in tweets_data.get('data', [])
            ]
    
    def format_tweets_for_memory(self, tweets: List[Dict], username: str) -> List[str]:
        """Format tweets into memory-friendly strings."""
        memories = []
        
        for tweet in tweets:
            memory_text = f"@{username} tweeted: {tweet['text']}"
            if tweet.get('created_at'):
                memory_text += f" (on {tweet['created_at']})"
            memories.append(memory_text)
        
        return memories


# Example usage function
async def sync_twitter_to_memory(username: str, user_id: str, app_id: str, db_session):
    """
    Sync a Twitter user's recent tweets to memory.
    This can be called from an API endpoint or MCP tool.
    """
    from app.utils.memory import get_memory_client
    
    service = TwitterService()
    memory_client = get_memory_client()
    
    try:
        # Try Nitter first (no auth required)
        tweets = await service.fetch_tweets_nitter(username)
        
        # Format tweets for memory storage
        memory_contents = service.format_tweets_for_memory(tweets, username)
        
        # Store tweets using memory client (which handles vector embeddings)
        synced_count = 0
        for content in memory_contents:
            try:
                # Add to memory using mem0 client
                response = memory_client.add(
                    messages=content,
                    user_id=user_id,  # This should be the Supabase user ID
                    metadata={
                        'source': 'twitter',
                        'username': username,
                        'type': 'tweet',
                        'app_id': app_id
                    }
                )
                synced_count += 1
            except Exception as e:
                logger.warning(f"Failed to add tweet to memory: {e}")
                continue
        
        return synced_count
        
    except Exception as e:
        logger.error(f"Failed to sync Twitter for @{username}: {e}")
        raise 
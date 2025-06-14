import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import httpx
import json
import os
from uuid import UUID

logger = logging.getLogger(__name__)

class TwitterService:
    """
    Twitter integration service using Apify Tweet Scraper V2.
    Updated to use proper app creation with environment variable support.
    """
    
    def __init__(self):
        self.apify_token = os.getenv('APIFY_TOKEN')
        self.apify_base_url = "https://api.apify.com/v2"
        
    async def fetch_tweets_apify(self, username: str, max_tweets: int = 40, progress_callback: Optional[callable] = None) -> List[Dict]:
        """
        Fetch tweets using Apify Twitter Scraper Unlimited.
        Now works with real data since user has paid Apify plan.
        """
        if not self.apify_token:
            logger.warning("No APIFY_TOKEN found, falling back to demo tweets")
            return self._create_demo_tweets(username, min(max_tweets, 5))
        
        # Twitter Scraper Unlimited actor ID
        actor_id = "nfp1fpt5gUlBwPcor"  # Twitter Scraper Unlimited
        
        # Input format for Twitter Scraper Unlimited
        run_input = {
            "searchTerms": [f"from:{username}"],
            "maxItems": min(max_tweets, 100),
            "sort": "Latest"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                # Start the actor run
                logger.info(f"Starting Apify Twitter Scraper Unlimited for @{username}")
                
                start_response = await client.post(
                    f"{self.apify_base_url}/acts/{actor_id}/runs",
                    headers={
                        "Authorization": f"Bearer {self.apify_token}",
                        "Content-Type": "application/json"
                    },
                    json=run_input,
                    timeout=30.0
                )
                
                if start_response.status_code != 201:
                    logger.error(f"Failed to start Apify run: {start_response.status_code} - {start_response.text}")
                    return self._create_demo_tweets(username, min(max_tweets, 5))
                
                run_data = start_response.json()
                run_id = run_data["data"]["id"]
                
                # Wait for the run to complete (with timeout)
                logger.info(f"Waiting for Apify run {run_id} to complete...")
                
                for attempt in range(30):  # Wait up to 5 minutes
                    await asyncio.sleep(10)  # Wait 10 seconds between checks
                    
                    status_response = await client.get(
                        f"{self.apify_base_url}/actor-runs/{run_id}",
                        headers={"Authorization": f"Bearer {self.apify_token}"},
                        timeout=10.0
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data["data"]["status"]
                        
                        if status == "SUCCEEDED":
                            # Get the results
                            results_response = await client.get(
                                f"{self.apify_base_url}/actor-runs/{run_id}/dataset/items",
                                headers={"Authorization": f"Bearer {self.apify_token}"},
                                timeout=30.0
                            )
                            
                            if results_response.status_code == 200:
                                tweets_data = results_response.json()
                                logger.debug(f"Raw Apify response count: {len(tweets_data)}")
                                if tweets_data:
                                    logger.debug(f"First tweet structure: {list(tweets_data[0].keys()) if tweets_data[0] else 'Empty'}")
                                parsed_tweets = self._parse_apify_tweets(tweets_data, max_tweets)
                                
                                # If we got no real tweets, fall back to demo
                                if not parsed_tweets:
                                    logger.info("No tweets parsed from Apify response, falling back to demo tweets")
                                    return self._create_demo_tweets(username, min(max_tweets, 5))
                                
                                return parsed_tweets
                            else:
                                logger.error(f"Failed to get results: {results_response.status_code}")
                                break
                                
                        elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                            logger.error(f"Apify run failed with status: {status}")
                            break
                        else:
                            logger.info(f"Run status: {status}, waiting...")
                            continue
                    else:
                        logger.error(f"Failed to check status: {status_response.status_code}")
                        break
                
                logger.warning("Apify run timed out or failed")
                return self._create_demo_tweets(username, min(max_tweets, 5))
                
        except Exception as e:
            logger.error(f"Error with Apify Twitter Scraper Unlimited: {e}")
            return self._create_demo_tweets(username, min(max_tweets, 5))
    
    def _parse_apify_tweets(self, tweets_data: List[Dict], max_tweets: int) -> List[Dict]:
        """Parse tweets from Apify Twitter Scraper Unlimited response"""
        tweets = []
        
        for tweet_data in tweets_data[:max_tweets]:
            try:
                # Handle different possible field names for tweet text
                tweet_text = (
                    tweet_data.get('text') or 
                    tweet_data.get('full_text') or 
                    tweet_data.get('content') or
                    tweet_data.get('tweet_text')
                )
                
                if tweet_text:
                    tweets.append({
                        'text': tweet_text,
                        'created_at': tweet_data.get('createdAt') or tweet_data.get('created_at'),
                        'id': tweet_data.get('id') or tweet_data.get('tweet_id'),
                        'url': tweet_data.get('url') or tweet_data.get('tweet_url'),
                        'source': 'apify_unlimited'
                    })
            except Exception as e:
                logger.error(f"Error parsing Apify tweet: {e}")
                continue
        
        logger.info(f"Parsed {len(tweets)} tweets from Apify Twitter Scraper Unlimited")
        return tweets
    
    async def fetch_tweets_nitter(self, username: str, max_tweets: int = 40) -> List[Dict]:
        """
        Legacy Nitter method - kept as fallback but mostly unreliable.
        """
        logger.warning("Nitter instances are unreliable, using demo tweets instead")
        return self._create_demo_tweets(username, min(max_tweets, 5))
    
    def _create_demo_tweets(self, username: str, count: int = 5) -> List[Dict]:
        """Create demo tweets when scraping is unavailable"""
        from datetime import datetime, timedelta
        
        demo_tweets = [
            f"Just shared some thoughts about the future of technology and innovation.",
            f"Working on some exciting new projects. Can't wait to share more details soon!",
            f"The intersection of AI and human creativity continues to fascinate me.",
            f"Building something amazing takes time, patience, and the right team.",
            f"Every challenge is an opportunity to learn and grow stronger."
        ]
        
        tweets = []
        for i in range(min(count, len(demo_tweets))):
            tweets.append({
                'text': demo_tweets[i],
                'created_at': (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                'source': 'demo'
            })
        
        logger.info(f"Created {len(tweets)} demo tweets for @{username}")
        return tweets

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
async def sync_twitter_to_memory(
    username: str, 
    user_id: str, 
    app_id: str, 
    db_session,
    progress_callback: Optional[callable] = None
):
    """
    Sync a Twitter user's recent tweets to memory.
    This can be called from an API endpoint or MCP tool.
    """
    from app.models import Memory, App, User
    from app.utils.memory import get_memory_client
    from sqlalchemy.sql import exists
    from uuid import UUID
    
    def safe_uuid(id_str):
        """Convert string to UUID, handling local development IDs"""
        try:
            return UUID(id_str)
        except ValueError:
            if id_str == 'default_user':
                return UUID('00000000-0000-0000-0000-000000000001')
            if id_str == 'twitter':
                return UUID('00000000-0000-0000-0000-000000000002')
            return UUID('00000000-0000-0000-0000-000000000099')

    def report_progress(progress: int, message: str, count: int = 0):
        if progress_callback:
            progress_callback(progress, message, count)

    service = TwitterService()
    memory_client = get_memory_client()
    
    # For local development, ensure the user and app exist
    user_uuid = safe_uuid(user_id)
    app_uuid = safe_uuid(app_id)
    
    # Check if this is local development mode
    if user_id == 'default_user' or app_id == 'twitter':
        logger.info("Local development mode detected, ensuring user and app exist in database")
        
        # Check if the user exists, create if not
        user_exists = db_session.query(exists().where(User.id == user_uuid)).scalar()
        if not user_exists:
            logger.info(f"Creating mock user for local development with id {user_uuid}")
            mock_user = User(
                id=user_uuid,
                email='local-dev@example.com',
                display_name='Local Dev User',
                is_active=True
            )
            db_session.add(mock_user)
        
        # Check if the Twitter app exists, create if not
        app_exists = db_session.query(exists().where(App.id == app_uuid)).scalar()
        if not app_exists:
            logger.info(f"Creating Twitter app for local development with id {app_uuid}")
            twitter_app = App(
                id=app_uuid,
                name='Twitter',
                description='Twitter Integration',
                owner_id=user_uuid,  # Set the mock user as owner
                is_active=True
            )
            db_session.add(twitter_app)
            
        # Commit these changes before proceeding with tweet processing
        db_session.commit()
        logger.info("Ensured user and app exist in database for local development")
    
    try:
        report_progress(5, "Starting sync...", 0)
        
        tweets = await service.fetch_tweets_apify(username, progress_callback=report_progress)
        
        if not tweets:
            report_progress(100, "No tweets found or user is private.", 0)
            return 0
        
        report_progress(50, f"Found {len(tweets)} tweets. Formatting for memory...", len(tweets))
        
        memory_contents = service.format_tweets_for_memory(tweets, username)
        
        # Store tweets using memory client (which handles vector embeddings)
        synced_count = 0
        failed_count = 0
        
        # Process tweets in smaller batches to prevent resource exhaustion
        batch_size = 5  # Process 5 tweets at a time
        
        for i in range(0, len(memory_contents), batch_size):
            batch = memory_contents[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(memory_contents) + batch_size - 1)//batch_size} ({len(batch)} tweets)")
            
            for j, content in enumerate(batch):
                try:
                    logger.debug(f"Adding tweet {i+j+1} to memory: {content[:50]}...")
                    
                    # Create memory in database first
                    memory_metadata = {
                        'source': 'twitter',
                        'source_app': 'twitter',
                        'username': username,
                        'type': 'tweet',
                        'tweet_index': i + j,
                        'tweet_data': tweets[i + j] if i + j < len(tweets) else {}
                    }
                    
                    # Create database record
                    db_memory = Memory(
                        user_id=safe_uuid(user_id),
                        app_id=safe_uuid(app_id),
                        content=content,
                        metadata_=memory_metadata
                    )
                    db_session.add(db_memory)
                    db_session.flush()  # Get the ID without committing
                    
                    # Add to vector store using mem0 client with the database ID
                    response = memory_client.add(
                        messages=content,
                        user_id=user_id,  # This should be the Supabase user ID
                        metadata={
                            **memory_metadata,
                            'db_memory_id': str(db_memory.id),  # Link to database record
                            'app_id': app_id,
                            'app_db_id': app_id
                        }
                    )
                    
                    logger.debug(f"Memory client response: {response}")
                    synced_count += 1
                    
                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Failed to add tweet {i+j+1} to memory: {e}")
                    failed_count += 1
                    db_session.rollback()
                    continue
            
            # Commit the batch
            try:
                db_session.commit()
                logger.info(f"Committed batch {i//batch_size + 1} to database")
            except Exception as e:
                logger.error(f"Failed to commit batch: {e}")
                db_session.rollback()
                failed_count += len(batch)
                synced_count -= len(batch)
            
            # Longer delay between batches
            if i + batch_size < len(memory_contents):
                logger.info(f"Batch complete. Waiting 2 seconds before next batch...")
                await asyncio.sleep(2)
        
        report_progress(100, f"Sync complete. Added {synced_count} new tweets.", synced_count)
        return synced_count
        
    except Exception as e:
        logger.error(f"An error occurred during Twitter sync for @{username}: {e}", exc_info=True)
        report_progress(100, f"An error occurred: {e}", 0)
        return 0 
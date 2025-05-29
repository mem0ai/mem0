"""
Substack scraper for OpenMemory.
Based on proven implementation from jonathan-politzki/Substack-Analysis
"""
import logging
from datetime import datetime
from typing import List, Optional
import re

import feedparser
import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass
from dateutil import parser

logger = logging.getLogger(__name__)


@dataclass
class Post:
    title: str
    url: str
    content: str
    date: Optional[datetime]
    subtitle: Optional[str] = ""


class BaseScraper:
    def __init__(self, url: str, max_posts: int = 100):
        self.url = url
        self.max_posts = max_posts

    async def scrape(self) -> List[Post]:
        raise NotImplementedError


class SubstackScraper(BaseScraper):
    """Scraper for Substack blogs."""
    
    async def scrape(self) -> List[Post]:
        """
        Scrape posts from a Substack blog.
        
        Returns:
            A list of Post objects with content and metadata
        """
        # Try multiple feed URL formats for robustness
        feed_urls = [
            f"{self.url}/feed",      # Primary format
            f"{self.url}/feed.xml",  # Alternative format
            f"{self.url}/rss",       # Some blogs use this
            f"{self.url}/atom.xml",  # Atom format
        ]
        
        for feed_url in feed_urls:
            try:
                logger.info(f"Fetching Substack posts from: {feed_url}")
                # Note: verify=False is needed for SSL certificate issues on some systems
                async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
                    response = await client.get(feed_url)
                    response.raise_for_status()
                    feed = feedparser.parse(response.text)
                    logger.info(f"Number of entries in feed: {len(feed.entries)}")
                    
                    # If we found entries, break out of the loop
                    if len(feed.entries) > 0:
                        logger.info(f"Successfully found feed at: {feed_url}")
                        break
                    else:
                        logger.warning(f"Feed at {feed_url} exists but has no entries")
                        
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error for {feed_url}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error fetching feed {feed_url}: {str(e)}")
                continue
        else:
            # If we've tried all URLs and none worked
            logger.error(f"No working RSS feed found for {self.url}")
            return []

        # If we have no entries after trying all feeds, return empty
        if len(feed.entries) == 0:
            logger.error(f"All RSS feeds for {self.url} were empty")
            return []

        posts = []
        for entry in feed.entries[:self.max_posts]:
            try:
                content = entry.content[0].value if 'content' in entry else entry.summary
                soup = BeautifulSoup(content, 'html.parser')
                cleaned_text = self._clean_content(soup.get_text(separator=' ', strip=True))
                
                # Parse date
                pub_date = None
                if hasattr(entry, 'published'):
                    try:
                        # Handle timezone-aware parsing
                        pub_date = parser.parse(entry.published)
                    except Exception as e:
                        logger.warning(f"Could not parse date: {entry.published} - {e}")
                
                post = Post(
                    title=self._clean_content(entry.title),
                    url=entry.link,
                    content=cleaned_text,
                    date=pub_date,
                    subtitle="",
                )
                posts.append(post)
            except Exception as e:
                logger.error(f"Error processing Substack post {entry.get('link', 'unknown')}: {str(e)}")

        logger.info(f"Scraped {len(posts)} posts from Substack")
        return posts
        
    @staticmethod
    def _clean_content(content: str) -> str:
        """Remove extra whitespace and normalize text."""
        # Remove extra whitespace and newlines
        content = re.sub(r'\s+', ' ', content).strip()
        return content 
"""
Background Sync Service for OpenMemory
Handles CRON jobs and manual refresh operations for integrations like Substack and Twitter.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import SessionLocal
from app.models import App, User
from app.models import get_current_utc_time

logger = logging.getLogger(__name__)

class BackgroundSyncService:
    """
    Service to handle background syncing of integration data.
    Replaces real-time polling with efficient hourly CRON jobs.
    """

    def __init__(self):
        self.sync_intervals = {
            'substack': timedelta(hours=1),  # Sync every hour
            'twitter': timedelta(hours=1),   # Sync every hour
            'default': timedelta(hours=2)    # Default for other integrations
        }

    async def sync_all_integrations(self) -> Dict[str, int]:
        """
        CRON job: Sync all user integrations that are due for refresh.
        Called every hour by the scheduler.
        """
        logger.info("🔄 Starting hourly background sync for all integrations")
        
        sync_results = {
            'substack_synced': 0,
            'twitter_synced': 0,
            'errors': 0
        }
        
        db = SessionLocal()
        try:
            # Get all apps that need syncing
            apps_to_sync = self._get_apps_due_for_sync(db)
            
            for app in apps_to_sync:
                try:
                    await self._sync_app_data(db, app)
                    
                    if 'substack' in app.name.lower():
                        sync_results['substack_synced'] += 1
                    elif 'twitter' in app.name.lower() or 'x' in app.name.lower():
                        sync_results['twitter_synced'] += 1
                        
                except Exception as e:
                    logger.error(f"Failed to sync app {app.name} for user {app.owner_id}: {e}")
                    sync_results['errors'] += 1
                    
                    # Update app with error status
                    app.sync_status = "failed"
                    app.sync_error = str(e)
                    db.commit()
            
            logger.info(f"✅ Hourly sync completed: {sync_results}")
            return sync_results
            
        finally:
            db.close()

    async def manual_refresh_app(self, user_id: str, app_name: str) -> Dict[str, any]:
        """
        Manual refresh triggered by user clicking refresh button.
        Returns immediately with task status, sync happens in background.
        """
        logger.info(f"🔄 Manual refresh requested for {app_name} by user {user_id}")
        
        db = SessionLocal()
        try:
            # Find the app
            app = db.query(App).join(User).filter(
                and_(
                    User.user_id == user_id,
                    App.name.ilike(f"%{app_name}%")
                )
            ).first()
            
            if not app:
                return {
                    'success': False,
                    'error': f'App {app_name} not found for user'
                }
            
            # Check if already syncing
            if app.sync_status == "syncing":
                return {
                    'success': False,
                    'error': 'Sync already in progress',
                    'last_synced_at': app.last_synced_at.isoformat() if app.last_synced_at else None
                }
            
            # Mark as syncing
            app.sync_status = "syncing"
            app.sync_error = None
            db.commit()
            
            # Start background sync task
            asyncio.create_task(self._sync_app_data(db, app))
            
            return {
                'success': True,
                'message': f'Sync started for {app_name}',
                'last_synced_at': app.last_synced_at.isoformat() if app.last_synced_at else None,
                'sync_status': 'syncing'
            }
            
        except Exception as e:
            logger.error(f"Failed to start manual refresh for {app_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            db.close()

    def _get_apps_due_for_sync(self, db: Session) -> List[App]:
        """
        Get all apps that are due for syncing based on their sync intervals.
        """
        now = get_current_utc_time()
        apps_due = []
        
        # Get all active apps
        apps = db.query(App).filter(App.is_active == True).all()
        
        for app in apps:
            app_type = self._get_app_type(app.name)
            sync_interval = self.sync_intervals.get(app_type, self.sync_intervals['default'])
            
            # Check if sync is due
            if not app.last_synced_at:
                # Never synced before
                apps_due.append(app)
            else:
                time_since_sync = now - app.last_synced_at
                if time_since_sync >= sync_interval:
                    apps_due.append(app)
        
        logger.info(f"Found {len(apps_due)} apps due for sync")
        return apps_due

    async def _sync_app_data(self, db: Session, app: App) -> None:
        """
        Sync data for a specific app based on its type.
        """
        app_type = self._get_app_type(app.name)
        
        try:
            app.sync_status = "syncing"
            db.commit()
            
            if app_type == 'substack':
                await self._sync_substack_data(db, app)
            elif app_type == 'twitter':
                await self._sync_twitter_data(db, app)
            else:
                logger.warning(f"Unknown app type for sync: {app.name}")
                return
            
            # Mark as successful
            app.sync_status = "idle"
            app.sync_error = None
            app.last_synced_at = get_current_utc_time()
            db.commit()
            
            logger.info(f"✅ Successfully synced {app.name} for user {app.owner_id}")
            
        except Exception as e:
            logger.error(f"❌ Sync failed for {app.name}: {e}")
            app.sync_status = "failed"
            app.sync_error = str(e)
            db.commit()
            raise

    async def _sync_substack_data(self, db: Session, app: App) -> None:
        """
        Sync Substack data for the app.
        """
        logger.info(f"Syncing Substack data for app {app.name}")
        
        # Get the Substack URL from app metadata
        substack_url = app.metadata_.get('substack_url') if app.metadata_ else None
        if not substack_url:
            raise ValueError("No Substack URL configured for this app")
        
        # Import here to avoid circular imports
        from app.services.substack_service import SubstackService
        
        substack_service = SubstackService()
        
        # Sync latest posts (limit to avoid overwhelming)
        result = await substack_service.sync_substack_posts(
            user_id=app.owner_id,
            substack_url=substack_url,
            max_posts=20,  # Reasonable limit for background sync
            app_id=app.id
        )
        
        # Update app metrics
        if result.get('synced_count'):
            app.total_memories_created += result['synced_count']
            
        logger.info(f"Substack sync completed: {result}")

    async def _sync_twitter_data(self, db: Session, app: App) -> None:
        """
        Sync Twitter/X data for the app.
        """
        logger.info(f"Syncing Twitter data for app {app.name}")
        
        # Get the Twitter username from app metadata
        twitter_username = app.metadata_.get('twitter_username') if app.metadata_ else None
        if not twitter_username:
            raise ValueError("No Twitter username configured for this app")
        
        # Import here to avoid circular imports
        from app.services.twitter_service import TwitterService
        
        twitter_service = TwitterService()
        
        # Sync latest tweets
        result = await twitter_service.sync_tweets(
            user_id=app.owner_id,
            username=twitter_username,
            max_posts=40,  # Reasonable limit for background sync
            app_id=app.id
        )
        
        # Update app metrics
        if result.get('synced_count'):
            app.total_memories_created += result['synced_count']
            
        logger.info(f"Twitter sync completed: {result}")

    def _get_app_type(self, app_name: str) -> str:
        """
        Determine app type from app name.
        """
        name_lower = app_name.lower()
        
        if 'substack' in name_lower:
            return 'substack'
        elif 'twitter' in name_lower or 'x' == name_lower:
            return 'twitter'
        else:
            return 'unknown'

    async def get_app_sync_status(self, user_id: str, app_name: str) -> Dict[str, any]:
        """
        Get current sync status for an app.
        """
        db = SessionLocal()
        try:
            app = db.query(App).join(User).filter(
                and_(
                    User.user_id == user_id,
                    App.name.ilike(f"%{app_name}%")
                )
            ).first()
            
            if not app:
                return {
                    'found': False,
                    'error': f'App {app_name} not found'
                }
            
            return {
                'found': True,
                'sync_status': app.sync_status,
                'last_synced_at': app.last_synced_at.isoformat() if app.last_synced_at else None,
                'sync_error': app.sync_error,
                'total_memories_created': app.total_memories_created,
                'total_memories_accessed': app.total_memories_accessed
            }
            
        finally:
            db.close()

    async def refresh_all_user_integrations(self, user_id: str) -> Dict[str, any]:
        """
        Refresh all integrations for a specific user.
        Used for dashboard refresh button and session-based auto-refresh.
        """
        logger.info(f"🔄 Refreshing all integrations for user {user_id}")
        
        refresh_results = {
            'total_apps': 0,
            'successful_refreshes': 0,
            'failed_refreshes': 0,
            'skipped_apps': 0,
            'results': [],
            'errors': []
        }
        
        db = SessionLocal()
        try:
            # Get all active apps for this user
            user_apps = db.query(App).join(User).filter(
                and_(
                    User.user_id == user_id,
                    App.is_active == True
                )
            ).all()
            
            refresh_results['total_apps'] = len(user_apps)
            
            if not user_apps:
                logger.info(f"No apps found for user {user_id}")
                return {
                    **refresh_results,
                    'message': 'No integrations found to refresh'
                }
            
            # Refresh each app
            for app in user_apps:
                app_type = self._get_app_type(app.name)
                
                try:
                    # Skip if already syncing
                    if app.sync_status == "syncing":
                        refresh_results['skipped_apps'] += 1
                        refresh_results['results'].append({
                            'app_name': app.name,
                            'status': 'skipped',
                            'reason': 'Already syncing'
                        })
                        continue
                    
                    # Only refresh supported app types
                    if app_type not in ['substack', 'twitter']:
                        refresh_results['skipped_apps'] += 1
                        refresh_results['results'].append({
                            'app_name': app.name,
                            'status': 'skipped',
                            'reason': f'App type {app_type} not supported for auto-refresh'
                        })
                        continue
                    
                    # Start the refresh (async)
                    asyncio.create_task(self._sync_app_data(db, app))
                    
                    refresh_results['successful_refreshes'] += 1
                    refresh_results['results'].append({
                        'app_name': app.name,
                        'status': 'started',
                        'app_type': app_type
                    })
                    
                    logger.info(f"✅ Started refresh for {app.name} ({app_type})")
                    
                except Exception as e:
                    refresh_results['failed_refreshes'] += 1
                    refresh_results['errors'].append({
                        'app_name': app.name,
                        'error': str(e)
                    })
                    logger.error(f"❌ Failed to start refresh for {app.name}: {e}")
            
            # Create summary message
            message_parts = []
            if refresh_results['successful_refreshes'] > 0:
                message_parts.append(f"{refresh_results['successful_refreshes']} integrations refreshing")
            if refresh_results['skipped_apps'] > 0:
                message_parts.append(f"{refresh_results['skipped_apps']} skipped")
            if refresh_results['failed_refreshes'] > 0:
                message_parts.append(f"{refresh_results['failed_refreshes']} failed")
            
            refresh_results['message'] = ', '.join(message_parts) if message_parts else 'No actions taken'
            
            logger.info(f"✅ User refresh completed: {refresh_results['message']}")
            return refresh_results
            
        finally:
            db.close()


# Global service instance
background_sync_service = BackgroundSyncService() 
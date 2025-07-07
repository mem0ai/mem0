/**
 * Session utilities for managing refresh state and preventing duplicate API calls
 */

const SESSION_REFRESH_KEY = "openmemory-session-refreshed";
const LAST_REFRESH_KEY = "openmemory-last-refresh";

export const sessionUtils = {
  /**
   * Check if integrations have been refreshed in this session
   */
  hasSessionRefreshed(): boolean {
    if (typeof window === 'undefined') return false;
    return !!sessionStorage.getItem(SESSION_REFRESH_KEY);
  },

  /**
   * Mark session as having been refreshed
   */
  markSessionRefreshed(): void {
    if (typeof window === 'undefined') return;
    sessionStorage.setItem(SESSION_REFRESH_KEY, 'true');
    localStorage.setItem(LAST_REFRESH_KEY, new Date().toISOString());
  },

  /**
   * Get the last refresh timestamp
   */
  getLastRefreshTime(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(LAST_REFRESH_KEY);
  },

  /**
   * Clear session refresh state (useful for testing or manual reset)
   */
  clearSessionRefresh(): void {
    if (typeof window === 'undefined') return;
    sessionStorage.removeItem(SESSION_REFRESH_KEY);
  },

  /**
   * Format a timestamp for display
   */
  formatRefreshTime(timestamp: string | null): string {
    if (!timestamp) return "Never refreshed";
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
    
    if (diffInMinutes < 1) return "Just now";
    if (diffInMinutes < 60) return `${diffInMinutes} minutes ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)} hours ago`;
    return `${Math.floor(diffInMinutes / 1440)} days ago`;
  }
}; 
import { useState, useCallback, useRef } from 'react';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

interface CacheOptions {
  ttl?: number; // Time to live in milliseconds
  maxSize?: number; // Maximum number of entries
}

export function useExplorerCache<T>(options: CacheOptions = {}) {
  const { ttl = 15 * 60 * 1000, maxSize = 50 } = options; // Default 15 minutes TTL
  const cache = useRef<Map<string, CacheEntry<T>>>(new Map());
  const [cacheStats, setCacheStats] = useState({ hits: 0, misses: 0 });

  const isExpired = useCallback((entry: CacheEntry<T>): boolean => {
    return Date.now() - entry.timestamp > entry.ttl;
  }, []);

  const cleanup = useCallback(() => {
    const now = Date.now();
    const entries = Array.from(cache.current.entries());
    
    // Remove expired entries
    entries.forEach(([key, entry]) => {
      if (now - entry.timestamp > entry.ttl) {
        cache.current.delete(key);
      }
    });

    // If still over maxSize, remove oldest entries
    if (cache.current.size > maxSize) {
      const sortedEntries = entries
        .filter(([key]) => cache.current.has(key))
        .sort((a, b) => a[1].timestamp - b[1].timestamp);
      
      const toRemove = sortedEntries.slice(0, cache.current.size - maxSize);
      toRemove.forEach(([key]) => cache.current.delete(key));
    }
  }, [maxSize]);

  const get = useCallback((key: string): T | null => {
    const entry = cache.current.get(key);
    
    if (!entry) {
      setCacheStats(prev => ({ ...prev, misses: prev.misses + 1 }));
      return null;
    }

    if (isExpired(entry)) {
      cache.current.delete(key);
      setCacheStats(prev => ({ ...prev, misses: prev.misses + 1 }));
      return null;
    }

    setCacheStats(prev => ({ ...prev, hits: prev.hits + 1 }));
    return entry.data;
  }, [isExpired]);

  const set = useCallback((key: string, data: T, customTtl?: number): void => {
    const entry: CacheEntry<T> = {
      data,
      timestamp: Date.now(),
      ttl: customTtl || ttl
    };

    cache.current.set(key, entry);
    cleanup();
  }, [ttl, cleanup]);

  const has = useCallback((key: string): boolean => {
    const entry = cache.current.get(key);
    if (!entry) return false;
    
    if (isExpired(entry)) {
      cache.current.delete(key);
      return false;
    }
    
    return true;
  }, [isExpired]);

  const clear = useCallback(() => {
    cache.current.clear();
    setCacheStats({ hits: 0, misses: 0 });
  }, []);

  const remove = useCallback((key: string) => {
    cache.current.delete(key);
  }, []);

  const getStats = useCallback(() => ({
    ...cacheStats,
    size: cache.current.size,
    hitRate: cacheStats.hits + cacheStats.misses > 0 
      ? (cacheStats.hits / (cacheStats.hits + cacheStats.misses) * 100).toFixed(1)
      : '0.0'
  }), [cacheStats]);

  return {
    get,
    set,
    has,
    clear,
    remove,
    getStats
  };
}
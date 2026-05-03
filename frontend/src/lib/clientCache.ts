type CacheEntry<T> = {
  data: T
  timestamp: number
  ttl: number  // in Millisekunden
}

// Modul-level Map — überlebt Seitenwechsel in Next.js App Router
const cache = new Map<string, CacheEntry<unknown>>()

export function cacheGet<T>(key: string): T | null {
  const entry = cache.get(key)
  if (!entry) return null
  if (Date.now() - entry.timestamp > entry.ttl) {
    cache.delete(key)
    return null
  }
  return entry.data as T
}

export function cacheSet<T>(key: string, data: T, ttlSeconds = 60): void {
  cache.set(key, {
    data,
    timestamp: Date.now(),
    ttl: ttlSeconds * 1000,
  })
}

export function cacheInvalidate(key: string): void {
  cache.delete(key)
}

export function cacheInvalidateAll(): void {
  cache.clear()
}

// Gibt zurück wie alt die Daten sind (in Sekunden), oder null wenn kein Cache
export function cacheAge(key: string): number | null {
  const entry = cache.get(key)
  if (!entry) return null
  return Math.floor((Date.now() - entry.timestamp) / 1000)
}

// Wrapper: lädt Daten nur wenn Cache abgelaufen oder leer
export async function cachedFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlSeconds = 60,
): Promise<{ data: T; fromCache: boolean }> {
  const cached = cacheGet<T>(key)
  if (cached !== null) {
    return { data: cached, fromCache: true }
  }
  const data = await fetcher()
  cacheSet(key, data, ttlSeconds)
  return { data, fromCache: false }
}

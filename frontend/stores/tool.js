import { defineStore } from 'pinia'

export const useToolStore = defineStore('tool', {
  state: () => ({
    // Cache format: { "http://...": { data: [...], timestamp: 123456789 } }
    cache: {}
  }),
  actions: {
    // Centralized fetching with URL-based caching
    async fetchWithCache(url, forceRefresh = false, ttlMs = 60000) {
      const now = Date.now()
      const cached = this.cache[url]

      // 1. Return cached data if it's still fresh
      if (!forceRefresh && cached && (now - cached.timestamp < ttlMs)) {
        return cached.data
      }

      // 2. Otherwise, fetch from API
      try {
        const res = await fetch(url)
        if (!res.ok) throw new Error(`API Error: ${res.status}`)
        const data = await res.json()
        
        // Save to cache
        this.cache[url] = { data, timestamp: now }
        return data
      } catch (err) {
        console.error(`Fetch failed for ${url}:`, err)
        throw err
      }
    },

    // Formatting helper for Gold/Silver/Copper
    formatMoney(copper) {
      if (copper === null || copper === undefined) return '-'
      const gold = Math.floor(copper / 10000)
      const silver = Math.floor((copper % 10000) / 100)
      const c = copper % 100
      
      let out = []
      if (gold > 0) out.push(`${gold}g`)
      if (silver > 0) out.push(`${silver}s`)
      if (c > 0 || out.length === 0) out.push(`${c}c`)
      return out.join(' ')
    },

    // Formatting helper for Time Ago (The missing function!)
    formatTimeAgo(timestamp) {
      if (!timestamp || timestamp === 0) return 'Never'
      
      // Our backend returns Python timestamps (seconds), not JS milliseconds
      const nowSeconds = Math.floor(Date.now() / 1000)
      const diff = nowSeconds - timestamp
      
      if (diff < 0) return 'Just now'
      if (diff < 60) return 'Just now'
      
      const minutes = Math.floor(diff / 60)
      if (minutes < 60) return `${minutes}m ago`
      
      const hours = Math.floor(minutes / 60)
      if (hours < 24) return `${hours}h ago`
      
      const days = Math.floor(hours / 24)
      return `${days}d ago`
    }
  }
})
import { defineStore } from 'pinia'
import { useFactionStore } from './faction'
import { useToolStore } from './tool'

export const useItemStore = defineStore('item', {
  state: () => ({
    stats: null,
    history: [],
    depth: [],
    listings: [],
    loading: false,
    error: null,
  }),
  actions: {
    async fetchItem(itemId, forceRefresh = false) {
      const factionStore = useFactionStore()
      const toolStore = useToolStore()
      const faction = factionStore.current

      this.loading = true
      this.error = null
      
      const baseUrl = `http://127.0.0.1:8000/items/${itemId}`
      const urls = [
        `${baseUrl}/stats`,
        `${baseUrl}/history`,
        `${baseUrl}/current_depth?faction=${faction}`,
        `http://127.0.0.1:8000/auctions/${itemId}?faction=${faction}`
      ]

      try {
        // Fetch all 4 endpoints in parallel
        const [stats, history, depth, listings] = await Promise.all(
          urls.map(url => toolStore.fetchWithCache(url, forceRefresh))
        )

        this.stats = stats
        this.history = history
        this.depth = depth
        this.listings = listings
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    }
  }
})
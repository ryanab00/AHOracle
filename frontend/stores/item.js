import { defineStore } from 'pinia'
import { useToolStore } from './tool'
import { useFactionStore } from './faction'

export const useItemStore = defineStore('item', {
  state: () => ({
    stats: null,
    history: [],
    depth: [],
    listings: [],
    loading: false
  }),
  actions: {
    async fetchItem(itemId, forceRefresh = false) {
      this.loading = true
      const toolStore = useToolStore()
      const factionStore = useFactionStore()
      const faction = factionStore.current
      
      try {
        const [stats, history, depth, listings] = await Promise.all([
          toolStore.fetchWithCache(`http://127.0.0.1:8000/items/${itemId}/stats?faction=${faction}`, forceRefresh),
          toolStore.fetchWithCache(`http://127.0.0.1:8000/items/${itemId}/history`, forceRefresh),
          toolStore.fetchWithCache(`http://127.0.0.1:8000/items/${itemId}/current_depth?faction=${faction}`, forceRefresh),
          toolStore.fetchWithCache(`http://127.0.0.1:8000/auctions/${itemId}?faction=${faction}`, forceRefresh)
        ])
        
        this.stats = stats
        this.history = history || []
        this.depth = depth || []
        this.listings = listings || []
      } catch (err) {
        console.error('Failed to fetch item:', err)
      } finally {
        this.loading = false
      }
    }
  }
})
import { defineStore } from 'pinia'
import { useToolStore } from './tool'
import { useFactionStore } from './faction'

export const useAuctionStore = defineStore('auction', {
  state: () => ({
    items: [],
    total: 0,
    loading: false
  }),
  actions: {
    async fetchAuctions(page = 1, forceRefresh = false) {
      this.loading = true
      const toolStore = useToolStore()
      const factionStore = useFactionStore()
      const url = `http://127.0.0.1:8000/auctions?page=${page}&faction=${factionStore.current}`
      
      try {
        const data = await toolStore.fetchWithCache(url, forceRefresh)
        // The backend returns { items: [...], total: X, ... }
        this.items = data.items || []
        this.total = data.total || 0
      } catch (err) {
        console.error('Failed to fetch auctions:', err)
        this.items = []
      } finally {
        this.loading = false
      }
    }
  }
})
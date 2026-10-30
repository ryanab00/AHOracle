import { defineStore } from 'pinia'
import { useFactionStore } from './faction'
import { useToolStore } from './tool'

export const useAuctionStore = defineStore('auction', {
  state: () => ({
    items: [],
    loading: false,
    error: null,
  }),
  actions: {
    async fetchAuctions(page = 1, forceRefresh = false) {
      const factionStore = useFactionStore()
      const toolStore = useToolStore()
      
      this.loading = true
      this.error = null
      
      const url = `http://127.0.0.1:8000/auctions?faction=${factionStore.current}&page=${page}&per_page=50`
      
      try {
        const data = await toolStore.fetchWithCache(url, forceRefresh)
        this.items = data.results
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    }
  }
})
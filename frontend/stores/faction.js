import { defineStore } from 'pinia'

export const useFactionStore = defineStore('faction', {
  state: () => ({
    current: 'Horde' // Default faction
  }),
  actions: {
    setFaction(faction) {
      this.current = faction
    }
  }
})
<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { useFactionStore } from '~/stores/faction'
import { useAuctionStore } from '~/stores/auction'
import { useToolStore } from '~/stores/tool'

const factionStore = useFactionStore()
const auctionStore = useAuctionStore()
const toolStore = useToolStore()

const page = ref(1)
const search = ref('')
let debounceTimer = null

// Fetch with server-side search when text changes
watch(search, (newVal) => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    page.value = 1
    auctionStore.fetchAuctions(page.value, newVal)
  }, 300)
})

watch([page, () => factionStore.current], () => {
  auctionStore.fetchAuctions(page.value, search.value)
})

onMounted(() => {
  auctionStore.fetchAuctions(page.value, search.value)
})
</script>

<template>
  <main class="p-8">
    <div class="max-w-6xl mx-auto">
      <div class="bg-gray-800 rounded-lg shadow-lg overflow-hidden">
        
        <!-- Header with Title, Search, and Pagination -->
        <div class="p-4 border-b border-gray-700 flex flex-wrap justify-between items-center gap-4">
          <h2 class="text-xl">{{ factionStore.current }} Auction House</h2>
          
          <div class="flex items-center gap-4">
            <!-- Search Bar -->
            <input 
              v-model="search"
              type="text" 
              placeholder="Search name or ID..." 
              class="bg-gray-900 text-white px-3 py-1.5 rounded border border-gray-600 text-sm w-64 focus:outline-none focus:border-blue-500" 
            />
            
            <!-- Pagination -->
            <div class="space-x-2 flex items-center">
              <button :disabled="page === 1" @click="page--" class="px-4 py-2 bg-gray-700 rounded disabled:opacity-50 hover:bg-gray-600 transition">Prev</button>
              <span class="px-4 py-2">Page {{ page }}</span>
              <button @click="page++" class="px-4 py-2 bg-gray-700 rounded hover:bg-gray-600 transition">Next</button>
            </div>
          </div>
        </div>

        <!-- Data Table -->
        <div v-if="auctionStore.loading" class="p-8 text-center text-gray-400">Loading summary...</div>
        
        <table v-else-if="auctionStore.items.length > 0" class="w-full text-left">
          <thead class="bg-gray-900 text-gray-400 text-sm">
            <tr>
              <th class="p-3">Item</th>
              <th class="p-3 text-right">Total Available</th>
              <th class="p-3 text-right">Listings</th>
              <th class="p-3 text-right">Min Price</th>
              <th class="p-3 text-right">Max Price</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-700">
            <tr v-for="item in auctionStore.items" :key="item.item_id" class="hover:bg-gray-700/50 transition-colors">
              <td class="p-3">
                <NuxtLink :to="`/item/${item.item_id}`" class="text-blue-400 hover:underline font-medium">
                  {{ item.item_name }}
                </NuxtLink>
              </td>
              <td class="p-3 text-right font-mono text-gray-300">{{ item.total_quantity }}</td>
              <td class="p-3 text-right font-mono text-gray-500">{{ item.num_listings }}</td>
              <td class="p-3 text-right font-mono text-green-400">{{ toolStore.formatMoney(item.min_price) }}</td>
              <td class="p-3 text-right font-mono text-red-400">{{ toolStore.formatMoney(item.max_price) }}</td>
            </tr>
          </tbody>
        </table>

        <div v-else class="p-8 text-center text-gray-500 italic">
          No items found matching your search.
        </div>

      </div>
    </div>
  </main>
</template>
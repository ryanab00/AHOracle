<script setup>
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useFactionStore } from '~/stores/faction'
import { useItemStore } from '~/stores/item'
import { useToolStore } from '~/stores/tool'
import MarketChart from '~/components/MarketChart.vue'
import OrderBook from '~/components/OrderBook.vue'

const route = useRoute()
const router = useRouter()
const factionStore = useFactionStore()
const itemStore = useItemStore()
const toolStore = useToolStore()

onMounted(() => {
  itemStore.fetchItem(route.params.id)
})

watch(() => factionStore.current, () => {
  itemStore.fetchItem(route.params.id)
})
</script>

<template>
  <main class="p-8">
    <div v-if="itemStore.loading" class="max-w-5xl mx-auto">Loading...</div>

    <div v-else-if="itemStore.stats" class="max-w-5xl mx-auto">
      <button @click="router.back()" class="text-gray-400 mb-4 hover:text-white transition">&larr; Back</button>
      
      <h1 class="text-3xl font-bold mb-6 text-yellow-500">
        {{ itemStore.stats.item.item_name }} <span class="text-sm text-gray-400">(ID: {{ itemStore.stats.item.item_id }})</span>
      </h1>

      <!-- Top Chart: Price & Volume over Time -->
      <div class="bg-gray-800 rounded-lg p-4 mb-6">
        <h2 class="text-lg font-bold mb-4 border-b border-gray-700 pb-2">Price & Volume History</h2>
        <MarketChart v-if="itemStore.history.length > 0" :data="itemStore.history" :faction="factionStore.current" />
        <p v-else class="text-gray-500 text-sm">Not enough data.</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- Left: Order Book -->
        <div class="md:col-span-2 bg-gray-800 rounded-lg p-4">
          <h2 class="text-lg font-bold mb-4 border-b border-gray-700 pb-2">Cumulative Order Book</h2>
          <p class="text-xs text-gray-400 mb-2">Shows how many units you can buy before the price jumps.</p>
          <OrderBook v-if="itemStore.depth.length > 0" :data="itemStore.depth" :faction="factionStore.current" />
          <p v-else class="text-gray-500 text-sm">No listings found.</p>
        </div>

        <!-- Right: Current Listings -->
        <div class="bg-gray-800 rounded-lg p-4">
          <h2 class="text-lg font-bold mb-4 border-b border-gray-700 pb-2">Top Listings</h2>
          <ul class="space-y-2 max-h-[250px] overflow-y-auto pr-2">
            <li v-for="(l, i) in itemStore.listings" :key="i" class="flex justify-between text-sm border-b border-gray-700/50 pb-1">
              <span class="text-gray-400">{{ l.stack_size }}x</span>
              <span class="text-yellow-400 font-mono">{{ toolStore.formatMoney(l.unit_buyout_price) }}</span>
            </li>
            <li v-if="itemStore.listings.length === 0" class="text-gray-500">No listings.</li>
          </ul>
        </div>
      </div>
    </div>
  </main>
</template>
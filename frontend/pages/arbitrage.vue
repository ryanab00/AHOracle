<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useToolStore } from '~/stores/tool'

const toolStore = useToolStore()
const direction = ref('ally_to_horde')
const loading = ref(true)
const opportunities = ref([])
const sortKey = ref('roi')
const sortDesc = ref(true)

const loadData = async () => {
  loading.value = true
  try {
    const url = `http://127.0.0.1:8000/arbitrage?direction=${direction.value}`
    const data = await toolStore.fetchWithCache(url, true)
    // Ensure we always set an array
    opportunities.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Failed to load arbitrage data', err)
    opportunities.value = []
  } finally {
    loading.value = false
  }
}

const setSort = (key) => {
  if (sortKey.value === key) sortDesc.value = !sortDesc.value
  else { sortKey.value = key; sortDesc.value = true }
}

const sortedOpportunities = computed(() => {
  if (!opportunities.value) return []
  // Filter out any nulls to prevent "reading craft_data of undefined" crashes
  return [...opportunities.value]
    .filter(item => item != null)
    .sort((a, b) => {
      let valA = a[sortKey.value]
      let valB = b[sortKey.value]
      if (typeof valA === 'string') { valA = valA.toLowerCase(); valB = valB.toLowerCase() }
      if (valA < valB) return sortDesc.value ? 1 : -1
      if (valA > valB) return sortDesc.value ? -1 : 1
      return 0
    })
})

watch(direction, loadData)
onMounted(loadData)
</script>

<template>
  <main class="p-8 w-full max-w-7xl mx-auto">
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
      <div>
        <h1 class="text-3xl font-bold text-yellow-500">Market Arbitrage</h1>
        <p class="text-sm text-gray-400 mt-1">Expand any craftable item (marked with ▶) to see raw material costs.</p>
      </div>
      <div class="flex bg-gray-800 rounded-lg p-1 border border-gray-700">
        <button @click="direction = 'ally_to_horde'" :class="['px-6 py-2 text-sm font-bold rounded transition-colors', direction === 'ally_to_horde' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white']">Ally ➔ Horde</button>
        <button @click="direction = 'horde_to_ally'" :class="['px-6 py-2 text-sm font-bold rounded transition-colors', direction === 'horde_to_ally' ? 'bg-red-600 text-white' : 'text-gray-400 hover:text-white']">Horde ➔ Ally</button>
      </div>
    </div>
    
    <div v-if="loading" class="text-gray-400">Scanning markets for the best flips...</div>
    <div v-else-if="sortedOpportunities.length === 0" class="bg-gray-800 rounded-lg p-8 text-center text-gray-500 border border-gray-700">
      No profitable flips found right now.
    </div>
    
    <div v-else class="bg-gray-800 rounded-lg shadow-lg overflow-hidden border border-gray-700">
      <table class="w-full text-left">
        <thead class="text-gray-400 text-sm border-b border-gray-700 bg-gray-900/50">
          <tr>
            <th class="p-4 w-8"></th>
            <th @click="setSort('item_name')" class="p-4 cursor-pointer hover:bg-gray-700/50">Item <span v-if="sortKey === 'item_name'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
            <th @click="setSort('buy_price')" class="p-4 text-right cursor-pointer hover:bg-gray-700/50">Min Buy <span v-if="sortKey === 'buy_price'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
            <th @click="setSort('sell_price')" class="p-4 text-right cursor-pointer hover:bg-gray-700/50">Safe Sell <span v-if="sortKey === 'sell_price'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
            <th @click="setSort('qty_available')" class="p-4 text-right cursor-pointer hover:bg-gray-700/50">Supply <span v-if="sortKey === 'qty_available'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
            <th @click="setSort('roi')" class="p-4 text-right text-yellow-500 cursor-pointer hover:bg-gray-700/50">ROI % <span v-if="sortKey === 'roi'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
            <th @click="setSort('total_profit')" class="p-4 text-right text-indigo-300 cursor-pointer hover:bg-gray-700/50">Max Profit <span v-if="sortKey === 'total_profit'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-700/50 text-sm">
          <template v-for="item in sortedOpportunities" :key="item.item_id">
            <!-- Main Row -->
            <tr @click="item.craft_data ? (item.isOpen = !item.isOpen) : null" class="hover:bg-gray-700/30 transition-colors cursor-pointer">
              <td class="p-4 text-center text-gray-500 w-8">
                <span v-if="item?.craft_data" :class="item.isOpen ? 'inline-block rotate-90 transition-transform' : 'inline-block transition-transform'">▶</span>
              </td>
              <td class="p-4 font-medium text-gray-200">
                <NuxtLink :to="`/item/${item.item_id}`" class="hover:text-blue-400" @click.stop>{{ item.item_name }}</NuxtLink>
              </td>
              <td class="p-4 text-right font-mono text-gray-400 whitespace-nowrap">{{ toolStore.formatMoney(item.buy_price) }}</td>
              <td class="p-4 text-right font-mono text-gray-400 whitespace-nowrap">{{ toolStore.formatMoney(item.sell_price) }}</td>
              <td class="p-4 text-right font-mono text-gray-300">{{ item.qty_available }}</td>
              <td class="p-4 text-right font-mono font-bold text-green-400">{{ item.roi.toFixed(1) }}%</td>
              <td class="p-4 text-right font-mono font-bold text-indigo-300 whitespace-nowrap">+{{ toolStore.formatMoney(item.total_profit) }}</td>
            </tr>
            
            <!-- Expanded Row -->
            <tr v-if="item.isOpen && item.craft_data" class="bg-gray-900/50 shadow-inner">
              <td colspan="7" class="p-6">
                <div class="flex justify-between items-center mb-4">
                  <h4 class="text-gray-300 font-bold text-sm">Crafting vs. Direct Flip</h4>
                  <span class="text-xs text-gray-500">
                    Cost to craft: <span class="text-blue-400">Ally: {{ toolStore.formatMoney(item.craft_data.ally_cost) }}</span> | 
                    <span class="text-red-400">Horde: {{ toolStore.formatMoney(item.craft_data.horde_cost) }}</span>
                  </span>
                </div>
                <table class="w-full text-xs text-left max-w-3xl">
                  <thead class="text-gray-500 border-b border-gray-700">
                    <tr>
                      <th class="pb-2 font-normal">Reagent</th>
                      <th class="pb-2 font-normal text-right">Qty</th>
                      <th class="pb-2 font-normal text-right text-blue-400">Ally Cost</th>
                      <th class="pb-2 font-normal text-right text-red-400">Horde Cost</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-800">
                    <tr v-for="mat in item.craft_data.reagents" :key="mat.name" class="hover:bg-gray-800/50">
                      <td class="py-2 text-gray-300">{{ mat.name }}</td>
                      <td class="py-2 text-right text-gray-500">{{ mat.qty }}</td>
                      <td class="py-2 text-right font-mono" :class="mat.ally_cost === 0 ? 'text-red-500' : 'text-gray-400'">
                        {{ mat.ally_cost === 0 ? 'Missing' : toolStore.formatMoney(mat.ally_cost) }}
                      </td>
                      <td class="py-2 text-right font-mono" :class="mat.horde_cost === 0 ? 'text-red-500' : 'text-gray-400'">
                        {{ mat.horde_cost === 0 ? 'Missing' : toolStore.formatMoney(mat.horde_cost) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </main>
</template>
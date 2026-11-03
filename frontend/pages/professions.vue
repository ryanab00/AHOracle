<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useToolStore } from '~/stores/tool'

const toolStore = useToolStore()
const loading = ref(true)
const errorMsg = ref(null)
const craftQuantity = ref(1)
const categories = ref([])
const selectedCategory = ref(null)

const loadData = async () => {
  loading.value = true
  errorMsg.value = null
  const url = `http://127.0.0.1:8000/consumables?quantity=${craftQuantity.value}`
  try {
    const data = await toolStore.fetchWithCache(url, true)
    const map = new Map()
    data.forEach(item => {
      const cat = item.category || 'Other'
      if (!map.has(cat)) map.set(cat, [])
      map.get(cat).push(item)
    })
    categories.value = Array.from(map.entries()).map(([name, items]) => {
      const profits = items.map(i => Math.max(
        i.horde?.insufficient_supply ? 0 : (i.horde?.total_profit || 0),
        i.alliance?.insufficient_supply ? 0 : (i.alliance?.total_profit || 0)
      ))
      const rois = items.flatMap(i => [i.horde?.roi, i.alliance?.roi])
        .filter(r => typeof r === 'number' && r > 0)
      return {
        name,
        items,
        count: items.length,
        bestProfit: Math.max(0, ...profits),
        avgRoi: rois.length ? rois.reduce((a, b) => a + b, 0) / rois.length : 0
      }
    }).sort((a, b) => b.bestProfit - a.bestProfit)
    if (categories.value.length > 0) selectedCategory.value = categories.value[0].name
  } catch (err) {
    errorMsg.value = 'Failed to load profession data.'
    console.error(err)
  } finally {
    loading.value = false
  }
}

const activeItems = computed(() => {
  const cat = categories.value.find(c => c.name === selectedCategory.value)
  if (!cat) return []
  return cat.items.map(item => {
    const hProfit = item.horde?.insufficient_supply ? -Infinity : (item.horde?.total_profit ?? -Infinity)
    const aProfit = item.alliance?.insufficient_supply ? -Infinity : (item.alliance?.total_profit ?? -Infinity)
    let best = null
    let faction = null
    if (hProfit !== -Infinity || aProfit !== -Infinity) {
      if (hProfit >= aProfit) { best = item.horde; faction = 'Horde' }
      else { best = item.alliance; faction = 'Alliance' }
    }
    return { ...item, best, bestFaction: faction }
  }).sort((a, b) => {
    const aP = a.best?.total_profit ?? -Infinity
    const bP = b.best?.total_profit ?? -Infinity
    return bP - aP
  })
})

watch(craftQuantity, loadData)
onMounted(loadData)
</script>

<template>
  <main class="p-8 w-full">
    <div class="max-w-7xl mx-auto">
      <div class="flex justify-between items-center mb-6">
        <div>
          <h1 class="text-3xl font-bold text-yellow-500">Professions</h1>
          <p class="text-sm text-gray-400 mt-1">
            Crafting profitability grouped by recipe category, using live AH prices.
          </p>
        </div>
        <div class="flex items-center space-x-3 bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
          <label class="text-sm text-gray-400">Craft Quantity:</label>
          <input
            type="number"
            v-model="craftQuantity"
            min="1"
            class="bg-gray-900 text-white w-20 px-2 py-1 rounded border border-gray-600 font-mono text-center"
          />
        </div>
      </div>

      <div v-if="loading" class="text-gray-400">Loading profession data...</div>
      <div v-else-if="errorMsg" class="text-red-500">{{ errorMsg }}</div>

      <div v-else class="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <!-- Category sidebar -->
        <div class="lg:col-span-1 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div class="p-3 bg-gray-900/50 border-b border-gray-700 text-sm font-bold text-gray-300 flex justify-between">
            <span>Categories</span>
            <span class="text-gray-500 font-normal">{{ categories.length }}</span>
          </div>
          <ul class="divide-y divide-gray-700/50 max-h-[600px] overflow-y-auto">
            <li v-for="cat in categories" :key="cat.name">
              <button
                @click="selectedCategory = cat.name"
                :class="[
                  'w-full text-left p-3 hover:bg-gray-700/50 transition',
                  selectedCategory === cat.name
                    ? 'bg-indigo-900/30 border-l-4 border-indigo-500'
                    : 'border-l-4 border-transparent'
                ]"
              >
                <div class="font-medium text-gray-200">{{ cat.name }}</div>
                <div class="text-xs text-gray-500 mt-0.5">
                  {{ cat.count }} recipes · best
                  <span class="text-green-400 font-mono">
                    {{ toolStore.formatMoney(cat.bestProfit) }}
                  </span>
                </div>
              </button>
            </li>
          </ul>
        </div>

        <!-- Recipe table -->
        <div class="lg:col-span-3">
          <div
            v-if="activeItems.length === 0"
            class="bg-gray-800 rounded-lg p-8 text-center text-gray-500 italic border border-gray-700"
          >
            No recipes in this category.
          </div>

          <div v-else class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
            <div class="p-3 bg-gray-900/50 border-b border-gray-700 flex justify-between items-center">
              <span class="font-bold text-gray-200">{{ selectedCategory }}</span>
              <span class="text-xs text-gray-500">
                {{ activeItems.length }} recipes · best market highlighted
              </span>
            </div>
            <table class="w-full text-left">
              <thead class="text-gray-400 text-xs bg-gray-900/30 border-b border-gray-700">
                <tr>
                  <th class="p-3">Recipe</th>
                  <th class="p-3 text-right">Craft Cost</th>
                  <th class="p-3 text-right">Revenue</th>
                  <th class="p-3 text-right">Profit</th>
                  <th class="p-3 text-right">ROI</th>
                  <th class="p-3 text-center">Best Market</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-700/50 text-sm">
                <tr
                  v-for="item in activeItems"
                  :key="item.name"
                  class="hover:bg-gray-700/30 transition"
                >
                  <td class="p-3 font-medium text-gray-200">{{ item.name }}</td>

                  <template v-if="item.best">
                    <td class="p-3 text-right font-mono text-gray-400">
                      {{ toolStore.formatMoney(item.best.total_craft_cost) }}
                    </td>
                    <td class="p-3 text-right font-mono text-gray-400">
                      {{ toolStore.formatMoney(item.best.total_revenue) }}
                    </td>
                    <td
                      class="p-3 text-right font-mono font-bold"
                      :class="item.best.total_profit > 0 ? 'text-green-400' : 'text-red-400'"
                    >
                      {{ toolStore.formatMoney(item.best.total_profit) }}
                    </td>
                    <td
                      class="p-3 text-right font-mono"
                      :class="item.best.roi > 0 ? 'text-green-400' : 'text-red-400'"
                    >
                      {{ item.best.roi.toFixed(1) }}%
                    </td>
                    <td
                      class="p-3 text-center text-xs font-bold"
                      :class="item.bestFaction === 'Horde' ? 'text-red-400' : 'text-blue-400'"
                    >
                      {{ item.bestFaction }}
                    </td>
                  </template>

                  <template v-else>
                    <td colspan="5" class="p-3 text-center text-gray-600 italic">
                      No profitable market found
                    </td>
                  </template>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
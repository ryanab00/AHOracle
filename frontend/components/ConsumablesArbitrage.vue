<script setup>
import { ref, computed } from 'vue'
import { useToolStore } from '~/stores/tool'

const props = defineProps({ items: Array })
const toolStore = useToolStore()

// Direction: 'ally_to_horde' or 'horde_to_ally'
const direction = ref('ally_to_horde')
// Action Type: 'craft' or 'transfer'
const actionType = ref('craft') 

// Sorting State
const sortKey = ref('profit')
const sortDesc = ref(true)

const setSort = (key) => {
  if (sortKey.value === key) sortDesc.value = !sortDesc.value
  else { sortKey.value = key; sortDesc.value = true }
}

const arbitrageOpportunities = computed(() => {
  if (!props.items) return []

  const mapped = props.items.map(item => {
    let source = null
    let dest = null
    
    if (direction.value === 'ally_to_horde') {
      source = item.alliance
      dest = item.horde
    } else {
      source = item.horde
      dest = item.alliance
    }

    // Need both factions to have data
    if (!source || !dest) return null

    let costBasis = 0
    let revenue = dest.avg_output_price // Default revenue is selling at Dest average price

    if (actionType.value === 'craft') {
      // Crafting Arbitrage: We need to be able to buy the mats
      if (source.insufficient_supply) return null
      costBasis = source.total_craft_cost / item.quantity // Cost per craft
    } else {
      // Direct Transfer: We buy the finished product on Source
      costBasis = source.avg_output_price
    }

    const profitPerUnit = revenue - costBasis
    const totalProfit = profitPerUnit * item.quantity
    const roi = costBasis > 0 ? (profitPerUnit / costBasis) * 100 : 0

    return {
      name: item.name,
      sourcePrice: costBasis,
      destPrice: revenue,
      priceDiff: revenue - costBasis,
      totalProfit,
      roi
    }
  })
  .filter(item => item !== null && item.totalProfit > 0) // Only show profitable

  // Sort logic
  return mapped.sort((a, b) => {
    let valA = a[sortKey.value]
    let valB = b[sortKey.value]
    
    if (typeof valA === 'string') {
      valA = valA.toLowerCase()
      valB = valB.toLowerCase()
    }

    if (valA < valB) return sortDesc.value ? 1 : -1
    if (valA > valB) return sortDesc.value ? -1 : 1
    return 0
  })
})
</script>

<template>
  <div class="bg-gray-800 rounded-lg shadow-lg overflow-hidden border border-indigo-500/50 w-full overflow-x-auto">
    
    <!-- Controls Bar -->
    <div class="p-4 bg-indigo-900/30 border-b border-indigo-500/50 flex flex-wrap justify-between items-center min-w-[800px] gap-4">
      
      <!-- Action Type Toggle -->
      <div class="flex bg-gray-900 rounded-lg p-1 border border-gray-700">
        <button 
          @click="actionType = 'craft'"
          :class="['px-4 py-1.5 text-xs font-bold rounded transition-colors', actionType === 'craft' ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white']"
        >
          Craft & Sell
        </button>
        <button 
          @click="actionType = 'transfer'"
          :class="['px-4 py-1.5 text-xs font-bold rounded transition-colors', actionType === 'transfer' ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white']"
        >
          Direct Transfer (Flip)
        </button>
      </div>

      <div class="text-sm text-indigo-200/70">
        <span v-if="actionType === 'craft'">
          Buy reagents on <strong class="text-white">{{ direction === 'ally_to_horde' ? 'Alliance' : 'Horde' }}</strong>, craft, and sell on <strong class="text-white">{{ direction === 'ally_to_horde' ? 'Horde' : 'Alliance' }}</strong>.
        </span>
        <span v-else>
          Buy the finished consume (or use stockpile) on <strong class="text-white">{{ direction === 'ally_to_horde' ? 'Alliance' : 'Horde' }}</strong>, and sell on <strong class="text-white">{{ direction === 'ally_to_horde' ? 'Horde' : 'Alliance' }}</strong>.
        </span>
      </div>

      <!-- Direction Toggle -->
      <div class="flex bg-gray-900 rounded-lg p-1 border border-gray-700">
        <button 
          @click="direction = 'ally_to_horde'"
          :class="['px-4 py-1.5 text-xs font-bold rounded transition-colors', direction === 'ally_to_horde' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white']"
        >
          Ally ➔ Horde
        </button>
        <button 
          @click="direction = 'horde_to_ally'"
          :class="['px-4 py-1.5 text-xs font-bold rounded transition-colors', direction === 'horde_to_ally' ? 'bg-red-600 text-white' : 'text-gray-400 hover:text-white']"
        >
          Horde ➔ Ally
        </button>
      </div>
    </div>

    <table class="w-full text-left min-w-[800px]">
      <thead class="text-gray-400 text-sm border-b border-gray-700 bg-gray-800/80">
        <tr>
          <th @click="setSort('name')" class="p-3 border-r border-gray-700 w-64 cursor-pointer hover:bg-gray-700/50 transition-colors">
            Consumable <span v-if="sortKey === 'name'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
          </th>
          
          <!-- Dynamic Header for Source Price -->
          <th @click="setSort('sourcePrice')" class="p-3 text-right border-r border-gray-700 cursor-pointer hover:bg-gray-700/50 transition-colors">
            <span v-if="actionType === 'craft'">Craft Cost (Source)</span>
            <span v-else>Buy Price (Source)</span>
            <span v-if="sortKey === 'sourcePrice'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
          </th>
          
          <!-- Dynamic Header for Dest Price -->
          <th @click="setSort('destPrice')" class="p-3 text-right border-r border-gray-700 cursor-pointer hover:bg-gray-700/50 transition-colors">
            Sell Price (Dest) <span v-if="sortKey === 'destPrice'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
          </th>
          
          <th @click="setSort('priceDiff')" class="p-3 text-right border-r border-gray-700 text-indigo-300 cursor-pointer hover:bg-gray-700/50 transition-colors">
            Profit Per Unit <span v-if="sortKey === 'priceDiff'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
          </th>

          <th @click="setSort('totalProfit')" class="p-3 text-right border-r border-gray-700 text-indigo-300 cursor-pointer hover:bg-gray-700/50 transition-colors">
            Total Profit <span v-if="sortKey === 'totalProfit'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
          </th>

          <th @click="setSort('roi')" class="p-3 text-right text-yellow-500 cursor-pointer hover:bg-gray-700/50 transition-colors">
            ROI % <span v-if="sortKey === 'roi'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-700/50 text-sm">
        <tr v-if="arbitrageOpportunities.length === 0">
          <td colspan="6" class="p-6 text-center text-gray-500 italic">
            No profitable arbitrage found in this direction (or missing data).
          </td>
        </tr>
        <tr v-for="item in arbitrageOpportunities" :key="item.name" class="hover:bg-gray-700/30 transition-colors">
          <td class="p-3 border-r border-gray-700 font-medium text-gray-200">{{ item.name }}</td>
          
          <td class="p-3 text-right font-mono text-gray-400 border-r border-gray-700">
            {{ toolStore.formatMoney(item.sourcePrice) }}
          </td>
          
          <td class="p-3 text-right font-mono text-gray-400 border-r border-gray-700">
            {{ toolStore.formatMoney(item.destPrice) }}
          </td>

          <td class="p-3 text-right font-mono font-bold text-green-400 border-r border-gray-700">
            +{{ toolStore.formatMoney(item.priceDiff) }}
          </td>

          <td class="p-3 text-right font-mono font-bold text-indigo-300 border-r border-gray-700">
            {{ toolStore.formatMoney(item.totalProfit) }}
          </td>
          
          <td class="p-3 text-right font-mono text-green-400">
            {{ item.roi.toFixed(1) }}%
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
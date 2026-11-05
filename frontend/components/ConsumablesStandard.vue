<script setup>
import { ref, computed } from 'vue'
import { useToolStore } from '~/stores/tool'

const props = defineProps({ items: Array })
const toolStore = useToolStore()

const sortKey = ref('roi')
const sortDesc = ref(true)
const expandedRows = ref(new Set())
const searchQuery = ref('')

const toggleExpand = (name) => {
    if (expandedRows.value.has(name)) expandedRows.value.delete(name)
    else expandedRows.value.add(name)
}

const setSort = (key) => {
    if (sortKey.value === key) sortDesc.value = !sortDesc.value
    else { sortKey.value = key; sortDesc.value = true }
}

const sortedConsumables = computed(() => {
    if (!props.items) return []
    
    let list = [...props.items]
    
    if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase()
        list = list.filter(item => item.name.toLowerCase().includes(q))
    }

    return list.sort((a, b) => {
        const getVal = (item) => {
            if (item.insufficient_supply || item[sortKey.value] === null) return -999999999
            return item[sortKey.value]
        }
        const valA = getVal(a)
        const valB = getVal(b)
        if (valA < valB) return sortDesc.value ? 1 : -1
        if (valA > valB) return sortDesc.value ? -1 : 1
        return 0
    })
})
</script>

<template>
    <div class="bg-gray-800 rounded-lg shadow-lg overflow-hidden border border-gray-700 w-full overflow-x-auto">
        <div class="p-3 bg-gray-900/50 border-b border-gray-700 flex justify-between items-center">
            <h3 class="font-bold text-gray-200">Market Prices</h3>
            <input 
                v-model="searchQuery"
                type="text" 
                placeholder="Search consumes..." 
                class="bg-gray-900 text-white px-3 py-1.5 rounded border border-gray-600 font-mono text-sm w-64 focus:outline-none focus:border-blue-500" 
            />
        </div>
        
        <table class="w-full text-left min-w-[800px]">
            <thead class="text-gray-400 text-sm border-b border-gray-700 bg-gray-800/80">
                <tr>
                    <th @click="setSort('name')" class="p-3 border-r border-gray-700 w-64 cursor-pointer hover:bg-gray-700/50 transition-colors">
                        Consumable <span v-if="sortKey === 'name'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
                    </th>
                    <th @click="setSort('max_crafts')" class="p-3 text-right border-r border-gray-700 text-blue-400 cursor-pointer hover:bg-gray-700/50 transition-colors">
                        Max Craftable <span v-if="sortKey === 'max_crafts'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
                    </th>
                    <th @click="setSort('total_craft_cost')" class="p-3 text-right border-r border-gray-700 cursor-pointer hover:bg-gray-700/50 transition-colors">
                        Unit Cost <span v-if="sortKey === 'total_craft_cost'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
                    </th>
                    <th @click="setSort('total_profit')" class="p-3 text-right border-r border-gray-700 cursor-pointer hover:bg-gray-700/50 transition-colors">
                        Unit Profit <span v-if="sortKey === 'total_profit'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
                    </th>
                    <th @click="setSort('roi')" class="p-3 text-right cursor-pointer hover:bg-gray-700/50 transition-colors">
                        ROI % <span v-if="sortKey === 'roi'" :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
                    </th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700/50 text-sm">
                <template v-for="item in sortedConsumables" :key="item.name">
                    <tr @click="toggleExpand(item.name)" class="hover:bg-gray-700/30 transition-colors cursor-pointer">
                        <td class="p-3 border-r border-gray-700 font-medium text-gray-200 flex items-center justify-between">
                            <span>{{ item.name }}</span>
                            <span class="text-gray-500 text-xs">{{ expandedRows.has(item.name) ? '▼' : '▶' }}</span>
                        </td>
                        <td class="p-3 text-right font-mono border-r border-gray-700">
                            <span v-if="item.insufficient_supply" class="text-gray-600">-</span>
                            <span v-else class="text-blue-400 font-bold">{{ item.max_crafts }}</span>
                        </td>
                        <td class="p-3 text-right font-mono text-gray-400 border-r border-gray-700">
                            {{ item.insufficient_supply ? '-' : toolStore.formatMoney(item.total_craft_cost) }}
                        </td>
                        <td class="p-3 text-right font-mono font-bold border-r border-gray-700" :class="item.total_profit > 0 ? 'text-green-400' : 'text-red-400'">
                            {{ item.insufficient_supply ? '-' : toolStore.formatMoney(item.total_profit) }}
                        </td>
                        <td class="p-3 text-right font-mono" :class="item.roi > 0 ? 'text-green-400' : 'text-red-400'">
                            {{ item.insufficient_supply ? '-' : item.roi.toFixed(1) + '%' }}
                        </td>
                    </tr>
                    
                    <!-- Expanded Breakdown -->
                    <tr v-if="expandedRows.has(item.name)" class="shadow-inner bg-gray-900/20">
                        <td colspan="5" class="p-4">
                            <h4 class="text-gray-300 font-bold text-sm mb-3">Reagent Breakdown</h4>
                            <div v-if="item.insufficient_supply" class="text-yellow-500 font-medium text-xs mb-4">
                                Missing reagents — cannot craft currently.
                            </div>
                            <table v-if="!item.insufficient_supply" class="w-full text-xs text-left">
                                <thead class="text-gray-500 border-b border-gray-700/50">
                                    <tr>
                                        <th class="pb-1 font-normal">Reagent</th>
                                        <th class="pb-1 font-normal text-right">Req</th>
                                        <th class="pb-1 font-normal text-right">Current Unit</th>
                                        <th class="pb-1 font-normal text-right">Available</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="r in item.reagent_details" :key="r.name" class="border-b border-gray-700/20 last:border-0">
                                        <td class="py-1.5 text-gray-300 flex items-center">
                                            {{ r.name }}
                                            <span v-if="r.method === 'Vendor'" class="text-blue-400 text-[10px] ml-1">(Vendor)</span>
                                            <span v-if="r.method === 'Craft'" class="text-purple-400 text-[10px] font-bold ml-1" title="Cheaper to craft than buy on AH">[Craft]</span>
                                        </td>
                                        <td class="py-1.5 text-right text-gray-400">{{ r.req }}</td>
                                        <td class="py-1.5 text-right font-mono text-gray-400">{{ toolStore.formatMoney(r.current_price) }}</td>
                                        <td class="py-1.5 text-right text-gray-500">{{ r.available }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                    </tr>
                </template>
            </tbody>
        </table>
    </div>
</template>
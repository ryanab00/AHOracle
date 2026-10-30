<script setup>
import { ref, computed } from 'vue'
import { useToolStore } from '~/stores/tool'

const props = defineProps({ items: Array })
const toolStore = useToolStore()

const sortKey = ref('roi')
const sortFaction = ref('horde')
const sortDesc = ref(true)
const expandedRows = ref(new Set())

const toggleExpand = (name) => {
    if (expandedRows.value.has(name)) expandedRows.value.delete(name)
    else expandedRows.value.add(name)
}

const setSort = (key, faction = null) => {
    if (sortKey.value === key && sortFaction.value === faction) sortDesc.value = !sortDesc.value
    else { sortKey.value = key; sortFaction.value = faction; sortDesc.value = true }
}

const sortedConsumables = computed(() => {
    if (!props.items) return []
    return [...props.items].sort((a, b) => {
        if (sortKey.value === 'name') {
            const valA = a.name.toLowerCase()
            const valB = b.name.toLowerCase()
            if (valA < valB) return sortDesc.value ? 1 : -1
            if (valA > valB) return sortDesc.value ? -1 : 1
            return 0
        }
        const getVal = (item) => {
            const data = item[sortFaction.value]
            if (!data || data.insufficient_supply || data[sortKey.value] === null) return -999999999
            return data[sortKey.value]
        }
        const valA = getVal(a)
        const valB = getVal(b)
        if (valA < valB) return sortDesc.value ? 1 : -1
        if (valA > valB) return sortDesc.value ? -1 : 1
        return 0
    })
})

// Helper to calculate 7-day total reagent cost
const get7dReagentCost = (reagentDetails) => {
    if (!reagentDetails) return 0
    return reagentDetails.reduce((sum, r) => sum + (r.req * r.avg_price), 0)
}
</script>

<template>
    <div class="bg-gray-800 rounded-lg shadow-lg overflow-hidden border border-gray-700 w-full overflow-x-auto">
        <table class="w-full text-left min-w-[800px]">
            <thead class="text-gray-400 text-sm border-b border-gray-700 bg-gray-800/80">
                <tr>
                    <th @click="setSort('name')"
                        class="p-3 border-r border-gray-700 w-64 cursor-pointer hover:bg-gray-700/50 transition-colors">
                        Consumable <span v-if="sortKey === 'name'"
                            :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span>
                    </th>
                    <th colspan="3" class="p-3 text-center text-red-400 border-r border-gray-700">Horde Market</th>
                    <th colspan="3" class="p-3 text-center text-blue-400">Alliance Market</th>
                </tr>
                <tr class="text-xs bg-gray-900/30">
                    <th class="p-2 border-r border-gray-700 text-gray-500">Recipe</th>
                    <th @click="setSort('total_craft_cost', 'horde')"
                        class="p-2 text-right cursor-pointer hover:text-white">Cost <span
                            v-if="sortKey === 'total_craft_cost' && sortFaction === 'horde'"
                            :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
                    <th @click="setSort('total_profit', 'horde')"
                        class="p-2 text-right cursor-pointer hover:text-white">Profit <span
                            v-if="sortKey === 'total_profit' && sortFaction === 'horde'"
                            :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
                    <th @click="setSort('roi', 'horde')"
                        class="p-2 text-right border-r border-gray-700 cursor-pointer hover:text-white">ROI % <span
                            v-if="sortKey === 'roi' && sortFaction === 'horde'"
                            :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
                    <th @click="setSort('total_craft_cost', 'alliance')"
                        class="p-2 text-right cursor-pointer hover:text-white">Cost <span
                            v-if="sortKey === 'total_craft_cost' && sortFaction === 'alliance'"
                            :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
                    <th @click="setSort('total_profit', 'alliance')"
                        class="p-2 text-right cursor-pointer hover:text-white">Profit <span
                            v-if="sortKey === 'total_profit' && sortFaction === 'alliance'"
                            :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
                    <th @click="setSort('roi', 'alliance')" class="p-2 text-right cursor-pointer hover:text-white">ROI %
                        <span v-if="sortKey === 'roi' && sortFaction === 'alliance'"
                            :class="sortDesc ? 'text-green-400' : 'text-red-400'">{{ sortDesc ? '▲' : '▼' }}</span></th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700/50 text-sm">
                <template v-for="item in sortedConsumables" :key="item.name">
                    <tr @click="toggleExpand(item.name)" class="hover:bg-gray-700/30 transition-colors cursor-pointer">
                        <td
                            class="p-3 border-r border-gray-700 font-medium text-gray-200 flex items-center justify-between">
                            <span>{{ item.name }}</span>
                            <span class="text-gray-500 text-xs">{{ expandedRows.has(item.name) ? '▼' : '▶' }}</span>
                        </td>
                        <template v-if="item.horde">
                            <td class="p-3 text-right font-mono text-gray-400">{{ item.horde.insufficient_supply ? '-' :
                                toolStore.formatMoney(item.horde.total_craft_cost) }}</td>
                            <td class="p-3 text-right font-mono font-bold"
                                :class="item.horde.total_profit > 0 ? 'text-green-400' : 'text-red-400'">{{
                                    item.horde.insufficient_supply ? '-' : toolStore.formatMoney(item.horde.total_profit) }}
                            </td>
                            <td class="p-3 text-right font-mono border-r border-gray-700"
                                :class="item.horde.roi > 0 ? 'text-green-400' : 'text-red-400'">{{
                                    item.horde.insufficient_supply ? '-' : item.horde.roi.toFixed(1) + '%' }}</td>
                        </template>
                        <template v-else>
                            <td colspan="3" class="p-3 text-center text-gray-600 border-r border-gray-700 italic">Not on
                                AH</td>
                        </template>
                        <template v-if="item.alliance">
                            <td class="p-3 text-right font-mono text-gray-400">{{ item.alliance.insufficient_supply ?
                                '-' : toolStore.formatMoney(item.alliance.total_craft_cost) }}</td>
                            <td class="p-3 text-right font-mono font-bold"
                                :class="item.alliance.total_profit > 0 ? 'text-green-400' : 'text-red-400'">{{
                                    item.alliance.insufficient_supply ? '-' :
                                toolStore.formatMoney(item.alliance.total_profit) }}</td>
                            <td class="p-3 text-right font-mono"
                                :class="item.alliance.roi > 0 ? 'text-green-400' : 'text-red-400'">{{
                                    item.alliance.insufficient_supply ? '-' : item.alliance.roi.toFixed(1) + '%' }}</td>
                        </template>
                        <template v-else>
                            <td colspan="3" class="p-3 text-center text-gray-600 italic">Not on AH</td>
                        </template>
                    </tr>

                    <tr v-if="expandedRows.has(item.name)" class="shadow-inner">
                        <td colspan="7" class="p-0">
                            <div class="grid grid-cols-1 md:grid-cols-2">

                                <!-- Horde Breakdown (Red Tint) -->
                                <div class="bg-red-900/10 p-4 border-r border-gray-700/50">
                                    <h4 class="text-red-400 font-bold text-sm mb-4 border-b border-red-900/30 pb-2">
                                        Horde Breakdown</h4>

                                    <!-- Summary Grid -->
                                    <div v-if="item.horde" class="text-xs mb-4">
                                        <template v-if="item.horde.insufficient_supply">
                                            <span class="text-yellow-500 font-medium">Missing Reagents to craft this
                                                many</span>
                                        </template>
                                        <template v-else>
                                            <!-- Current Row -->
                                            <div class="grid grid-cols-[50px_1fr_30px_1fr] gap-2 py-1 items-center">
                                                <span class="text-gray-500 text-right font-medium">Curr:</span>
                                                <span class="text-gray-300 text-right font-mono">{{
                                                    toolStore.formatMoney(item.horde.total_craft_cost) }}</span>
                                                <span class="text-gray-600 italic text-center text-[10px]">vs</span>
                                                <span class="text-green-400 text-right font-mono">{{
                                                    toolStore.formatMoney(item.horde.total_revenue) }}</span>
                                            </div>
                                            <!-- 7D Row -->
                                            <div
                                                class="grid grid-cols-[50px_1fr_30px_1fr] gap-2 py-1 items-center border-t border-gray-700/30">
                                                <span class="text-gray-500 text-right font-medium">7D Avg:</span>
                                                <span class="text-gray-400 text-right font-mono">{{
                                                    toolStore.formatMoney(get7dReagentCost(item.horde.reagent_details))
                                                    }}</span>
                                                <span class="text-gray-600 italic text-center text-[10px]">vs</span>
                                                <span class="text-green-400/70 text-right font-mono">{{
                                                    toolStore.formatMoney(item.horde.hist_output_price *
                                                    item.horde.quantity) }}</span>
                                            </div>
                                        </template>
                                    </div>

                                    <!-- Reagent Table -->
                                    <table v-if="item.horde && !item.horde.insufficient_supply"
                                        class="w-full text-xs text-left">
                                        <thead class="text-gray-500 border-b border-gray-700/50">
                                            <tr>
                                                <th class="pb-1 font-normal">Reagent</th>
                                                <th class="pb-1 font-normal text-right">Req</th>
                                                <th class="pb-1 font-normal text-right">Curr</th>
                                                <th class="pb-1 font-normal text-right">7d Avg</th>
                                                <th class="pb-1 font-normal text-right">Avail</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr v-for="r in item.horde.reagent_details" :key="r.name"
                                                class="border-b border-gray-700/20 last:border-0">
                                                <td class="py-1.5 text-gray-300 flex items-center">
                                                    {{ r.name }}
                                                    <span v-if="r.method === 'Vendor'"
                                                        class="text-blue-400 text-[10px] ml-1">(Vendor)</span>
                                                    <span v-if="r.method === 'Craft'"
                                                        class="text-purple-400 text-[10px] font-bold ml-1"
                                                        title="Cheaper to craft than buy on AH">[C]</span>
                                                </td>
                                                <td class="py-1.5 text-right text-gray-400">{{ r.req }}</td>
                                                <td class="py-1.5 text-right font-mono"
                                                    :class="r.current_price > r.avg_price ? 'text-red-400' : 'text-green-400'">
                                                    {{
                                                    toolStore.formatMoney(r.current_price) }}</td>
                                                <td class="py-1.5 text-right font-mono text-gray-500">{{
                                                    toolStore.formatMoney(r.avg_price)
                                                    }}</td>
                                                <td class="py-1.5 text-right text-gray-500">{{ r.available }}</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>

                                <!-- Alliance Breakdown (Blue Tint) -->
                                <div class="bg-blue-900/10 p-4">
                                    <h4 class="text-blue-400 font-bold text-sm mb-4 border-b border-blue-900/30 pb-2">
                                        Alliance Breakdown
                                    </h4>

                                    <!-- Summary Grid -->
                                    <div v-if="item.alliance" class="text-xs mb-4">
                                        <template v-if="item.alliance.insufficient_supply">
                                            <span class="text-yellow-500 font-medium">Missing Reagents to craft this
                                                many</span>
                                        </template>
                                        <template v-else>
                                            <!-- Current Row -->
                                            <div class="grid grid-cols-[50px_1fr_30px_1fr] gap-2 py-1 items-center">
                                                <span class="text-gray-500 text-right font-medium">Curr:</span>
                                                <span class="text-gray-300 text-right font-mono">{{
                                                    toolStore.formatMoney(item.alliance.total_craft_cost) }}</span>
                                                <span class="text-gray-600 italic text-center text-[10px]">vs</span>
                                                <span class="text-green-400 text-right font-mono">{{
                                                    toolStore.formatMoney(item.alliance.total_revenue) }}</span>
                                            </div>
                                            <!-- 7D Row -->
                                            <div
                                                class="grid grid-cols-[50px_1fr_30px_1fr] gap-2 py-1 items-center border-t border-gray-700/30">
                                                <span class="text-gray-500 text-right font-medium">7D Avg:</span>
                                                <span class="text-gray-400 text-right font-mono">{{
                                                    toolStore.formatMoney(get7dReagentCost(item.alliance.reagent_details))
                                                    }}</span>
                                                <span class="text-gray-600 italic text-center text-[10px]">vs</span>
                                                <span class="text-green-400/70 text-right font-mono">{{
                                                    toolStore.formatMoney(item.alliance.hist_output_price *
                                                    item.alliance.quantity) }}</span>
                                            </div>
                                        </template>
                                    </div>

                                    <!-- Reagent Table -->
                                    <table v-if="item.alliance && !item.alliance.insufficient_supply"
                                        class="w-full text-xs text-left">
                                        <thead class="text-gray-500 border-b border-gray-700/50">
                                            <tr>
                                                <th class="pb-1 font-normal">Reagent</th>
                                                <th class="pb-1 font-normal text-right">Req</th>
                                                <th class="pb-1 font-normal text-right">Curr</th>
                                                <th class="pb-1 font-normal text-right">7d Avg</th>
                                                <th class="pb-1 font-normal text-right">Avail</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr v-for="r in item.alliance.reagent_details" :key="r.name"
                                                class="border-b border-gray-700/20 last:border-0">
                                                <td class="py-1.5 text-gray-300 flex items-center">
                                                    {{ r.name }}
                                                    <span v-if="r.method === 'Vendor'"
                                                        class="text-blue-400 text-[10px] ml-1">(Vendor)</span>
                                                    <span v-if="r.method === 'Craft'"
                                                        class="text-purple-400 text-[10px] font-bold ml-1"
                                                        title="Cheaper to craft than buy on AH">[C]</span>
                                                </td>
                                                <td class="py-1.5 text-right text-gray-400">{{ r.req }}</td>
                                                <td class="py-1.5 text-right font-mono"
                                                    :class="r.current_price > r.avg_price ? 'text-red-400' : 'text-green-400'">
                                                    {{
                                                    toolStore.formatMoney(r.current_price) }}</td>
                                                <td class="py-1.5 text-right font-mono text-gray-500">{{
                                                    toolStore.formatMoney(r.avg_price)
                                                    }}</td>
                                                <td class="py-1.5 text-right text-gray-500">{{ r.available }}</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>

                            </div>
                        </td>
                    </tr>
                </template>
            </tbody>
        </table>
    </div>
</template>
<script setup>
import { ref, onMounted, watch } from 'vue'
import { useToolStore } from '~/stores/tool'
import ConsumablesStandard from '~/components/ConsumablesStandard.vue'

const toolStore = useToolStore()

const mergedConsumables = ref([])
const loading = ref(true)
const errorMsg = ref(null)
const craftQuantity = ref(1)

const loadConsumables = async () => {
  loading.value = true
  errorMsg.value = null
  const baseUrl = `http://127.0.0.1:8000/consumables?quantity=${craftQuantity.value}`
  
  try {
    const [hordeData, allianceData] = await Promise.all([
      toolStore.fetchWithCache(`${baseUrl}&faction=Horde`, true),
      toolStore.fetchWithCache(`${baseUrl}&faction=Alliance`, true)
    ])

    const mergedMap = new Map()
    hordeData.forEach(item => mergedMap.set(item.name, { ...item, horde: item, alliance: null }))
    allianceData.forEach(item => {
      if (mergedMap.has(item.name)) mergedMap.get(item.name).alliance = item
      else mergedMap.set(item.name, { ...item, horde: null, alliance: item })
    })

    mergedConsumables.value = Array.from(mergedMap.values())
  } catch (err) {
    errorMsg.value = "Failed to load recipes."
    console.error(err)
  } finally {
    loading.value = false
  }
}

watch(craftQuantity, loadConsumables)
onMounted(loadConsumables)
</script>

<template>
  <main class="p-8 w-full">
    <div class="max-w-7xl mx-auto">
      
      <!-- Header -->
      <div class="flex justify-between items-center mb-6">
        <div>
          <h1 class="text-3xl font-bold text-yellow-500">Raid Consumes Tracker</h1>
        </div>
        
        <div class="flex items-center space-x-3 bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
          <label class="text-sm text-gray-400">Craft Quantity:</label>
          <input type="number" v-model="craftQuantity" min="1" class="bg-gray-900 text-white w-20 px-2 py-1 rounded border border-gray-600 font-mono text-center" />
        </div>
      </div>
      
      <div v-if="loading" class="text-gray-400">Calculating market prices...</div>
      <div v-else-if="errorMsg" class="text-red-500">{{ errorMsg }}</div>

      <!-- Standard View Component -->
      <ConsumablesStandard 
        v-else
        :items="mergedConsumables" 
      />
      
    </div>
  </main>
</template>
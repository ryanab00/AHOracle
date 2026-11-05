<script setup>
import { ref, onMounted, watch } from 'vue'
import { useToolStore } from '~/stores/tool'
import { useFactionStore } from '~/stores/faction'
import ConsumablesStandard from '~/components/ConsumablesStandard.vue'

const toolStore = useToolStore()
const factionStore = useFactionStore()

const consumables = ref([])
const loading = ref(true)
const errorMsg = ref(null)

const loadConsumables = async () => {
  loading.value = true
  errorMsg.value = null
  const url = `http://127.0.0.1:8000/consumables?quantity=1&faction=${factionStore.current}`
  
  try {
    consumables.value = await toolStore.fetchWithCache(url, true)
  } catch (err) {
    errorMsg.value = "Failed to load recipes."
    console.error(err)
  } finally {
    loading.value = false
  }
}

// Re-fetch when the user toggles Horde/Alliance
watch(() => factionStore.current, loadConsumables)
onMounted(loadConsumables)
</script>

<template>
  <main class="p-8 w-full">
    <div class="max-w-7xl mx-auto">
      <div class="flex justify-between items-center mb-6">
        <div>
          <h1 class="text-3xl font-bold text-yellow-500">Raid Consumes Tracker</h1>
        </div>
      </div>
      <div v-if="loading" class="text-gray-400">Calculating market prices...</div>
      <div v-else-if="errorMsg" class="text-red-500">{{ errorMsg }}</div>
      <ConsumablesStandard v-else :items="consumables" />
    </div>
  </main>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useFactionStore } from '~/stores/faction'
import { useToolStore } from '~/stores/tool'

const factionStore = useFactionStore()
const toolStore = useToolStore()

// Now holds an object like { Horde: 16999999, Alliance: 16999998 }
const scanTimes = ref({ Horde: 0, Alliance: 0, Neutral: 0 })

const toggleFaction = () => {
  factionStore.setFaction(factionStore.current === 'Horde' ? 'Alliance' : 'Horde')
}

const factionClass = computed(() => 
  factionStore.current === 'Horde' ? 'faction-horde' : 'faction-alliance'
)

onMounted(async () => {
  try {
    const res = await fetch('http://127.0.0.1:8000/last_scan')
    scanTimes.value = await res.json()
  } catch (e) {
    console.error("Failed to fetch last scan time")
  }
})
</script>

<template>
  <div class="min-h-screen">
    <header class="bg-gray-800 border-b-2 p-4 flex justify-between items-center transition-colors duration-300" :class="factionClass">
      
      <!-- Left: Logo & Nav -->
      <div class="flex items-center space-x-8">
        <h1 class="text-2xl font-bold">AHOracle</h1>
        <nav class="flex space-x-6 text-sm font-medium">
            <NuxtLink to="/" class="text-gray-400 hover:text-white transition">Auction House</NuxtLink>
  <NuxtLink to="/professions" class="text-gray-400 hover:text-white transition">Professions</NuxtLink>
  <NuxtLink to="/consumables" class="text-gray-400 hover:text-white transition">Consumables</NuxtLink>
  <NuxtLink to="/arbitrage" class="text-gray-400 hover:text-white transition">Arbitrage</NuxtLink>
        </nav>
      </div>
      
      <!-- Right Side: Scan Times & Toggle -->
      <div class="flex items-center space-x-6">
        
        <!-- Individual Faction Scan Times -->
        <div class="flex flex-col items-end text-xs font-medium space-y-0.5">
          <div class="text-gray-400">
            Horde: <span class="text-red-400">{{ toolStore.formatTimeAgo(scanTimes.Horde) }}</span>
          </div>
          <div class="text-gray-400">
            Alliance: <span class="text-blue-400">{{ toolStore.formatTimeAgo(scanTimes.Alliance) }}</span>
          </div>
        </div>
        
        <!-- Toggle Button -->
        <button 
          @click="toggleFaction"
          class="px-6 py-1.5 rounded-md text-sm font-bold transition-all duration-300 border hover:scale-105"
          :class="factionClass"
        >
          {{ factionStore.current }}
        </button>
      </div>
      
    </header>

    <NuxtPage />
  </div>
</template>
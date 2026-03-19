<template>
  <el-container class="agents-view">
    <el-aside
      :width="agentStore.sidebarCollapsed ? '50px' : '240px'"
      class="agents-sidebar"
    >
      <AgentSidebar />
    </el-aside>
    <el-main class="agents-main">
      <MainPanel />
    </el-main>
  </el-container>
</template>

<script setup>
import { watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAgentStore } from '../stores/agent'
import { useDashboardStore } from '../stores/dashboard'
import AgentSidebar from '../components/AgentSidebar.vue'
import MainPanel from '../components/MainPanel.vue'

const route = useRoute()
const agentStore = useAgentStore()
const dashboardStore = useDashboardStore()

onMounted(() => {
  dashboardStore.loadAll()
  dashboardStore.startAutoRefresh(10000)
})

onUnmounted(() => {
  dashboardStore.stopAutoRefresh()
})

watch(
  () => route.params.name,
  async (name) => {
    if (name) {
      await agentStore.selectAgentByName(name)
    } else {
      agentStore.selectAgentByName(null)
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.agents-view {
  height: 100%;
  overflow: hidden;
}
.agents-sidebar {
  background: #f5f7fa;
  border-right: 1px solid #e4e7ed;
  overflow: hidden;
  padding: 0;
  transition: width 0.2s;
}
.agents-main {
  padding: 0;
  overflow: hidden;
}
</style>

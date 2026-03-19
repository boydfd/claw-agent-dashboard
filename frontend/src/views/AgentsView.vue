<template>
  <el-container class="agents-view">
    <el-aside width="300px" class="agents-sidebar">
      <Sidebar />
    </el-aside>
    <el-main class="agents-main">
      <FileViewer />
    </el-main>
  </el-container>
</template>

<script setup>
import { watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAgentStore } from '../stores/agent'
import { useDashboardStore } from '../stores/dashboard'
import Sidebar from '../components/Sidebar.vue'
import FileViewer from '../components/FileViewer.vue'

const route = useRoute()
const agentStore = useAgentStore()
const dashboardStore = useDashboardStore()

// Load dashboard data and start auto-refresh for sidebar status dots
onMounted(() => {
  dashboardStore.loadAll()
  dashboardStore.startAutoRefresh(10000)
})

onUnmounted(() => {
  dashboardStore.stopAutoRefresh()
})

// Watch route params and select agent
watch(
  () => route.params.name,
  async (name) => {
    if (name) {
      await agentStore.selectAgentByName(name)
    } else {
      agentStore.currentAgent = null
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
  overflow-y: auto;
  padding: 0;
}
.agents-main {
  padding: 0;
  overflow-y: auto;
  background: #fff;
}
</style>

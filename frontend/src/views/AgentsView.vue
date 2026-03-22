<template>
  <el-container class="agents-view">
    <!-- Desktop sidebar -->
    <el-aside
      v-if="!isMobile"
      :width="agentStore.sidebarCollapsed ? '50px' : '240px'"
      class="agents-sidebar"
    >
      <AgentSidebar />
    </el-aside>

    <!-- Mobile sidebar drawer -->
    <el-drawer
      v-if="isMobile"
      v-model="sidebarDrawerVisible"
      direction="ltr"
      :size="'80%'"
      :with-header="false"
      class="mobile-sidebar-drawer"
    >
      <AgentSidebar />
    </el-drawer>

    <el-main class="agents-main">
      <MainPanel />
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, watch, provide, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAgentStore } from '../stores/agent'
import { useDashboardStore } from '../stores/dashboard'
import { useResponsive } from '../composables/useResponsive'
import AgentSidebar from '../components/AgentSidebar.vue'
import MainPanel from '../components/MainPanel.vue'

const route = useRoute()
const agentStore = useAgentStore()
const dashboardStore = useDashboardStore()
const { isMobile } = useResponsive()

const sidebarDrawerVisible = ref(false)

// Provide drawer state for MainPanel trigger button
provide('sidebarDrawer', {
  open: () => { sidebarDrawerVisible.value = true },
  isMobile,
})

// Auto-close drawer when agent changes (mobile)
watch(() => route.params.name, async (name) => {
  if (name) {
    await agentStore.selectAgentByName(name)
  } else {
    agentStore.selectAgentByName(null)
  }
  // Close drawer after selection
  if (isMobile.value) {
    sidebarDrawerVisible.value = false
  }
}, { immediate: true })

onMounted(() => {
  dashboardStore.loadAll()
  dashboardStore.startAutoRefresh(10000)
})

onUnmounted(() => {
  dashboardStore.stopAutoRefresh()
})
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

<style>
/* el-drawer overrides (unscoped to reach Element Plus internals) */
.mobile-sidebar-drawer .el-drawer__body {
  padding: 0;
  overflow: hidden;
}
@media (max-width: 768px) {
  .mobile-sidebar-drawer {
    max-width: 300px;
  }
}
</style>

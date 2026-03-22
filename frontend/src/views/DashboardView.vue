<template>
  <div class="dashboard-view">
    <div class="dashboard-header">
      <h1>
        <el-icon><DataLine /></el-icon>
        System Dashboard
      </h1>
      <div class="header-actions">
        <el-tag :type="store.loading ? 'warning' : 'info'" size="small">
          <el-icon v-if="store.loading" class="is-loading"><Loading /></el-icon>
          {{ store.loading ? 'Refreshing...' : 'Auto-refresh 10s' }}
        </el-tag>
        <el-button size="small" @click="store.loadAll" :loading="store.loading">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- Card grid -->
    <div class="card-grid">
      <GatewayCard :gateway="store.gatewayStatus" />
      <SystemCard :system="store.systemMetrics" />
    </div>

    <AgentsOverviewCard :agents="store.allAgentsStatus" />

    <EventsCard :events="store.events" />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { DataLine, Loading, Refresh } from '@element-plus/icons-vue'
import { useDashboardStore } from '../stores/dashboard'
import GatewayCard from '../components/GatewayCard.vue'
import SystemCard from '../components/SystemCard.vue'
import EventsCard from '../components/EventsCard.vue'
import AgentsOverviewCard from '../components/AgentsOverviewCard.vue'

const store = useDashboardStore()

onMounted(() => {
  store.loadAll()
  store.startAutoRefresh(10000)
})

onUnmounted(() => {
  store.stopAutoRefresh()
})
</script>

<style scoped>
.dashboard-view {
  padding: 20px 24px;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dashboard-header h1 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 20px;
  color: var(--el-text-color-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 768px) {
  .dashboard-view {
    padding: 12px 16px;
  }
  .card-grid {
    grid-template-columns: 1fr;
  }
  .dashboard-header h1 {
    font-size: 17px;
  }
}
</style>

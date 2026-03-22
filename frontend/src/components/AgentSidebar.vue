<template>
  <div class="agent-sidebar" :class="{ collapsed: store.sidebarCollapsed }">
    <!-- Expanded state -->
    <template v-if="!store.sidebarCollapsed">
      <div class="sidebar-header">
        <span>{{ t('sidebar.agents') }}</span>
        <el-button
          text
          size="small"
          :title="t('sidebar.collapse')"
          @click="store.sidebarCollapsed = true"
        >
          <el-icon><DArrowLeft /></el-icon>
        </el-button>
      </div>

      <!-- Blueprint filter -->
      <div class="blueprint-filter" v-if="store.blueprintOptions.length > 0">
        <el-select
          v-model="store.selectedBlueprint"
          :placeholder="t('sidebar.allBlueprints')"
          clearable
          size="small"
        >
          <el-option
            v-for="bp in store.blueprintOptions"
            :key="bp"
            :label="bp"
            :value="bp"
          />
        </el-select>
      </div>

      <el-scrollbar>
        <div v-if="store.loading && store.filteredAgents.length === 0" class="loading-tip">
          <el-icon class="is-loading"><Loading /></el-icon> {{ t('sidebar.loading') }}
        </div>

        <div
          v-for="agent in store.filteredAgents"
          :key="agent.name"
          class="agent-item"
          :class="{ active: store.currentAgent?.name === agent.name }"
          @click="selectAgent(agent)"
        >
          <span class="agent-status-dot" :class="getAgentDotClass(agent.name)"></span>
          <span class="agent-name">{{ agent.display_name }}</span>
        </div>

        <div v-if="!store.loading && store.filteredAgents.length === 0" class="empty-tip">
          {{ t('sidebar.noAgents') }}
        </div>
      </el-scrollbar>
    </template>

    <!-- Collapsed state -->
    <template v-else>
      <div class="collapsed-header">
        <el-button
          text
          size="small"
          :title="t('sidebar.expand')"
          @click="store.sidebarCollapsed = false"
        >
          <el-icon><DArrowRight /></el-icon>
        </el-button>
      </div>

      <el-scrollbar>
        <div
          v-for="agent in store.filteredAgents"
          :key="agent.name"
          class="agent-dot-item"
          :class="{ active: store.currentAgent?.name === agent.name }"
          @click="selectAgent(agent)"
        >
          <el-tooltip :content="agent.display_name" placement="right" :show-after="300">
            <span class="agent-status-dot" :class="getAgentDotClass(agent.name)"></span>
          </el-tooltip>
        </div>
      </el-scrollbar>
    </template>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { DArrowLeft, DArrowRight, Loading } from '@element-plus/icons-vue'
import { useAgentStore } from '../stores/agent'
import { useDashboardStore } from '../stores/dashboard'

const router = useRouter()
const { t } = useI18n()
const store = useAgentStore()
const dashboardStore = useDashboardStore()

function selectAgent(agent) {
  const shortName = agent.name.replace('workspace-', '')
  router.push(`/agents/${shortName}`)
}

function getAgentDotClass(agentName) {
  if (!dashboardStore.allAgentsStatus?.length) return 'dot-unknown'
  const shortName = agentName.replace('workspace-', '')
  const agentStatus = dashboardStore.allAgentsStatus.find(a => a.agent_name === shortName)
  if (!agentStatus) return 'dot-unknown'
  const map = {
    working: 'dot-working',
    active: 'dot-active',
    idle: 'dot-idle',
    dormant: 'dot-dormant',
    error: 'dot-error',
    unknown: 'dot-unknown',
  }
  return map[agentStatus.status] || 'dot-unknown'
}
</script>

<style scoped>
.agent-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}
.sidebar-header {
  padding: 12px 12px 12px 16px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid #e4e7ed;
  color: #303133;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.collapsed-header {
  padding: 10px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: center;
}
.blueprint-filter {
  padding: 8px 12px;
  border-bottom: 1px solid #ebeef5;
}
.blueprint-filter .el-select {
  width: 100%;
}
.loading-tip, .empty-tip {
  padding: 20px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
.agent-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
  border-bottom: 1px solid #ebeef5;
}
.agent-item:hover {
  background: #ecf5ff;
}
.agent-item.active {
  background: #e6f0ff;
  color: #409eff;
}
.agent-name {
  font-weight: 500;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.agent-dot-item {
  padding: 10px;
  cursor: pointer;
  display: flex;
  justify-content: center;
  border-bottom: 1px solid #ebeef5;
  transition: background 0.2s;
}
.agent-dot-item:hover {
  background: #ecf5ff;
}
.agent-dot-item.active {
  background: #e6f0ff;
}

/* Agent status dots */
.agent-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-active {
  background: #67c23a;
  box-shadow: 0 0 4px #67c23a;
}
.dot-working {
  background: #e6a23c;
  box-shadow: 0 0 4px #e6a23c;
  animation: dot-pulse 1.5s ease-in-out infinite;
}
@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 4px #e6a23c; }
  50% { box-shadow: 0 0 8px #e6a23c; }
}
.dot-idle {
  background: #909399;
}
.dot-dormant {
  background: #c0c4cc;
}
.dot-error {
  background: #f56c6c;
  box-shadow: 0 0 4px #f56c6c;
}
.dot-unknown {
  background: #dcdfe6;
}

/* Mobile touch-friendly */
@media (max-width: 768px) {
  .agent-item {
    min-height: 44px;
    padding: 12px 16px;
  }
  .agent-dot-item {
    min-height: 44px;
  }
}
</style>

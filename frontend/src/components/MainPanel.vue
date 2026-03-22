<template>
  <div class="main-panel">
    <template v-if="store.currentAgent">
      <!-- Tab bar -->
      <div class="tab-bar">
        <!-- Mobile sidebar trigger -->
        <div
          v-if="sidebarDrawer?.isMobile?.value"
          class="tab-item sidebar-trigger"
          @click="sidebarDrawer.open()"
        >
          <el-icon :size="18"><Operation /></el-icon>
        </div>
        <div
          class="tab-item"
          :class="{ active: store.activeTab === 'sessions' }"
          @click="store.setActiveTab('sessions')"
        >
          {{ t('mainPanel.sessions') }}
        </div>
        <div
          class="tab-item"
          :class="{ active: store.activeTab === 'files' }"
          @click="store.setActiveTab('files')"
        >
          {{ t('mainPanel.files') }}
        </div>
        <div
          class="tab-item"
          :class="{ active: store.activeTab === 'changes' }"
          @click="store.setActiveTab('changes')"
        >
          {{ t('mainPanel.changes') }}
          <span v-if="store.pendingChangesCount > 0" class="badge">{{ store.pendingChangesCount }}</span>
        </div>
      </div>

      <!-- Tab content — v-show keeps both alive -->
      <div class="tab-content" v-show="store.activeTab === 'sessions'">
        <AgentSessions />
      </div>
      <div class="tab-content" v-show="store.activeTab === 'files'">
        <FilesPanel />
      </div>
      <div class="tab-content" v-show="store.activeTab === 'changes'">
        <AgentChangesPanel />
      </div>
    </template>

    <!-- No agent selected -->
    <div v-else class="empty-state">
      <!-- Mobile: show button to open sidebar -->
      <template v-if="sidebarDrawer?.isMobile?.value">
        <div class="empty-icon">📂</div>
        <p>{{ t('fileViewer.selectFile') }}</p>
        <el-button type="primary" style="margin-top: 12px" @click="sidebarDrawer.open()">
          {{ t('sidebar.agents') }}
        </el-button>
      </template>
      <template v-else>
        <div class="empty-icon">📂</div>
        <p>{{ t('fileViewer.selectFile') }}</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { Operation } from '@element-plus/icons-vue'
import { useAgentStore } from '../stores/agent'
import AgentSessions from './AgentSessions.vue'
import FilesPanel from './FilesPanel.vue'
import AgentChangesPanel from './AgentChangesPanel.vue'

const { t } = useI18n()
const store = useAgentStore()
const sidebarDrawer = inject('sidebarDrawer', null)
</script>

<style scoped>
.main-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}
.tab-bar {
  display: flex;
  border-bottom: 1px solid #e4e7ed;
  background: #fafafa;
  flex-shrink: 0;
}
.tab-item {
  padding: 10px 20px;
  font-size: 14px;
  color: #909399;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}
.tab-item:hover {
  color: #606266;
}
.tab-item.active {
  color: #409eff;
  border-bottom-color: #409eff;
}
.sidebar-trigger {
  border-right: 1px solid #e4e7ed;
  padding: 10px 14px;
  color: #606266;
}
.sidebar-trigger:hover {
  background: #f0f2f5;
  color: #409eff;
}
.badge {
  background: #f56c6c;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: 6px;
  min-width: 16px;
  text-align: center;
  display: inline-block;
  line-height: 16px;
}
.tab-content {
  flex: 1;
  overflow: hidden;
}
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
}
.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .tab-item {
    padding: 10px 14px;
    font-size: 13px;
    min-height: 44px;
    display: flex;
    align-items: center;
  }
}
</style>

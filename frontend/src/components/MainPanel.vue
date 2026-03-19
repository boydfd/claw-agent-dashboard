<template>
  <div class="main-panel">
    <template v-if="store.currentAgent">
      <!-- Tab bar -->
      <div class="tab-bar">
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
      </div>

      <!-- Tab content — v-show keeps both alive -->
      <div class="tab-content" v-show="store.activeTab === 'sessions'">
        <AgentSessions />
      </div>
      <div class="tab-content" v-show="store.activeTab === 'files'">
        <FilesPanel />
      </div>
    </template>

    <!-- No agent selected -->
    <div v-else class="empty-state">
      <div class="empty-icon">📂</div>
      <p>{{ t('fileViewer.selectFile') }}</p>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useAgentStore } from '../stores/agent'
import AgentSessions from './AgentSessions.vue'
import FilesPanel from './FilesPanel.vue'

const { t } = useI18n()
const store = useAgentStore()
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
</style>

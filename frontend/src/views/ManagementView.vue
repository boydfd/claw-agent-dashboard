<template>
  <div class="management-view">
    <div class="management-tabs">
      <span
        v-for="tab in tabs"
        :key="tab.key"
        class="management-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ t(`management.${tab.key}`) }}
      </span>
    </div>
    <div class="management-content">
      <VariablesPanel v-if="activeTab === 'variables'" />
      <BlueprintsPanel v-else-if="activeTab === 'blueprints'" />
      <div v-else class="coming-soon">
        <p>{{ t('management.comingSoon') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import VariablesPanel from '../components/VariablesPanel.vue'
import BlueprintsPanel from '../components/BlueprintsPanel.vue'

const { t } = useI18n()
const activeTab = ref('variables')
const tabs = [
  { key: 'variables' },
  { key: 'blueprints' },
  { key: 'skills' },
]
</script>

<style scoped>
.management-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.management-tabs {
  display: flex;
  padding: 0 20px;
  background: var(--bg-secondary, #1a1a2e);
  border-bottom: 1px solid var(--border-color, #333);
}
.management-tab {
  padding: 10px 18px;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}
.management-tab:hover {
  color: #999;
}
.management-tab.active {
  color: var(--primary-color, #e94560);
  border-bottom-color: var(--primary-color, #e94560);
  font-weight: bold;
}
.management-content {
  flex: 1;
  overflow: auto;
  padding: 20px;
}
.coming-soon {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #666;
  font-size: 16px;
}

@media (max-width: 768px) {
  .management-tab {
    padding: 8px 12px;
    font-size: 13px;
  }
  .management-content {
    padding: 12px;
  }
}
</style>

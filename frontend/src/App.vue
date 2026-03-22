<template>
  <el-config-provider :locale="elementLocale">
    <AppLayout />
    <SettingsDialog />
  </el-config-provider>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import en from 'element-plus/es/locale/lang/en'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import AppLayout from './components/AppLayout.vue'
import SettingsDialog from './components/SettingsDialog.vue'
import { useAgentStore } from './stores/agent'
import { useDashboardStore } from './stores/dashboard'
import { useSettingsStore } from './stores/settings'

const { locale } = useI18n()
const elementLocale = computed(() => locale.value === 'zh' ? zhCn : en)

const agentStore = useAgentStore()
const dashboardStore = useDashboardStore()
const settingsStore = useSettingsStore()

onMounted(() => {
  agentStore.loadAgents()
  agentStore.loadGlobalSkillSources()
  dashboardStore.loadAll()
  settingsStore.load()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Mobile responsive: dialog width */
@media (max-width: 768px) {
  .el-dialog {
    width: 90vw !important;
    max-width: 560px;
  }
}
</style>

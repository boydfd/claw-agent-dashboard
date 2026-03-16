<template>
  <el-container class="app-layout">
    <!-- Header -->
    <el-header class="app-header">
      <div class="header-left">
        <span class="logo">🤖 {{ t('app.title') }}</span>
        <nav class="header-nav">
          <router-link
            to="/dashboard"
            class="nav-tab"
            :class="{ active: isDashboard }"
          >
            <el-icon><DataLine /></el-icon>
            {{ t('app.dashboard') }}
          </router-link>
          <router-link
            to="/agents"
            class="nav-tab"
            :class="{ active: isAgents }"
          >
            <el-icon><Monitor /></el-icon>
            {{ t('app.agents') }}
          </router-link>
          <router-link
            to="/management"
            class="nav-tab"
            :class="{ active: isManagement }"
          >
            <el-icon><Setting /></el-icon>
            {{ t('management.title') }}
          </router-link>
        </nav>
      </div>
      <div class="header-right">
        <el-button text class="lang-btn" @click="toggleLocale">
          {{ locale === 'en' ? '中文' : 'EN' }}
        </el-button>
        <el-button :icon="Setting" circle @click="settingsStore.openDialog()" />
      </div>
    </el-header>

    <div class="app-body">
      <router-view />
    </div>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Setting, DataLine, Monitor } from '@element-plus/icons-vue'
import { useSettingsStore } from '../stores/settings'

const route = useRoute()
const settingsStore = useSettingsStore()
const { t, locale } = useI18n()

const isDashboard = computed(() => route.path === '/dashboard')
const isAgents = computed(() => route.path.startsWith('/agents'))
const isManagement = computed(() => route.path.startsWith('/management'))

// Sync <html lang> on initial load from saved locale
onMounted(() => {
  document.documentElement.lang = locale.value === 'zh' ? 'zh-CN' : 'en'
})

function toggleLocale() {
  const next = locale.value === 'en' ? 'zh' : 'en'
  locale.value = next
  localStorage.setItem('locale', next)
  document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en'
}
</script>

<style scoped>
.app-layout {
  height: 100vh;
  flex-direction: column;
}
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1a1a2e;
  color: #fff;
  height: 52px !important;
  padding: 0 20px;
  border-bottom: 1px solid #16213e;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 24px;
}
.header-left .logo {
  font-size: 18px;
  font-weight: 600;
}
.header-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}
.nav-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  transition: all 0.2s;
  cursor: pointer;
}
.nav-tab:hover {
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.08);
}
.nav-tab.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.15);
  font-weight: 500;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.lang-btn {
  color: rgba(255, 255, 255, 0.7) !important;
  font-size: 13px;
  font-weight: 500;
}
.lang-btn:hover {
  color: #fff !important;
}
.app-body {
  flex: 1;
  overflow: hidden;
}
</style>

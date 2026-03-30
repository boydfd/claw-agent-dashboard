<template>
  <el-container class="app-layout">
    <!-- Header -->
    <el-header class="app-header">
      <div class="header-left">
        <span class="logo">🤖 {{ t('app.title') }}</span>
        <!-- Desktop nav -->
        <nav v-if="!isMobile" class="header-nav">
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
          <router-link
            to="/security"
            class="nav-tab"
            :class="{ active: isSecurity }"
          >
            <el-icon><Lock /></el-icon>
            {{ t('app.security') }}
          </router-link>
        </nav>
      </div>
      <!-- Desktop right buttons -->
      <div v-if="!isMobile" class="header-right">
        <el-button text class="lang-btn" @click="toggleLocale">
          {{ locale === 'en' ? '中文' : 'EN' }}
        </el-button>
        <el-button :icon="Setting" circle @click="settingsStore.openDialog()" />
      </div>
      <!-- Mobile hamburger -->
      <el-button
        v-if="isMobile"
        text
        class="mobile-menu-btn"
        @click="mobileMenuOpen = !mobileMenuOpen"
      >
        <el-icon :size="22"><Close v-if="mobileMenuOpen" /><MenuIcon v-else /></el-icon>
      </el-button>
    </el-header>

    <!-- Mobile dropdown panel -->
    <div v-if="isMobile && mobileMenuOpen" class="mobile-nav-backdrop" @click="mobileMenuOpen = false"></div>
    <Transition name="slide-down">
      <div v-if="isMobile && mobileMenuOpen" class="mobile-nav-panel">
        <router-link to="/dashboard" class="mobile-nav-item" :class="{ active: isDashboard }">
          <el-icon><DataLine /></el-icon>
          {{ t('app.dashboard') }}
        </router-link>
        <router-link to="/agents" class="mobile-nav-item" :class="{ active: isAgents }">
          <el-icon><Monitor /></el-icon>
          {{ t('app.agents') }}
        </router-link>
        <router-link to="/management" class="mobile-nav-item" :class="{ active: isManagement }">
          <el-icon><Setting /></el-icon>
          {{ t('management.title') }}
        </router-link>
        <router-link to="/security" class="mobile-nav-item" :class="{ active: isSecurity }">
          <el-icon><Lock /></el-icon>
          {{ t('app.security') }}
        </router-link>
        <div class="mobile-nav-divider"></div>
        <div class="mobile-nav-actions">
          <el-button text class="lang-btn" @click="toggleLocale">
            {{ locale === 'en' ? '中文' : 'EN' }}
          </el-button>
          <el-button :icon="Setting" circle @click="settingsStore.openDialog(); mobileMenuOpen = false" />
        </div>
      </div>
    </Transition>

    <div class="app-body">
      <router-view />
    </div>
  </el-container>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Setting, DataLine, Monitor, Menu as MenuIcon, Close, Lock } from '@element-plus/icons-vue'
import { useSettingsStore } from '../stores/settings'
import { useResponsive } from '../composables/useResponsive'

const route = useRoute()
const settingsStore = useSettingsStore()
const { t, locale } = useI18n()
const { isMobile } = useResponsive()

const isDashboard = computed(() => route.path === '/dashboard')
const isAgents = computed(() => route.path.startsWith('/agents'))
const isManagement = computed(() => route.path.startsWith('/management'))
const isSecurity = computed(() => route.path.startsWith('/security'))

const mobileMenuOpen = ref(false)

// Auto-close mobile menu on navigation
watch(() => route.path, () => {
  mobileMenuOpen.value = false
})

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
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}
/* Mobile header */
.mobile-menu-btn {
  color: #fff !important;
}
.mobile-nav-backdrop {
  position: fixed;
  top: 52px;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 99;
}
.mobile-nav-panel {
  position: absolute;
  top: 52px;
  left: 0;
  right: 0;
  background: #1a1a2e;
  z-index: 100;
  padding: 8px 0;
  border-bottom: 1px solid #16213e;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
.mobile-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  font-size: 15px;
  min-height: 44px;
  transition: background 0.15s;
}
.mobile-nav-item:hover,
.mobile-nav-item.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}
.mobile-nav-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: 4px 16px;
}
.mobile-nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
}
/* Slide transition */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-8px);
  opacity: 0;
}
</style>

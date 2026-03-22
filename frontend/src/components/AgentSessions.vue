<template>
  <div class="agent-sessions">
    <!-- Status bar -->
    <div class="status-bar">
      <div class="status-bar-left">
        <span class="status-dot" :class="agentDotClass"></span>
        <h2>{{ agentDisplayName }}</h2>
        <el-tag :type="statusTagType" size="small">{{ detail?.agent?.status_label || '—' }}</el-tag>
      </div>
      <div class="status-bar-right">
        <el-tag :type="refreshing ? 'warning' : 'info'" size="small">
          <el-icon v-if="refreshing" class="is-loading"><Loading /></el-icon>
          {{ refreshing ? t('agentSessions.refreshing') : t('agentSessions.updated', { time: lastUpdated }) }}
        </el-tag>
        <el-button size="small" @click="refresh" :loading="refreshing">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <div v-if="!detail" class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      {{ t('agentSessions.loadingStatus') }}
    </div>

    <!-- Sessions split pane -->
    <template v-else>
      <div v-if="detail.agent.sessions.length" class="split-pane" :class="{ 'mobile-layout': isMobile }">
        <!-- Left: Session list (desktop always, mobile when no session selected) -->
        <div
          v-if="!isMobile || !store.selectedSessionId"
          class="session-list-panel"
          :style="!isMobile ? { width: leftPanelWidth + 'px' } : {}"
        >
          <div class="session-list-header">
            <span class="session-list-title">{{ t('agentSessions.sessions') }}</span>
            <div style="display: flex; gap: 6px;">
              <el-button size="small" @click="openSwitchModel">{{ t('agentSessions.switchModel') }}</el-button>
              <el-button size="small" type="primary" :icon="Plus" @click="openNewSession">{{ t('agentSessions.newBtn') }}</el-button>
            </div>
          </div>
          <div v-if="store.sessionSearchEnabled" class="session-search-box">
            <el-input
              v-model="store.sessionSearchQuery"
              :placeholder="t('search.sessionPlaceholder')"
              :prefix-icon="Search"
              clearable
              size="small"
              @keyup.enter="handleSessionSearch"
              @clear="store.clearSessionSearch()"
            />
          </div>
          <!-- Session search results -->
          <div v-if="store.sessionSearchResults" class="session-list-scroll">
            <div v-if="store.sessionSearchLoading" class="search-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              {{ t('search.searching') }}
            </div>
            <div v-else-if="store.sessionSearchResults.total_matches === 0" class="search-empty">
              {{ t('search.sessionNoResults') }}
            </div>
            <div v-else class="session-search-results">
              <div class="search-summary">
                {{ t('search.sessionMatchCount', { count: store.sessionSearchResults.total_matches }) }}
              </div>
              <div
                v-for="(result, idx) in store.sessionSearchResults.results"
                :key="idx"
                class="session-search-item"
                @click="openSessionSearchResult(result)"
              >
                <div class="ssr-header">
                  <el-tag size="small" type="info">{{ result.channel }}</el-tag>
                  <el-tag size="small">{{ result.chat_type }}</el-tag>
                  <el-tag size="small" :type="result.role === 'user' ? '' : 'success'">{{ result.role }}</el-tag>
                </div>
                <div class="ssr-content" v-html="highlightSnippet(result.content_snippet, store.sessionSearchQuery)"></div>
                <div class="ssr-time">{{ formatTimestamp(result.timestamp) }}</div>
              </div>
            </div>
          </div>
          <!-- Normal session list -->
          <div v-else class="session-list-scroll">
            <div
              v-for="sess in detail.agent.sessions"
              :key="sess.session_id"
              class="session-card-compact"
              :class="{
                selected: store.selectedSessionId === sess.session_id,
                aborted: sess.aborted,
              }"
              @click="onSelectSession(sess)"
            >
              <div class="sc-header">
                <span class="status-dot" :class="sessionDotClass(sess)"></span>
                <span class="sc-channel">{{ sess.channel }}</span>
                <el-tag size="small" type="info" class="sc-type">{{ sess.chat_type }}</el-tag>
                <el-tag v-if="sess.aborted" type="danger" size="small">{{ t('agentSessions.aborted') }}</el-tag>
              </div>
              <div class="sc-meta">
                <span class="sc-age">{{ t('agentSessions.ago', { time: sess.age_human }) }}</span>
                <span v-if="sess.model" class="sc-model mono">{{ shortModel(sess.model, sess.provider) }}</span>
              </div>
              <div class="sc-stats" v-if="sess.total_tokens > 0">
                <span class="mono">{{ formatTokens(sess.total_tokens) }} {{ t('agentSessions.tokens') }}</span>
                <span v-if="sess.turns > 0">{{ t('agentSessions.turns', { n: sess.turns }) }}</span>
                <span v-if="sess.cache_rate > 0" class="cache-rate" :class="cacheRateClass(sess.cache_rate)">
                  {{ t('agentSessions.cacheRate', { n: sess.cache_rate }) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Draggable divider (desktop only) -->
        <div v-if="!isMobile" class="split-divider" @mousedown="startDrag">
          <div class="divider-line"></div>
        </div>

        <!-- Right: Message content (desktop always, mobile when session selected) -->
        <div
          v-if="!isMobile || store.selectedSessionId"
          class="message-panel"
        >
          <template v-if="store.selectedSessionId">
            <!-- Mobile back button + action buttons -->
            <div v-if="isMobile" class="mobile-back-bar">
              <el-button text @click="mobileBackToList">
                <el-icon><ArrowLeft /></el-icon> {{ t('agentSessions.sessions') }}
              </el-button>
              <div class="mobile-back-actions">
                <el-button size="small" @click="openSwitchModel">{{ t('agentSessions.switchModel') }}</el-button>
                <el-button size="small" type="primary" :icon="Plus" @click="openNewSession">{{ t('agentSessions.newBtn') }}</el-button>
              </div>
            </div>
            <SessionMessages
              :messages="currentMessages"
              :total="currentTotal"
              :current-page="store.sessionPage"
              :page-size="store.sessionPageSize"
              :loading="currentLoading"
              :target-message-index="store.targetMessageIndex"
              :session-key="store.selectedSessionKey || ''"
              :agent-name="agentName"
              :session-status="currentSessionStatus"
              @page-change="onPageChange"
              @highlight-done="store.targetMessageIndex = null"
            />
          </template>
          <div v-else class="empty-panel">
            <el-icon :size="32"><ChatDotRound /></el-icon>
            <span>{{ t('agentSessions.selectSession') }}</span>
          </div>
        </div>
      </div>

      <!-- No sessions -->
      <div v-else class="empty-tip">
        {{ t('agentSessions.noSessions') }}
        <div style="margin-top: 12px;">
          <el-button size="small" type="primary" @click="openNewSession">
            <el-icon><Plus /></el-icon>
            {{ t('agentSessions.newSession') }}
          </el-button>
        </div>
      </div>
    </template>

    <!-- New Session Confirm Dialog -->
    <el-dialog
      v-model="newSessionVisible"
      :title="t('agentSessions.newSession')"
      width="400px"
      :close-on-click-modal="false"
      @close="closeNewSession"
    >
      <p>{{ t('agentSessions.newSessionConfirm') }}</p>
      <template #footer>
        <el-button @click="closeNewSession">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="newSessionLoading"
          @click="submitNewSession"
        >
          {{ t('agentSessions.confirm') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Switch Model Dialog -->
    <el-dialog
      v-model="switchModelVisible"
      :title="t('agentSessions.switchModel')"
      width="450px"
      :close-on-click-modal="false"
      @close="closeSwitchModel"
    >
      <el-form label-position="top">
        <el-form-item :label="t('agentSessions.selectModel')">
          <el-select
            v-model="switchModelId"
            :placeholder="t('agentSessions.selectModel')"
            style="width: 100%;"
          >
            <el-option
              v-for="m in store.availableModels"
              :key="m.id"
              :label="m.name + (m.primary ? ' ' + t('agentSessions.defaultModel') : '')"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeSwitchModel">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="switchModelLoading"
          :disabled="!switchModelId"
          @click="submitSwitchModel"
        >
          {{ t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { Loading, Refresh, ChatDotRound, Plus, Search, ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '../stores/agent'
import SessionMessages from './SessionMessages.vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

const store = useAgentStore()

import { useResponsive } from '../composables/useResponsive'
const { isMobile } = useResponsive()

// Split pane state
const leftPanelWidth = ref(340)
let isDragging = false
let dragStartX = 0
let dragStartWidth = 0

// New session dialog state
const newSessionVisible = ref(false)
const newSessionLoading = ref(false)

// Switch model dialog state
const switchModelVisible = ref(false)
const switchModelLoading = ref(false)
const switchModelId = ref('')

const detail = computed(() => store.agentDetail)
const refreshing = computed(() => store.statusLoading)

const agentDisplayName = computed(() => {
  return store.currentAgent?.display_name || store.currentAgent?.name || 'Agent'
})

const lastUpdated = computed(() => {
  if (!detail.value?.timestamp) return '—'
  const diff = Math.round((Date.now() - detail.value.timestamp) / 1000)
  if (diff < 5) return t('agentSessions.justNow')
  if (diff < 60) return t('agentSessions.secondsAgo', { n: diff })
  return t('agentSessions.minutesAgo', { n: Math.round(diff / 60) })
})

const agentDotClass = computed(() => {
  if (!detail.value) return 'dot-unknown'
  const map = {
    working: 'dot-working',
    active: 'dot-active',
    idle: 'dot-idle',
    dormant: 'dot-dormant',
    error: 'dot-error',
    unknown: 'dot-unknown',
  }
  return map[detail.value.agent.status] || 'dot-unknown'
})

const statusTagType = computed(() => {
  if (!detail.value) return 'info'
  const map = {
    working: '',
    active: 'success',
    idle: '',
    dormant: 'info',
    error: 'danger',
    unknown: 'info',
  }
  return map[detail.value.agent.status] || 'info'
})

// Session messages computed
const currentMessages = computed(() => {
  const sid = store.selectedSessionId
  return sid ? (store.sessionMessages[sid]?.messages || []) : []
})

const currentTotal = computed(() => {
  const sid = store.selectedSessionId
  return sid ? (store.sessionMessages[sid]?.total || 0) : 0
})

const currentLoading = computed(() => {
  const sid = store.selectedSessionId
  return sid ? (store.sessionMessagesLoading[sid] || false) : false
})

const agentName = computed(() => store.currentAgent?.name?.replace('workspace-', '') || '')

const currentSessionStatus = computed(() => {
  const sid = store.selectedSessionId
  if (!sid) return ''
  const sessions = store.sessions?.[store.currentAgent?.name] || []
  const sess = sessions.find(s => s.session_id === sid)
  if (!sess) return ''
  return sess.has_lock ? 'working' : ''
})

function sessionDotClass(sess) {
  if (sess.aborted) return 'dot-error'
  if (sess.has_lock) return 'dot-working'
  if (sess.jsonl_age_seconds != null && sess.jsonl_age_seconds < 30) return 'dot-active'
  if (sess.age_seconds < 120) return 'dot-active'
  if (sess.age_seconds < 600) return 'dot-idle'
  return 'dot-dormant'
}

function cacheRateClass(rate) {
  if (rate >= 80) return 'cache-excellent'
  if (rate >= 50) return 'cache-good'
  if (rate >= 20) return 'cache-fair'
  return 'cache-low'
}

function formatTokens(count) {
  if (count >= 1_000_000) return (count / 1_000_000).toFixed(1) + 'M'
  if (count >= 1000) return Math.round(count / 1000) + 'k'
  return String(count)
}

function shortModel(model, provider) {
  if (!model) return ''
  const short = model.replace(/^claude-/, '')
  if (provider) return `${provider}/${short}`
  return short
}

function onSelectSession(sess) {
  store.selectSession(sess.session_id, sess.session_key)
}

function mobileBackToList() {
  store.selectedSessionId = null
}

function onPageChange(page) {
  const sid = store.selectedSessionId
  if (sid) {
    store.loadSessionPage(sid, page, false)
  }
}

function refresh() {
  store.loadAgentDetail()
}

// New session dialog
async function openNewSession() {
  newSessionVisible.value = true
}

function closeNewSession() {
  newSessionVisible.value = false
  newSessionLoading.value = false
}

async function submitNewSession() {
  const agentName = store.currentAgent?.name?.replace('workspace-', '') || ''
  if (!agentName) return

  // Native /new parity for Nextcloud: always reset the current channel session first.
  // Priority:
  // 1) nextcloud-talk group session
  // 2) currently selected session
  // 3) null (detached fallback)
  const sessions = detail.value?.agent?.sessions || []
  const nextcloudGroup = sessions.find(
    s => s?.session_key?.includes('nextcloud-talk:group:')
  )
  const selected = sessions.find(s => s.session_id === store.selectedSessionId)
  const sessionKey = nextcloudGroup?.session_key || selected?.session_key || null

  newSessionLoading.value = true
  try {
    await store.createSession(agentName, sessionKey)
    ElMessage.success(t('agentSessions.sessionCreated'))
    closeNewSession()
    store.loadAgentDetail()
  } catch (e) {
    console.error('Failed to create session:', e)
    ElMessage.error(t('agentSessions.createFailed') + ': ' + (e.response?.data?.detail || e.message))
  } finally {
    newSessionLoading.value = false
  }
}

// Switch model dialog
async function openSwitchModel() {
  if (!store.selectedSessionId) {
    ElMessage.warning(t('agentSessions.selectSessionFirst'))
    return
  }
  if (!store.availableModels.length) {
    await store.loadModels()
  }
  switchModelId.value = store.defaultModel || ''
  switchModelVisible.value = true
}

function closeSwitchModel() {
  switchModelVisible.value = false
  switchModelId.value = ''
  switchModelLoading.value = false
}

async function submitSwitchModel() {
  if (!switchModelId.value) return
  const agentName = store.currentAgent?.name?.replace('workspace-', '') || ''
  if (!agentName) return

  const sessions = detail.value?.agent?.sessions || []
  const sess = sessions.find(s => s.session_id === store.selectedSessionId)
  if (!sess) {
    ElMessage.error(t('agentSessions.selectSessionFirst'))
    return
  }

  switchModelLoading.value = true
  try {
    await store.switchModel(agentName, switchModelId.value, sess.session_key)
    ElMessage.success(t('agentSessions.switchSuccess'))
    closeSwitchModel()
    store.loadAgentDetail()
  } catch (e) {
    console.error('Failed to switch model:', e)
    ElMessage.error(t('agentSessions.switchFailed') + ': ' + (e.response?.data?.detail || e.message))
  } finally {
    switchModelLoading.value = false
  }
}

function handleSessionSearch() {
  if (store.sessionSearchQuery.trim()) {
    store.searchSessionMessages(store.sessionSearchQuery)
  }
}

function openSessionSearchResult(result) {
  store.selectedSessionId = result.session_id
  const page = Math.floor(result.message_index / store.sessionPageSize) + 1
  store.targetMessageIndex = result.message_index
  store.loadSessionPage(result.session_id, page, false)
}

function highlightSnippet(text, query) {
  if (!text || !query) return text || ''
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escaped})`, 'gi')
  return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(regex, '<mark>$1</mark>')
}

function formatTimestamp(ts) {
  if (!ts) return ''
  const date = new Date(ts)
  const now = new Date()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}h ago`
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// Drag to resize split pane
function startDrag(e) {
  isDragging = true
  dragStartX = e.clientX
  dragStartWidth = leftPanelWidth.value
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onDrag(e) {
  if (!isDragging) return
  const delta = e.clientX - dragStartX
  const newWidth = Math.max(200, Math.min(600, dragStartWidth + delta))
  leftPanelWidth.value = newWidth
}

function stopDrag() {
  isDragging = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onMounted(() => {
  store.startStatusAutoRefresh(10000)
  store.checkSearchCapabilities()
})

onUnmounted(() => {
  store.stopStatusAutoRefresh()
  stopDrag()
})
</script>

<style scoped>
.agent-sessions {
  padding: 16px 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* Status bar */
.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.status-bar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-bar-left h2 {
  margin: 0;
  font-size: 18px;
  color: var(--el-text-color-primary);
}

.status-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 40px;
  justify-content: center;
  color: var(--el-text-color-secondary);
}

/* ========== Split Pane Layout ========== */
.split-pane {
  display: flex;
  flex: 1;
  min-height: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-bg-color-overlay);
}

.session-list-panel {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
}

.session-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}

.session-list-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.session-list-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.session-card-compact {
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 4px;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s;
  border: 1px solid transparent;
}

.session-card-compact:last-child { margin-bottom: 0; }
.session-card-compact:hover { background: var(--el-fill-color-light); }

.session-card-compact.selected {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.session-card-compact.aborted {
  border-left: 3px solid var(--el-color-danger);
}

.sc-header { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.sc-channel { font-weight: 600; font-size: 13px; color: var(--el-text-color-primary); }
.sc-type { font-size: 11px; }
.sc-meta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--el-text-color-secondary); margin-bottom: 2px; }
.sc-age { color: var(--el-text-color-placeholder); }
.sc-model { color: var(--el-text-color-secondary); font-size: 10px; }
.sc-stats { display: flex; align-items: center; gap: 8px; font-size: 10px; color: var(--el-text-color-placeholder); }

/* Draggable divider */
.split-divider {
  width: 6px;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--el-fill-color-lighter);
  transition: background 0.15s;
}
.split-divider:hover { background: var(--el-color-primary-light-8); }
.divider-line { width: 2px; height: 32px; border-radius: 1px; background: var(--el-border-color); }
.split-divider:hover .divider-line { background: var(--el-color-primary); }

.message-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; }

.empty-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--el-text-color-placeholder);
  font-size: 14px;
}

.mono { font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace; }

/* Status dots */
.status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.dot-active { background: var(--el-color-success); box-shadow: 0 0 6px var(--el-color-success); }
.dot-working { background: var(--el-color-warning); box-shadow: 0 0 6px var(--el-color-warning); animation: dot-pulse 1.5s ease-in-out infinite; }
@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 6px var(--el-color-warning); }
  50% { box-shadow: 0 0 12px var(--el-color-warning); }
}
.dot-idle { background: var(--el-text-color-secondary); }
.dot-dormant { background: var(--el-text-color-disabled); }
.dot-error { background: var(--el-color-danger); box-shadow: 0 0 6px var(--el-color-danger); }
.dot-unknown { background: var(--el-text-color-placeholder); }

/* Cache rate colors */
.cache-rate { font-weight: 600; }
.cache-excellent { color: var(--el-color-success); }
.cache-good { color: var(--el-color-primary); }
.cache-fair { color: var(--el-color-warning); }
.cache-low { color: var(--el-color-danger); }

.empty-tip { padding: 16px; text-align: center; color: var(--el-text-color-placeholder); }

.session-search-box {
  padding: 6px 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}
.search-loading, .search-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
.search-summary {
  padding: 6px 10px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.session-search-item {
  padding: 8px 10px;
  border-radius: 6px;
  margin: 2px 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.session-search-item:hover {
  background: var(--el-fill-color-light);
}
.ssr-header {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}
.ssr-content {
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ssr-content :deep(mark) {
  background: #ffd54f;
  color: #333;
  padding: 0 1px;
  border-radius: 2px;
}
.ssr-time {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}

/* Mobile two-step layout */
.split-pane.mobile-layout {
  flex-direction: column;
}
.split-pane.mobile-layout .session-list-panel {
  width: 100% !important;
  border-right: none;
  flex: 1;
}
.split-pane.mobile-layout .message-panel {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.mobile-back-bar {
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mobile-back-actions {
  display: flex;
  gap: 6px;
}

@media (max-width: 768px) {
  .agent-sessions {
    padding: 12px;
  }
  .status-bar {
    flex-wrap: wrap;
    gap: 8px;
  }
  .status-bar-left h2 {
    font-size: 15px;
  }
  .session-card-compact {
    min-height: 44px;
  }
}
</style>

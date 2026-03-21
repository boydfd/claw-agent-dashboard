<template>
  <div class="version-history-panel">
    <!-- Version list (left) + diff/preview (right) -->
    <div class="vh-layout">
      <!-- Left: version list -->
      <div class="vh-list-pane">
        <div class="vh-list-header">
          <span class="vh-title">{{ t('versionHistory.title') }}</span>
          <el-button size="small" text @click="$emit('close')">✕</el-button>
        </div>

        <div v-if="loading" class="vh-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ t('versionHistory.loading') }}</span>
        </div>

        <div v-else-if="versions.length === 0" class="vh-empty">
          {{ t('versionHistory.noHistory') }}
        </div>

        <div v-else class="vh-list-body">
          <div
            v-for="ver in versions"
            :key="ver.id"
            class="vh-item"
            :class="{ selected: selectedVersion?.id === ver.id }"
            @click="selectVersion(ver)"
          >
            <div class="vh-item-header">
              <span class="vh-item-num">v{{ ver.version_num }}</span>
              <span class="vh-item-time">{{ formatTime(ver.created_at) }}</span>
              <el-tag :type="sourceTagType(ver.source)" size="small">
                {{ ver.source }}
              </el-tag>
            </div>
            <div v-if="ver.commit_msg || ver.ai_summary" class="vh-item-summary">
              {{ ver.commit_msg || ver.ai_summary }}
            </div>
          </div>

          <!-- Load more -->
          <div v-if="hasMore" class="vh-load-more">
            <el-button text size="small" @click="$emit('load-more')">
              {{ t('versionHistory.loadMore') }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- Right: diff view -->
      <div class="vh-diff-pane">
        <template v-if="selectedVersion">
          <div class="vh-diff-header">
            <span class="vh-diff-title">
              v{{ selectedVersion.version_num }}
              <template v-if="compareTarget">
                → v{{ compareTarget.version_num }}
              </template>
            </span>
            <div class="vh-diff-actions">
              <el-button
                v-if="!showPreview"
                size="small"
                @click="doPreview"
                :loading="previewLoading"
              >{{ t('versionHistory.view') }}</el-button>
              <el-button
                v-if="showPreview"
                size="small"
                @click="showPreview = false"
              >{{ t('versionHistory.showDiff') }}</el-button>
              <el-popconfirm
                :title="t('versionHistory.confirmRestore', { num: selectedVersion.version_num })"
                @confirm="doRestore"
              >
                <template #reference>
                  <el-button size="small" type="warning" :loading="restoring">
                    {{ t('versionHistory.restore') }}
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>

          <!-- Preview mode -->
          <div v-if="showPreview" class="vh-preview-content">
            <pre class="vh-preview-pre">{{ previewContent }}</pre>
          </div>

          <!-- Diff mode -->
          <div v-else class="vh-diff-content">
            <div v-if="diffLoading" class="vh-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>
            <div v-else-if="diffLines.length === 0" class="vh-empty">
              {{ t('versionHistory.identicalContent') }}
            </div>
            <div v-else class="vh-diff-lines">
              <div
                v-for="(line, idx) in diffLines"
                :key="idx"
                class="diff-line"
                :class="line.type"
              >
                <span class="line-num old-num">{{ line.oldNum || '' }}</span>
                <span class="line-num new-num">{{ line.newNum || '' }}</span>
                <span class="line-prefix">{{ line.prefix }}</span>
                <span class="line-text">{{ line.text }}</span>
              </div>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="vh-empty">
            <p>{{ t('versionHistory.selectVersion') }}</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'

const props = defineProps({
  versions: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  hasMore: { type: Boolean, default: false },
  // Functions to fetch version content — passed by parent
  fetchContent: { type: Function, required: true },
  onRestore: { type: Function, required: true },
})

const emit = defineEmits(['close', 'load-more', 'restored'])

const { t, locale } = useI18n()
const selectedVersion = ref(null)
const compareTarget = ref(null)
const diffLines = ref([])
const diffLoading = ref(false)
const showPreview = ref(false)
const previewContent = ref('')
const previewLoading = ref(false)
const restoring = ref(false)

// When a version is selected, auto-compute diff against the latest
watch(() => props.versions, () => {
  // Reset selection when version list changes
  selectedVersion.value = null
  compareTarget.value = null
  diffLines.value = []
  showPreview.value = false
})

async function selectVersion(ver) {
  if (selectedVersion.value?.id === ver.id) {
    selectedVersion.value = null
    compareTarget.value = null
    diffLines.value = []
    showPreview.value = false
    return
  }

  selectedVersion.value = ver
  showPreview.value = false

  // Auto-diff: compare this version with the latest (first in list)
  const latest = props.versions[0]
  if (!latest || latest.id === ver.id) {
    // This IS the latest — show its content as preview
    compareTarget.value = null
    diffLines.value = []
    return
  }

  compareTarget.value = latest
  diffLoading.value = true
  try {
    const [oldContent, newContent] = await Promise.all([
      props.fetchContent(ver),
      props.fetchContent(latest),
    ])
    diffLines.value = computeDiff(oldContent, newContent)
  } catch (e) {
    ElMessage.error(t('versionHistory.diffFailed'))
    diffLines.value = []
  } finally {
    diffLoading.value = false
  }
}

async function doPreview() {
  if (!selectedVersion.value) return
  previewLoading.value = true
  try {
    previewContent.value = await props.fetchContent(selectedVersion.value)
    showPreview.value = true
  } catch (e) {
    ElMessage.error(t('versionHistory.fetchFailed'))
  } finally {
    previewLoading.value = false
  }
}

async function doRestore() {
  if (!selectedVersion.value) return
  restoring.value = true
  try {
    await props.onRestore(selectedVersion.value)
    ElMessage.success(t('versionHistory.restored', { num: selectedVersion.value.version_num }))
    selectedVersion.value = null
    compareTarget.value = null
    diffLines.value = []
    showPreview.value = false
    emit('restored')
  } catch (e) {
    ElMessage.error(t('versionHistory.restoreFailed') + ': ' + (e.response?.data?.detail || e.message || e))
  } finally {
    restoring.value = false
  }
}

function sourceTagType(source) {
  if (source === 'app' || source === 'dashboard') return 'success'
  if (source === 'external' || source === 'filesystem_sync') return 'warning'
  if (source === 'restore') return 'info'
  return ''
}

function formatTime(ts) {
  if (!ts) return ''
  const date = new Date(ts + 'Z')
  const now = new Date()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return t('versionHistory.justNow')
  if (diffMin < 60) return t('versionHistory.minutesAgo', { n: diffMin })
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return t('versionHistory.hoursAgo', { n: diffHour })
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 30) return t('versionHistory.daysAgo', { n: diffDay })
  return date.toLocaleDateString(locale.value === 'zh' ? 'zh-CN' : 'en-US')
}

// --- LCS-based diff computation (from AgentChangesPanel) ---

function computeLCS(a, b) {
  const m = a.length, n = b.length
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }
  const result = []
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      result.unshift({ aIdx: i - 1, bIdx: j - 1 })
      i--; j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }
  return result
}

function computeDiff(oldText, newText) {
  if (!oldText && !newText) return []
  const oldLines = (oldText || '').split('\n')
  const newLines = (newText || '').split('\n')

  if (!oldText) {
    return newLines.map((line, i) => ({
      type: 'add', prefix: '+', text: line, oldNum: null, newNum: i + 1
    }))
  }
  if (!newText) {
    return oldLines.map((line, i) => ({
      type: 'del', prefix: '-', text: line, oldNum: i + 1, newNum: null
    }))
  }

  const lcs = computeLCS(oldLines, newLines)
  const lines = []
  let oi = 0, ni = 0, li = 0

  while (oi < oldLines.length || ni < newLines.length) {
    if (li < lcs.length && oi === lcs[li].aIdx && ni === lcs[li].bIdx) {
      lines.push({ type: 'context', prefix: ' ', text: oldLines[oi], oldNum: oi + 1, newNum: ni + 1 })
      oi++; ni++; li++
    } else {
      if (oi < oldLines.length && (li >= lcs.length || oi < lcs[li].aIdx)) {
        lines.push({ type: 'del', prefix: '-', text: oldLines[oi], oldNum: oi + 1, newNum: null })
        oi++
      }
      if (ni < newLines.length && (li >= lcs.length || ni < lcs[li].bIdx)) {
        lines.push({ type: 'add', prefix: '+', text: newLines[ni], oldNum: null, newNum: ni + 1 })
        ni++
      }
    }
  }
  return lines
}
</script>

<style scoped>
.version-history-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border-color, #e4e7ed);
}
.vh-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Left pane: version list */
.vh-list-pane {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color, #e4e7ed);
  display: flex;
  flex-direction: column;
}
.vh-list-header {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color, #e4e7ed);
}
.vh-title {
  color: var(--text-primary, #303133);
}
.vh-list-body {
  flex: 1;
  overflow-y: auto;
}
.vh-item {
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color-light, #f0f0f0);
  transition: background 0.15s;
}
.vh-item:hover {
  background: var(--hover-bg, rgba(0, 0, 0, 0.03));
}
.vh-item.selected {
  background: var(--selected-bg, rgba(64, 158, 255, 0.08));
  border-left: 3px solid var(--primary-color, #409eff);
  padding-left: 9px;
}
.vh-item-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.vh-item-num {
  font-weight: 600;
  font-size: 13px;
  min-width: 28px;
}
.vh-item-time {
  font-size: 11px;
  color: var(--text-secondary, #909399);
  flex: 1;
}
.vh-item-summary {
  margin-top: 3px;
  font-size: 12px;
  color: var(--text-secondary, #909399);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Right pane: diff/preview */
.vh-diff-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.vh-diff-header {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.vh-diff-title {
  font-size: 13px;
  font-weight: 600;
}
.vh-diff-actions {
  display: flex;
  gap: 8px;
}
.vh-diff-content, .vh-preview-content {
  flex: 1;
  overflow: auto;
}

/* Diff lines — same style as AgentChangesPanel */
.vh-diff-lines {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 20px;
}
.diff-line {
  display: flex;
  white-space: pre;
}
.diff-line.add {
  background: rgba(46, 160, 67, 0.15);
}
.diff-line.del {
  background: rgba(248, 81, 73, 0.15);
}
.line-num {
  width: 40px;
  text-align: right;
  padding-right: 8px;
  color: var(--text-secondary, #909399);
  user-select: none;
  flex-shrink: 0;
}
.line-prefix {
  width: 16px;
  text-align: center;
  color: var(--text-secondary, #909399);
  flex-shrink: 0;
}
.line-text {
  flex: 1;
  overflow-x: auto;
}

/* Preview */
.vh-preview-pre {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Shared states */
.vh-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--text-secondary, #909399);
}
.vh-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: var(--text-secondary, #909399);
}
.vh-load-more {
  text-align: center;
  padding: 8px 0;
}
</style>

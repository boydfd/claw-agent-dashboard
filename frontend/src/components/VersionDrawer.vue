<template>
  <el-drawer
    :model-value="store.versionDrawerOpen"
    :title="t('versionDrawer.title')"
    direction="rtl"
    size="420px"
    :before-close="store.closeVersionDrawer"
    :append-to-body="true"
  >
    <template #header>
      <div class="drawer-header">
        <span>{{ t('versionDrawer.titleWithFile', { name: store.currentFile?.name }) }}</span>
      </div>
    </template>

    <!-- Diff view -->
    <div v-if="diffMode" class="diff-view">
      <div class="diff-header">
        <el-button size="small" @click="exitDiff">
          &larr; {{ t('versionDrawer.backToList') }}
        </el-button>
        <span class="diff-title">v{{ diffFrom }} vs v{{ diffTo }}</span>
      </div>
      <div class="diff-content">
        <div v-if="!store.versionDiff" class="diff-empty">{{ t('versionDrawer.identicalContent') }}</div>
        <pre v-else class="diff-pre"><template v-for="(line, i) in diffLines" :key="i"><span :class="lineClass(line)">{{ line }}
</span></template></pre>
      </div>
    </div>

    <!-- Preview mode -->
    <div v-else-if="previewContent !== null" class="preview-view">
      <div class="preview-header">
        <el-button size="small" @click="previewContent = null; previewNum = null">
          &larr; {{ t('versionDrawer.backToList') }}
        </el-button>
        <span class="preview-title">v{{ previewNum }} {{ t('versionDrawer.preview') }}</span>
      </div>
      <pre class="preview-content">{{ previewContent }}</pre>
    </div>

    <!-- Version list -->
    <div v-else>
      <div v-if="store.versionLoading" class="loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>{{ t('versionDrawer.loading') }}</span>
      </div>

      <div v-else-if="store.versionList.length === 0" class="empty-state">
        {{ t('versionDrawer.noHistory') }}
      </div>

      <div v-else class="version-list">
        <div
          v-for="ver in store.versionList"
          :key="ver.id"
          class="version-item"
          :class="{ expanded: expandedId === ver.id }"
          @click="toggleExpand(ver.id)"
        >
          <div class="version-header">
            <span class="version-num">v{{ ver.version_num }}</span>
            <span class="version-time">{{ formatTime(ver.created_at) }}</span>
            <el-tag
              :type="sourceTagType(ver.source)"
              size="small"
              class="source-tag"
            >
              {{ ver.source }}
            </el-tag>
            <span v-if="ver.likely_openclaw && ver.source === 'external'" class="openclaw-hint">🦞</span>
          </div>
          <div class="version-summary">
            <template v-if="ver.commit_msg">{{ ver.commit_msg }}</template>
            <template v-else-if="ver.ai_summary">{{ ver.ai_summary }}</template>
            <span v-else class="summary-pending">
              <el-icon class="is-loading"><Loading /></el-icon> {{ t('versionDrawer.generatingSummary') }}
            </span>
          </div>

          <!-- Expanded actions -->
          <div v-if="expandedId === ver.id" class="version-actions" @click.stop>
            <el-button size="small" @click="previewVersion(ver.id)">{{ t('versionDrawer.view') }}</el-button>
            <el-button size="small" @click="compareVersion(ver)">{{ t('versionDrawer.compare') }}</el-button>
            <el-popconfirm
              :title="t('versionDrawer.confirmRestore')"
              :confirm-button-text="t('versionDrawer.confirmRestoreBtn')"
              :cancel-button-text="t('common.cancel')"
              @confirm="doRestore(ver.id)"
            >
              <template #reference>
                <el-button size="small" type="warning" :loading="restoring">{{ t('versionDrawer.restore') }}</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>

        <!-- Load more -->
        <div v-if="store.versionList.length < store.versionTotal" class="load-more">
          <el-button text @click="loadMore">{{ t('versionDrawer.loadMore') }}</el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '../stores/agent'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
const store = useAgentStore()
const expandedId = ref(null)
const restoring = ref(false)
const diffMode = ref(false)
const diffFrom = ref(0)
const diffTo = ref(0)
const previewContent = ref(null)
const previewNum = ref(null)

const diffLines = computed(() => {
  if (!store.versionDiff) return []
  return store.versionDiff.split('\n')
})

function lineClass(line) {
  if (line.startsWith('+') && !line.startsWith('+++')) return 'diff-add'
  if (line.startsWith('-') && !line.startsWith('---')) return 'diff-del'
  if (line.startsWith('@@')) return 'diff-hunk'
  return 'diff-ctx'
}

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function sourceTagType(source) {
  if (source === 'app') return 'success'
  if (source === 'external') return ''
  if (source === 'restore') return 'warning'
  return 'info'
}

function formatTime(ts) {
  if (!ts) return ''
  const date = new Date(ts + 'Z') // SQLite timestamps are UTC
  const now = new Date()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return t('versionDrawer.justNow')
  if (diffMin < 60) return t('versionDrawer.minutesAgo', { n: diffMin })
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return t('versionDrawer.hoursAgo', { n: diffHour })
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 30) return t('versionDrawer.daysAgo', { n: diffDay })
  return date.toLocaleDateString(locale.value === 'zh' ? 'zh-CN' : 'en-US')
}

async function previewVersion(versionId) {
  try {
    const detail = await store.fetchVersionDetail(versionId)
    if (detail) {
      previewContent.value = detail.content
      previewNum.value = detail.version_num
    }
  } catch (e) {
    ElMessage.error(t('versionDrawer.fetchFailed'))
  }
}

async function compareVersion(ver) {
  // Compare this version with the latest (first in list)
  const latest = store.versionList[0]
  if (!latest || latest.id === ver.id) {
    ElMessage.info(t('versionDrawer.noVersionToCompare'))
    return
  }
  try {
    await store.fetchDiff(ver.id, latest.id)
    diffMode.value = true
    diffFrom.value = ver.version_num
    diffTo.value = latest.version_num
  } catch (e) {
    ElMessage.error(t('versionDrawer.diffFailed'))
  }
}

function exitDiff() {
  diffMode.value = false
  store.versionDiff = null
}

async function doRestore(versionId) {
  restoring.value = true
  try {
    await store.restoreVersion(versionId)
    ElMessage.success(t('versionDrawer.restored'))
    expandedId.value = null
  } catch (e) {
    ElMessage.error(t('versionDrawer.restoreFailed') + ': ' + (e.response?.data?.detail || e.message || e))
  } finally {
    restoring.value = false
  }
}

function loadMore() {
  const offset = store.versionList.length
  store.fetchVersions(20, offset)
}
</script>

<style scoped>
.drawer-header {
  font-weight: 600;
  font-size: 15px;
}
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 0;
  color: #909399;
}
.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #909399;
}
.version-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.version-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.version-item:hover {
  background: #f5f7fa;
}
.version-item.expanded {
  background: #f0f2f5;
}
.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.version-num {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
  min-width: 28px;
}
.version-time {
  font-size: 12px;
  color: #909399;
}
.source-tag {
  font-size: 11px;
}
.openclaw-hint {
  font-size: 14px;
}
.version-summary {
  margin-top: 4px;
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}
.summary-pending {
  color: #c0c4cc;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.version-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.load-more {
  text-align: center;
  padding: 12px 0;
}
/* Diff view */
.diff-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.diff-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.diff-title {
  font-weight: 600;
  font-size: 13px;
}
.diff-content {
  flex: 1;
  overflow: auto;
}
.diff-empty {
  text-align: center;
  padding: 40px 0;
  color: #909399;
}
.diff-pre {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.diff-add {
  background: #e6ffec;
  color: #1a7f37;
}
.diff-del {
  background: #ffebe9;
  color: #cf222e;
}
.diff-hunk {
  background: #ddf4ff;
  color: #0550ae;
}
.diff-ctx {
  color: #57606a;
}
/* Preview view */
.preview-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.preview-title {
  font-weight: 600;
  font-size: 13px;
}
.preview-content {
  flex: 1;
  overflow: auto;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
}
</style>

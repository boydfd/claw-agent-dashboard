<template>
  <div class="version-history-panel">
    <div class="panel-header">
      <span class="panel-title">{{ t('fileToolbar.versionHistory') }}</span>
      <el-button text size="small" @click="$emit('close')">✕</el-button>
    </div>

    <div class="panel-body">
      <div v-if="loading && versions.length === 0" class="panel-loading">
        {{ t('versionPanel.loading') }}
      </div>

      <div v-else-if="versions.length === 0" class="panel-empty">
        {{ t('versionPanel.noHistory') }}
      </div>

      <div v-else class="version-list">
        <div v-for="ver in versions" :key="ver.id"
             class="version-item" :class="{ expanded: expandedId === ver.id }"
             @click="toggleExpand(ver.id)">
          <div class="version-header">
            <span class="version-num">v{{ ver.version_num }}</span>
            <span class="version-time">{{ formatTime(ver.created_at) }}</span>
            <el-tag :type="sourceTagType(ver.source)" size="small" class="source-tag">
              {{ ver.source }}
            </el-tag>
          </div>
          <div v-if="ver.commit_msg" class="version-summary">{{ ver.commit_msg }}</div>
          <div v-else-if="ver.ai_summary" class="version-summary ai">{{ ver.ai_summary }}</div>
          <div v-else-if="ver.summary_pending" class="version-summary pending">
            {{ t('versionPanel.generatingSummary') }}
          </div>
          <div v-if="expandedId === ver.id" class="version-actions">
            <el-button size="small" @click.stop="handleView(ver)">
              {{ t('versionPanel.view') }}
            </el-button>
            <el-button size="small" @click.stop="handleCompare(ver)">
              {{ t('versionPanel.compare') }}
            </el-button>
            <el-popconfirm
              :title="t('versionPanel.confirmRestore')"
              :confirm-button-text="t('versionPanel.confirmRestoreBtn')"
              @confirm="handleRestore(ver)">
              <template #reference>
                <el-button size="small" type="warning" @click.stop>
                  {{ t('versionPanel.restore') }}
                </el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>

        <div v-if="hasMore" class="load-more">
          <el-button size="small" :loading="loading" @click.stop="$emit('load-more')">
            {{ t('versionPanel.loadMore') }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { computeDiff } from '../utils/diff'

const { t, locale } = useI18n()

const props = defineProps({
  versions: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  hasMore: { type: Boolean, default: false },
  fetchContent: { type: Function, required: true },
  onRestore: { type: Function, required: true },
  latestContent: { type: String, default: '' },
})

const emit = defineEmits(['view', 'compare', 'close', 'restore', 'load-more'])

const expandedId = ref(null)

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function formatTime(ts) {
  if (!ts) return ''
  const date = new Date(ts + 'Z')
  const now = new Date()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return t('versionPanel.justNow')
  if (diffMin < 60) return t('versionPanel.minutesAgo', { n: diffMin })
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return t('versionPanel.hoursAgo', { n: diffHour })
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 30) return t('versionPanel.daysAgo', { n: diffDay })
  return date.toLocaleDateString(locale.value === 'zh' ? 'zh-CN' : 'en-US')
}

function sourceTagType(source) {
  if (source === 'app' || source === 'dashboard') return 'success'
  if (source === 'external' || source === 'filesystem_sync') return ''
  if (source === 'restore') return 'warning'
  return 'info'
}

async function handleView(ver) {
  try {
    const content = await props.fetchContent(ver)
    emit('view', { content, versionNum: ver.version_num })
  } catch (e) {
    ElMessage.error(t('versionPanel.restoreFailed'))
  }
}

async function handleCompare(ver) {
  try {
    const content = await props.fetchContent(ver)
    const diffLines = computeDiff(content, props.latestContent)
    emit('compare', { diffLines, versionNum: ver.version_num })
  } catch (e) {
    ElMessage.error(t('versionPanel.restoreFailed'))
  }
}

async function handleRestore(ver) {
  try {
    await props.onRestore(ver)
    ElMessage.success(t('versionPanel.restored'))
    emit('restore')
  } catch (e) {
    ElMessage.error(t('versionPanel.restoreFailed'))
  }
}
</script>

<style scoped>
.version-history-panel {
  width: 300px;
  min-width: 300px;
  border-left: 1px solid var(--border-color, rgba(255,255,255,0.1));
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary, #161b22);
  height: 100%;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.1));
}
.panel-title {
  font-weight: 600;
  font-size: 14px;
  color: rgba(255,255,255,0.9);
}
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.panel-loading, .panel-empty {
  padding: 24px 16px;
  text-align: center;
  color: rgba(255,255,255,0.5);
  font-size: 13px;
}
.version-list {
  display: flex;
  flex-direction: column;
}
.version-item {
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  transition: background 0.15s;
}
.version-item:hover {
  background: rgba(255,255,255,0.03);
}
.version-item.expanded {
  background: rgba(255,255,255,0.05);
}
.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.version-num {
  font-weight: 600;
  font-size: 13px;
  color: rgba(255,255,255,0.9);
}
.version-time {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  flex: 1;
}
.source-tag {
  font-size: 11px;
}
.version-summary {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255,255,255,0.6);
  line-height: 1.4;
}
.version-summary.ai {
  font-style: italic;
}
.version-summary.pending {
  font-style: italic;
  color: rgba(255,255,255,0.35);
}
.version-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.load-more {
  padding: 12px 16px;
  text-align: center;
}
</style>

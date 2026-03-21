<template>
  <div class="agent-changes-panel">
    <template v-if="store.pendingChanges.length === 0">
      <div class="empty-state">
        <div class="empty-icon">✓</div>
        <p>{{ t('agentChanges.noChanges') }}</p>
        <p class="empty-desc">{{ t('agentChanges.noChangesDesc') }}</p>
      </div>
    </template>

    <template v-else>
      <div class="changes-layout">
        <!-- Left: file list -->
        <div class="file-list">
          <div class="file-list-header">
            <span>{{ t('agentChanges.title') }} ({{ store.pendingChanges.length }})</span>
          </div>
          <div class="file-list-body">
            <div
              v-for="change in store.pendingChanges"
              :key="change.id"
              class="file-item"
              :class="{ active: selectedChange?.id === change.id }"
              @click="selectChange(change)"
            >
              <span class="file-name">{{ change.file_path }}</span>
              <span class="change-badge" :class="change.change_type">
                {{ t(`agentChanges.${change.change_type}`) }}
              </span>
            </div>
          </div>
          <div class="file-list-footer">
            <el-popconfirm
              :title="t('agentChanges.acceptAllConfirm')"
              @confirm="handleAcceptAll"
              width="280"
            >
              <template #reference>
                <el-button type="primary" size="small">{{ t('agentChanges.acceptAll') }}</el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm
              :title="t('agentChanges.rejectAllConfirm')"
              @confirm="handleRejectAll"
              width="280"
            >
              <template #reference>
                <el-button type="danger" size="small" plain>{{ t('agentChanges.rejectAll') }}</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>

        <!-- Right: diff view -->
        <div class="diff-view">
          <template v-if="selectedChange">
            <div class="diff-header">
              <span class="diff-file-path">{{ selectedChange.file_path }}</span>
              <div class="diff-actions">
                <el-popconfirm
                  :title="t('agentChanges.acceptConfirm')"
                  @confirm="handleAccept"
                  width="320"
                >
                  <template #reference>
                    <el-button type="primary" size="small">{{ t('agentChanges.acceptChange') }}</el-button>
                  </template>
                </el-popconfirm>
                <el-popconfirm
                  :title="t('agentChanges.rejectConfirm')"
                  @confirm="handleReject"
                  width="320"
                >
                  <template #reference>
                    <el-button type="danger" size="small" plain>{{ t('agentChanges.rejectChange') }}</el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
            <div class="diff-content">
              <div class="diff-labels">
                <span class="label-old">{{ t('agentChanges.templateContent') }}</span>
                <span class="label-new">{{ t('agentChanges.diskContent') }}</span>
              </div>
              <div class="diff-lines">
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
            <div class="empty-state">
              <p>{{ t('agentChanges.selectChange') }}</p>
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '../stores/agent'

const { t } = useI18n()
const store = useAgentStore()

const selectedChange = ref(null)

// Reload when agent changes
watch(() => store.currentAgent, () => {
  selectedChange.value = null
  store.loadPendingChanges()
})

function selectChange(change) {
  selectedChange.value = change
}

// --- Diff computation (LCS-based, same as BlueprintDiffView) ---

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

const diffLines = computed(() => {
  if (!selectedChange.value) return []
  return computeDiff(selectedChange.value.old_content, selectedChange.value.new_content)
})

// --- Actions ---

async function handleAccept() {
  if (!selectedChange.value) return
  await store.acceptChange(selectedChange.value.id)
  ElMessage.success(t('agentChanges.accepted'))
  if (store.pendingChanges.length > 0) {
    selectedChange.value = store.pendingChanges[0]
  } else {
    selectedChange.value = null
  }
}

async function handleReject() {
  if (!selectedChange.value) return
  await store.rejectChange(selectedChange.value.id)
  ElMessage.success(t('agentChanges.rejected'))
  if (store.pendingChanges.length > 0) {
    selectedChange.value = store.pendingChanges[0]
  } else {
    selectedChange.value = null
  }
}

async function handleAcceptAll() {
  await store.acceptAllChanges()
  selectedChange.value = null
  ElMessage.success(t('agentChanges.allAccepted'))
}

async function handleRejectAll() {
  await store.rejectAllChanges()
  selectedChange.value = null
  ElMessage.success(t('agentChanges.allRejected'))
}
</script>

<style scoped>
.agent-changes-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
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
  font-size: 48px;
  margin-bottom: 12px;
  color: #67c23a;
}
.empty-desc {
  font-size: 12px;
  color: #c0c4cc;
}
.changes-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}
.file-list {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}
.file-list-header {
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #e4e7ed;
}
.file-list-body {
  flex: 1;
  overflow-y: auto;
}
.file-item {
  padding: 8px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #606266;
  border-bottom: 1px solid #f0f0f0;
}
.file-item:hover {
  background: #f5f7fa;
}
.file-item.active {
  background: #ecf5ff;
  color: #409eff;
}
.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 8px;
}
.change-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  flex-shrink: 0;
}
.change-badge.modified {
  background: #fdf6ec;
  color: #e6a23c;
}
.change-badge.added {
  background: #f0f9eb;
  color: #67c23a;
}
.file-list-footer {
  padding: 8px 12px;
  border-top: 1px solid #e4e7ed;
  display: flex;
  gap: 8px;
}
.diff-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.diff-header {
  padding: 8px 16px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.diff-file-path {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.diff-actions {
  display: flex;
  gap: 8px;
}
.diff-content {
  flex: 1;
  overflow-y: auto;
}
.diff-labels {
  display: flex;
  padding: 4px 16px;
  font-size: 11px;
  color: #909399;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
}
.label-old {
  width: 50%;
}
.label-new {
  width: 50%;
}
.diff-lines {
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
  color: #909399;
  user-select: none;
  flex-shrink: 0;
}
.line-prefix {
  width: 16px;
  text-align: center;
  color: #909399;
  flex-shrink: 0;
}
.line-text {
  flex: 1;
  overflow-x: auto;
}
</style>

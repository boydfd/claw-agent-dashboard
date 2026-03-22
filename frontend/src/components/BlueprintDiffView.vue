<template>
  <div class="diff-view">
    <!-- Header with back button -->
    <div class="diff-header">
      <el-button @click="$emit('back')" text>
        ← {{ t('management.backToList') }}
      </el-button>
      <span class="diff-title">{{ blueprintName }} — {{ t('management.pendingChanges') }}</span>
    </div>

    <div class="diff-body" v-loading="loading">
      <!-- Left: file list -->
      <div class="diff-file-list">
        <div class="file-list-header">Changed Files</div>
        <div
          v-for="change in changes"
          :key="change.id"
          class="file-item"
          :class="{ active: selectedChange?.id === change.id }"
          @click="selectedChange = change"
        >
          <span class="change-type-badge" :class="change.change_type">
            {{ changeTypeLabel(change.change_type) }}
          </span>
          <span class="file-name">{{ change.file_path }}</span>
        </div>
        <!-- Accept All button -->
        <div class="file-list-footer" v-if="changes.length > 0">
          <el-popconfirm
            :title="t('management.acceptAllConfirm', { count: changes.length })"
            @confirm="handleAcceptAll"
          >
            <template #reference>
              <el-button type="success" class="accept-all-btn">
                ✓ {{ t('management.acceptAll') }} ({{ changes.length }})
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>

      <!-- Right: diff content -->
      <div class="diff-content" v-if="selectedChange">
        <!-- File header with per-file accept/reject -->
        <div class="diff-file-header">
          <div>
            <span class="file-title">{{ selectedChange.file_path }}</span>
            <el-tag :type="changeTagType(selectedChange.change_type)" size="small">
              {{ changeTypeLabel(selectedChange.change_type) }}
            </el-tag>
          </div>
          <div class="file-actions">
            <el-button type="success" size="small" @click="handleAccept(selectedChange)">
              ✓ {{ t('management.acceptChange') }}
            </el-button>
            <el-button type="danger" size="small" @click="handleReject(selectedChange)">
              ✗ {{ t('management.rejectChange') }}
            </el-button>
          </div>
        </div>

        <!-- Diff lines -->
        <div class="diff-lines">
          <div
            v-for="(line, idx) in diffLines"
            :key="idx"
            class="diff-line"
            :class="line.type"
          >
            <span class="line-num old">{{ line.oldNum || '' }}</span>
            <span class="line-num new">{{ line.newNum || '' }}</span>
            <span class="line-content">{{ line.prefix }}{{ line.text }}</span>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="changes.length === 0" class="no-changes">
        {{ t('management.noChanges') }}
      </div>
      <div v-else class="select-file-hint">
        Select a file to view diff
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useBlueprintStore } from '../stores/blueprint'
import { computeDiff } from '../utils/diff'

const props = defineProps({
  blueprintId: {
    type: Number,
    required: true,
  },
  blueprintName: {
    type: String,
    default: '',
  },
})

defineEmits(['back'])

const { t } = useI18n()
const store = useBlueprintStore()

const selectedChange = ref(null)

const loading = computed(() => store.pendingLoading)

const changes = computed(() => store.currentPendingChanges?.changes || [])

// Auto-select first change on load
onMounted(async () => {
  await store.loadBlueprintPendingChanges(props.blueprintId)
  if (changes.value.length > 0) {
    selectedChange.value = changes.value[0]
  }
})

const diffLines = computed(() => {
  if (!selectedChange.value) return []
  const change = selectedChange.value
  if (change.change_type === 'added') {
    return (change.new_content || '').split('\n').map((text, idx) => ({
      type: 'add',
      prefix: '+',
      text,
      oldNum: null,
      newNum: idx + 1,
    }))
  }
  if (change.change_type === 'deleted') {
    return (change.old_content || '').split('\n').map((text, idx) => ({
      type: 'del',
      prefix: '-',
      text,
      oldNum: idx + 1,
      newNum: null,
    }))
  }
  // modified
  return computeDiff(change.old_content, change.new_content)
})

// --- Labels and tag types ---

function changeTypeLabel(type) {
  const map = {
    modified: t('management.changeModified'),
    added: t('management.changeAdded'),
    deleted: t('management.changeDeleted'),
  }
  return map[type] || type
}

function changeTagType(type) {
  const map = {
    modified: 'warning',
    added: 'success',
    deleted: 'danger',
  }
  return map[type] || 'info'
}

// --- Event handlers ---

async function handleAccept(change) {
  try {
    await store.acceptChange(props.blueprintId, change.id)
    ElMessage.success(t('management.changeAccepted'))
    // If current change was accepted, select next or clear
    if (selectedChange.value?.id === change.id) {
      selectedChange.value = changes.value[0] || null
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'Accept failed')
  }
}

async function handleReject(change) {
  try {
    await store.rejectChange(props.blueprintId, change.id)
    ElMessage.success(t('management.changeRejected'))
    if (selectedChange.value?.id === change.id) {
      selectedChange.value = changes.value[0] || null
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'Reject failed')
  }
}

async function handleAcceptAll() {
  try {
    await store.acceptAllChanges(props.blueprintId)
    ElMessage.success(t('management.allChangesAccepted'))
    selectedChange.value = null
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'Accept all failed')
  }
}
</script>

<style scoped>
.diff-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.diff-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.diff-title {
  font-size: 16px;
  font-weight: bold;
  color: #eee;
}

.diff-body {
  flex: 1;
  display: flex;
  gap: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--border-color, #333);
  border-radius: 6px;
}

/* Left: file list */
.diff-file-list {
  width: 240px;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color, #333);
  background: var(--bg-secondary, #1a1a2e);
}

.file-list-header {
  padding: 10px 12px;
  font-size: 13px;
  font-weight: bold;
  color: #999;
  border-bottom: 1px solid var(--border-color, #333);
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #bbb;
  transition: background 0.15s;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.file-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.file-item.active {
  background: rgba(233, 69, 96, 0.15);
  color: var(--primary-color, #e94560);
}

.file-name {
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
}

.change-type-badge {
  font-size: 10px;
  font-weight: bold;
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
  text-transform: uppercase;
}

.change-type-badge.modified {
  background: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.change-type-badge.added {
  background: rgba(46, 160, 67, 0.2);
  color: #67c23a;
}

.change-type-badge.deleted {
  background: rgba(248, 81, 73, 0.2);
  color: #f56c6c;
}

.file-list-footer {
  margin-top: auto;
  padding: 10px 12px;
  border-top: 1px solid var(--border-color, #333);
}

.accept-all-btn {
  width: 100%;
}

/* Right: diff content */
.diff-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.diff-file-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border-color, #333);
  background: var(--bg-secondary, #1a1a2e);
  flex-wrap: wrap;
  gap: 8px;
}

.file-title {
  font-family: monospace;
  font-size: 14px;
  color: #eee;
  margin-right: 8px;
}

.file-actions {
  display: flex;
  gap: 8px;
}

.diff-lines {
  flex: 1;
  overflow: auto;
  background: var(--bg-primary, #0f0f23);
}

.diff-line {
  display: flex;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 20px;
  white-space: pre;
}

.diff-line.add {
  background: rgba(46, 160, 67, 0.15);
}

.diff-line.del {
  background: rgba(248, 81, 73, 0.15);
}

.diff-line.context {
  background: transparent;
}

.line-num {
  display: inline-block;
  width: 44px;
  min-width: 44px;
  text-align: right;
  padding-right: 8px;
  color: #555;
  user-select: none;
  border-right: 1px solid var(--border-color, #333);
}

.line-num.new {
  border-right: none;
  margin-right: 8px;
}

.line-content {
  flex: 1;
  color: #ccc;
  padding-right: 16px;
}

.diff-line.add .line-content {
  color: #67c23a;
}

.diff-line.del .line-content {
  color: #f56c6c;
}

/* Empty states */
.no-changes,
.select-file-hint {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  font-size: 14px;
}
</style>

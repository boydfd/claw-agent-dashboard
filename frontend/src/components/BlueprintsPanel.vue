<template>
  <div class="blueprints-panel">
    <!-- List Mode -->
    <template v-if="store.viewMode === 'list'">
      <div class="blueprints-toolbar">
        <h3 class="panel-title">{{ t('management.blueprints') }}</h3>
        <el-button type="primary" @click="store.createDialogVisible = true">
          {{ t('management.newBlueprint') }}
        </el-button>
      </div>
      <div v-loading="store.loading" class="blueprints-grid">
        <el-card
          v-for="bp in store.blueprints"
          :key="bp.id"
          class="blueprint-card"
          shadow="hover"
        >
          <template #header>
            <div class="card-header">
              <span class="card-title">{{ bp.name }}</span>
            </div>
          </template>
          <p v-if="bp.description" class="card-description">{{ bp.description }}</p>
          <div class="card-stats">
            <span class="stat">{{ t('management.blueprintFiles') }}: {{ bp.file_count ?? 0 }}</span>
            <span class="stat">{{ t('management.variables') }}: {{ bp.variable_count ?? 0 }}</span>
            <span class="stat">{{ t('management.deriveNewAgent') }}: {{ bp.derivation_count ?? 0 }}</span>
          </div>
          <div class="card-actions">
            <el-button
              v-if="getPendingCount(bp.id) > 0"
              type="warning"
              size="small"
              @click.stop="enterDiffView(bp)"
            >
              {{ t('management.reviewChanges') }} ({{ getPendingCount(bp.id) }})
            </el-button>
            <el-button size="small" @click="store.selectBlueprint(bp.id)">
              {{ t('management.editBlueprint') }}
            </el-button>
            <el-button size="small" type="success" @click="store.openDeriveDialog(bp.id)">
              {{ t('management.deriveNewAgent') }}
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(bp)">
              {{ t('management.deleteBlueprint') }}
            </el-button>
          </div>
        </el-card>
        <el-card
          class="blueprint-card add-card"
          shadow="hover"
          @click="store.createDialogVisible = true"
        >
          <div class="add-card-content">
            <span class="add-icon">+</span>
            <span>{{ t('management.newBlueprint') }}</span>
          </div>
        </el-card>
      </div>
    </template>

    <!-- Editor Mode -->
    <template v-else-if="store.viewMode === 'editor'">
      <div class="editor-topbar">
        <a class="back-link" @click="store.backToList()">
          {{ t('management.backToList') }}
        </a>
        <span class="editor-title">{{ store.currentBlueprint?.name }}</span>
        <el-button
          v-if="variableCount > 0"
          size="small"
          @click="variablesDrawerVisible = true"
        >
          {{ t('management.viewVariables') }} ({{ variableCount }})
        </el-button>
      </div>
      <div v-loading="store.loading" class="editor-layout">
        <!-- Left: File tree -->
        <div class="file-tree-panel">
          <div class="file-tree-list">
            <template v-for="node in flattenedTree" :key="node.path || node.dirPath">
              <div
                v-if="node.type === 'dir'"
                class="tree-dir-item"
                :style="{ paddingLeft: node.depth * 16 + 'px' }"
                @click="toggleDir(node.dirPath)"
              >
                <span class="dir-arrow">{{ node.collapsed ? '▶' : '▼' }}</span>
                <span class="dir-name">{{ node.name }}</span>
              </div>
              <div
                v-else
                class="file-item"
                :class="{ active: store.currentFile?.file_path === node.path }"
                :style="{ paddingLeft: node.depth * 16 + 8 + 'px' }"
                @click="store.selectFile(node.path)"
              >
                <span class="file-name">{{ node.name }}</span>
                <el-popconfirm
                  :title="t('common.confirm') + '?'"
                  @confirm="handleDeleteFile(node.path)"
                >
                  <template #reference>
                    <el-button text size="small" type="danger" @click.stop>×</el-button>
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </div>
          <el-button class="add-file-btn" size="small" @click="addFileDialogVisible = true">
            {{ t('management.addFile') }}
          </el-button>
        </div>

        <!-- Right: Code editor -->
        <div class="editor-panel">
          <template v-if="store.currentFile">
            <div class="editor-file-header">
              <code class="current-file-path">{{ store.currentFile.file_path }}</code>
              <div class="editor-file-actions">
                <el-button
                  size="small"
                  @click="store.openVersionDrawer(store.currentFile.file_path)"
                >
                  {{ t('management.versionHistory') }}
                </el-button>
                <el-button
                  type="primary"
                  size="small"
                  :loading="store.saving"
                  @click="handleSave"
                >
                  {{ t('common.save') }}
                </el-button>
              </div>
            </div>
            <CodeEditor
              v-model:value="store.editContent"
              :language="editorLanguage"
              :variable-map="variableMap"
            />
          </template>
          <div v-else class="no-file-selected">
            <p>{{ t('management.noFiles') }}</p>
          </div>
        </div>
      </div>
    </template>

    <!-- Diff View Mode -->
    <template v-else-if="store.viewMode === 'diff'">
      <BlueprintDiffView
        :blueprint-id="store.currentBlueprint?.id"
        :blueprint-name="store.currentBlueprint?.name"
        @back="store.backToList()"
      />
    </template>

    <!-- Variables Drawer -->
    <el-drawer
      v-model="variablesDrawerVisible"
      :title="t('management.viewVariables')"
      direction="rtl"
      size="380px"
    >
      <div class="variables-drawer-content">
        <div
          v-for="varInfo in store.currentBlueprint?.referenced_variables || []"
          :key="varInfo.name"
          class="var-group"
        >
          <div class="var-group-header">
            <span class="var-name">!{<span>{{ varInfo.name }}</span>}</span>
            <span class="var-file-count">({{ varInfo.source_files.length }})</span>
          </div>
          <div class="var-source-files">
            <div
              v-for="(file, idx) in varInfo.source_files"
              :key="file"
              class="var-source-file"
              @click="handleVarFileClick(file)"
            >
              <span class="var-connector">{{ idx === varInfo.source_files.length - 1 ? '\u2514\u2500' : '\u251C\u2500' }}</span>
              <span class="var-file-name">{{ file }}</span>
            </div>
          </div>
        </div>
        <div v-if="variableCount === 0" class="no-variables">
          No variables found in template files.
        </div>
      </div>
    </el-drawer>

    <!-- Version History Drawer -->
    <el-drawer
      :model-value="store.versionDrawerOpen"
      :title="t('management.versionHistoryTitle', { name: store.versionFilePath })"
      direction="rtl"
      size="460px"
      :before-close="store.closeVersionDrawer"
      :append-to-body="true"
    >
      <!-- Preview mode -->
      <div v-if="store.versionPreviewContent !== null" class="version-preview">
        <div class="version-preview-header">
          <el-button size="small" @click="store.versionPreviewContent = null; store.versionPreviewNum = null">
            &larr; {{ t('management.versionBackToList') }}
          </el-button>
          <span class="version-preview-title">{{ t('management.versionPreviewTitle', { num: store.versionPreviewNum }) }}</span>
        </div>
        <pre class="version-preview-content">{{ store.versionPreviewContent }}</pre>
      </div>

      <!-- Version list -->
      <div v-else>
        <div v-if="store.versionLoading" class="version-loading">
          Loading...
        </div>
        <div v-else-if="store.versionList.length === 0" class="version-empty">
          {{ t('management.versionNoHistory') }}
        </div>
        <div v-else class="version-list">
          <div
            v-for="ver in store.versionList"
            :key="ver.id"
            class="version-item"
            :class="{ expanded: expandedVersionId === ver.id }"
            @click="expandedVersionId = expandedVersionId === ver.id ? null : ver.id"
          >
            <div class="version-header">
              <span class="version-num">{{ t('management.versionNum', { num: ver.version_num }) }}</span>
              <span class="version-time">{{ formatVersionTime(ver.created_at) }}</span>
              <el-tag :type="versionSourceTagType(ver.source)" size="small" class="version-source-tag">
                {{ ver.source }}
              </el-tag>
            </div>
            <div v-if="ver.commit_msg || ver.ai_summary" class="version-summary">
              {{ ver.commit_msg || ver.ai_summary }}
            </div>
            <div v-if="expandedVersionId === ver.id" class="version-actions" @click.stop>
              <el-button size="small" @click="handleViewVersion(ver.version_num)">
                {{ t('management.versionView') }}
              </el-button>
              <el-popconfirm
                :title="t('management.versionRestoreConfirm', { num: ver.version_num })"
                @confirm="handleRestoreVersion(ver.version_num)"
              >
                <template #reference>
                  <el-button size="small" type="warning" :loading="restoringVersion">
                    {{ t('management.versionRestore') }}
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- Create Blueprint Dialog -->
    <el-dialog
      v-model="store.createDialogVisible"
      :title="t('management.createBlueprint')"
      width="500px"
      @close="resetCreateForm"
    >
      <el-input
        v-model="newName"
        :placeholder="t('management.blueprintName')"
        class="dialog-input"
      />
      <el-input
        v-model="newDescription"
        :placeholder="t('management.blueprintDescription')"
        type="textarea"
        :rows="3"
        class="dialog-input"
      />
      <el-divider />
      <el-form-item style="margin-bottom: 12px">
        <el-switch
          v-model="importFromAgent"
          :active-text="t('management.importFromAgent')"
        />
      </el-form-item>
      <template v-if="importFromAgent">
        <el-form-item :label="t('management.importSourceAgent')" style="margin-bottom: 12px">
          <el-select
            v-model="selectedAgentId"
            :placeholder="t('management.importSourceAgentPlaceholder')"
            filterable
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="agent in availableAgents"
              :key="agent.id"
              :label="agent.display_name || agent.name"
              :value="agent.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('management.excludePatterns')" style="margin-bottom: 0">
          <el-input
            v-model="excludePatternsText"
            type="textarea"
            :rows="4"
            :placeholder="t('management.excludePatternsPlaceholder')"
          />
        </el-form-item>
      </template>
      <template #footer>
        <el-button @click="store.createDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :disabled="!newName.trim() || (importFromAgent && !selectedAgentId)"
          @click="handleCreate"
        >{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- Add File Dialog -->
    <el-dialog
      v-model="addFileDialogVisible"
      :title="t('management.addFileTitle')"
      width="460px"
    >
      <el-input
        v-model="newFilePath"
        :placeholder="t('management.filePath')"
        class="dialog-input"
      />
      <template #footer>
        <el-button @click="addFileDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleAddFile">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- Derive Agent Dialog -->
    <DeriveAgentDialog />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useBlueprintStore } from '../stores/blueprint'
import { useAgentStore } from '../stores/agent'
import CodeEditor from './CodeEditor.vue'
import DeriveAgentDialog from './DeriveAgentDialog.vue'
import BlueprintDiffView from './BlueprintDiffView.vue'

const { t } = useI18n()
const store = useBlueprintStore()
const agentStore = useAgentStore()

// Local state
const newName = ref('')
const newDescription = ref('')
const addFileDialogVisible = ref(false)
const newFilePath = ref('')
const variablesDrawerVisible = ref(false)
const expandedVersionId = ref(null)
const restoringVersion = ref(false)

// Import from agent state
const importFromAgent = ref(false)
const selectedAgentId = ref(null)
const excludePatternsText = ref('memories/*\nlogs/*')

const availableAgents = computed(() => agentStore.agents || [])

onMounted(async () => {
  store.loadBlueprints()
  store.startPendingPolling()
  if (!agentStore.agents || agentStore.agents.length === 0) {
    await agentStore.loadAgents()
  }
})

onUnmounted(() => {
  store.stopPendingPolling()
})

// Build tree structure from flat file list
function buildFileTree(files) {
  const root = []
  const dirs = {}

  for (const f of files) {
    const parts = f.file_path.split('/')
    if (parts.length === 1) {
      root.push({ name: parts[0], path: f.file_path, type: 'file' })
    } else {
      let current = root
      let currentPath = ''
      for (let i = 0; i < parts.length - 1; i++) {
        currentPath = currentPath ? currentPath + '/' + parts[i] : parts[i]
        if (!dirs[currentPath]) {
          const dirNode = { name: parts[i], type: 'dir', dirPath: currentPath, children: [] }
          current.push(dirNode)
          dirs[currentPath] = dirNode
        }
        current = dirs[currentPath].children
      }
      current.push({ name: parts[parts.length - 1], path: f.file_path, type: 'file' })
    }
  }

  function sortNodes(nodes) {
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    for (const n of nodes) {
      if (n.type === 'dir') sortNodes(n.children)
    }
  }
  sortNodes(root)
  return root
}

const fileTree = computed(() =>
  buildFileTree(store.currentBlueprint?.files || [])
)

const collapsedDirs = ref(new Set())

// Initialize collapsed state: top-level dirs start collapsed
watch(() => store.currentBlueprint?.files, (files) => {
  if (!files) return
  const tree = buildFileTree(files)
  const collapsed = new Set()
  for (const node of tree) {
    if (node.type === 'dir') collapsed.add(node.dirPath)
  }
  collapsedDirs.value = collapsed
})

function toggleDir(dirPath) {
  const next = new Set(collapsedDirs.value)
  if (next.has(dirPath)) {
    next.delete(dirPath)
  } else {
    next.add(dirPath)
  }
  collapsedDirs.value = next
}

// Flatten tree for rendering
const flattenedTree = computed(() => {
  const result = []
  function walk(nodes, depth) {
    for (const node of nodes) {
      if (node.type === 'dir') {
        const collapsed = collapsedDirs.value.has(node.dirPath)
        result.push({ ...node, depth, collapsed })
        if (!collapsed) walk(node.children, depth + 1)
      } else {
        result.push({ ...node, depth })
      }
    }
  }
  walk(fileTree.value, 0)
  return result
})

// Build variable map for CodeEditor highlighting
const variableMap = computed(() => {
  const vars = store.currentBlueprint?.referenced_variables || []
  const map = {}
  for (const v of vars) {
    map[v.name] = { value: v.name }
  }
  return map
})

// Detect editor language from file extension
const editorLanguage = computed(() => {
  const path = store.currentFile?.file_path || ''
  if (path.endsWith('.md')) return 'markdown'
  if (path.endsWith('.json')) return 'json'
  if (path.endsWith('.yaml') || path.endsWith('.yml')) return 'yaml'
  if (path.endsWith('.js')) return 'javascript'
  if (path.endsWith('.ts')) return 'typescript'
  if (path.endsWith('.py')) return 'python'
  return 'markdown'
})

const variableCount = computed(() =>
  store.currentBlueprint?.referenced_variables?.length ?? 0
)

// Handlers
async function handleCreate() {
  if (!newName.value.trim()) return

  let sourceAgentId = null
  let excludePatterns = null

  if (importFromAgent.value && selectedAgentId.value) {
    sourceAgentId = selectedAgentId.value
    excludePatterns = excludePatternsText.value
      .split('\n')
      .map(l => l.trim())
      .filter(l => l.length > 0)
  }

  try {
    const result = await store.createNewBlueprint(
      newName.value.trim(), newDescription.value.trim(),
      sourceAgentId, excludePatterns
    )
    if (sourceAgentId && result.imported_file_count > 0) {
      ElMessage.success(t('management.importSuccess', { count: result.imported_file_count }))
    } else if (sourceAgentId && result.imported_file_count === 0) {
      ElMessage.warning(t('management.importNoFiles'))
    } else {
      ElMessage.success(t('management.blueprintCreated'))
    }
    store.createDialogVisible = false
    resetCreateForm()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('management.blueprintCreateFailed'))
  }
}

function resetCreateForm() {
  newName.value = ''
  newDescription.value = ''
  importFromAgent.value = false
  selectedAgentId.value = null
  excludePatternsText.value = 'memories/*\nlogs/*'
}

async function handleDelete(bp) {
  if (bp.derivation_count > 0) {
    try {
      await ElMessageBox.confirm(
        t('management.deleteConfirmWithDerivations', { count: bp.derivation_count }),
        t('management.deleteBlueprint'),
        { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' }
      )
    } catch {
      return // cancelled
    }
  }
  try {
    await store.deleteBlueprint(bp.id, true)
    ElMessage.success(t('management.blueprintDeleted'))
  } catch {
    ElMessage.error(t('management.deleteFailed'))
  }
}

async function handleSave() {
  try {
    await store.saveCurrentFile()
    ElMessage.success(t('management.saved'))
  } catch {
    ElMessage.error(t('management.saveFailed'))
  }
}

async function handleAddFile() {
  if (!newFilePath.value.trim()) return
  try {
    await store.addFile(newFilePath.value.trim())
    ElMessage.success(t('management.fileAdded'))
    addFileDialogVisible.value = false
    newFilePath.value = ''
  } catch {
    ElMessage.error(t('management.createFailed'))
  }
}

async function handleDeleteFile(filePath) {
  try {
    await store.deleteFile(filePath)
    ElMessage.success(t('management.fileDeleted'))
  } catch {
    ElMessage.error(t('management.deleteFailed'))
  }
}

function handleVarFileClick(filePath) {
  variablesDrawerVisible.value = false
  store.selectFile(filePath)
}

function getPendingCount(blueprintId) {
  const bp = store.pendingChangesSummary.blueprints.find(b => b.blueprint_id === blueprintId)
  return bp?.pending_count || 0
}

function enterDiffView(bp) {
  store.currentBlueprint = bp
  store.viewMode = 'diff'
}

// Version history helpers
function formatVersionTime(ts) {
  if (!ts) return ''
  const date = new Date(ts + 'Z')
  const now = new Date()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}h ago`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  return date.toLocaleDateString()
}

function versionSourceTagType(source) {
  if (source === 'dashboard') return 'success'
  if (source === 'filesystem_sync') return 'warning'
  if (source === 'restore') return 'info'
  return ''
}

async function handleViewVersion(versionNum) {
  try {
    await store.viewVersion(store.versionFilePath, versionNum)
  } catch {
    ElMessage.error(t('management.versionRestoreFailed'))
  }
}

async function handleRestoreVersion(versionNum) {
  restoringVersion.value = true
  try {
    await store.restoreVersion(store.versionFilePath, versionNum)
    ElMessage.success(t('management.versionRestored', { num: versionNum }))
    expandedVersionId.value = null
  } catch {
    ElMessage.error(t('management.versionRestoreFailed'))
  } finally {
    restoringVersion.value = false
  }
}
</script>

<style scoped>
.blueprints-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* Toolbar */
.blueprints-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.panel-title {
  margin: 0;
  font-size: 16px;
  color: #ccc;
}

/* Card grid */
.blueprints-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.blueprint-card {
  background: var(--bg-secondary, #1a1a2e);
  border-color: var(--border-color, #333);
}
.blueprint-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom-color: var(--border-color, #333);
}
.blueprint-card :deep(.el-card__body) {
  padding: 16px;
}
.card-header {
  display: flex;
  align-items: center;
}
.card-title {
  font-weight: bold;
  font-size: 15px;
  color: #eee;
}
.card-description {
  color: #999;
  font-size: 13px;
  margin: 0 0 12px 0;
}
.card-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}
.stat {
  font-size: 12px;
  color: #777;
}
.card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.add-card {
  cursor: pointer;
  border-style: dashed;
}
.add-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
}
.add-card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #666;
  font-size: 14px;
}
.add-icon {
  font-size: 32px;
  line-height: 1;
}

/* Editor mode */
.editor-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}
.back-link {
  color: var(--primary-color, #e94560);
  cursor: pointer;
  font-size: 14px;
}
.back-link:hover {
  text-decoration: underline;
}
.editor-title {
  font-size: 16px;
  font-weight: bold;
  color: #eee;
}
.editor-layout {
  display: flex;
  flex: 1;
  gap: 16px;
  min-height: 0;
  overflow: hidden;
}

/* File tree */
.file-tree-panel {
  width: 240px;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color, #333);
  padding-right: 12px;
  overflow-y: auto;
  overflow-x: auto;
}
.file-tree-list {
  flex: 1;
  min-height: 0;
}
.tree-dir-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 13px;
  color: #999;
  user-select: none;
}
.tree-dir-item:hover {
  background: rgba(255, 255, 255, 0.03);
}
.dir-arrow {
  font-size: 10px;
  width: 12px;
  color: #666;
}
.dir-name {
  font-family: monospace;
  font-weight: bold;
}
.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #bbb;
  transition: background 0.15s;
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
}
.add-file-btn {
  margin-top: 8px;
}

/* Editor panel */
.editor-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.editor-file-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.editor-file-actions {
  display: flex;
  gap: 8px;
}
.current-file-path {
  font-family: monospace;
  color: #aaa;
  font-size: 13px;
}
.no-file-selected {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #666;
  font-size: 14px;
}
.dialog-input {
  margin-bottom: 12px;
}

/* Variables drawer */
.variables-drawer-content {
  padding: 0 4px;
}
.var-group {
  margin-bottom: 16px;
}
.var-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.var-name {
  font-family: monospace;
  font-weight: bold;
  font-size: 14px;
  color: #e94560;
}
.var-file-count {
  font-size: 12px;
  color: #888;
}
.var-source-files {
  margin-left: 8px;
}
.var-source-file {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
  cursor: pointer;
  border-radius: 3px;
}
.var-source-file:hover {
  background: rgba(255, 255, 255, 0.05);
}
.var-source-file:hover .var-file-name {
  text-decoration: underline;
}
.var-connector {
  font-family: monospace;
  color: #555;
  font-size: 13px;
}
.var-file-name {
  font-family: monospace;
  font-size: 13px;
  color: #bbb;
}
.no-variables {
  color: #666;
  font-size: 14px;
  text-align: center;
  padding: 32px 0;
}

/* Version history drawer */
.version-loading,
.version-empty {
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
  background: rgba(255, 255, 255, 0.05);
}
.version-item.expanded {
  background: rgba(255, 255, 255, 0.08);
}
.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.version-num {
  font-weight: 600;
  font-size: 13px;
  color: #eee;
  min-width: 28px;
}
.version-time {
  font-size: 12px;
  color: #909399;
}
.version-source-tag {
  font-size: 11px;
}
.version-summary {
  margin-top: 4px;
  font-size: 12px;
  color: #999;
  line-height: 1.4;
}
.version-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

/* Version preview */
.version-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.version-preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.version-preview-title {
  font-weight: 600;
  font-size: 13px;
  color: #eee;
}
.version-preview-content {
  flex: 1;
  overflow: auto;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  color: #ccc;
}
</style>

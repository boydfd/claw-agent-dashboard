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
          @click="openVariablesDrawer()"
        >
          {{ t('management.viewVariables') }} ({{ variableCount }})
        </el-button>
      </div>
      <div v-loading="store.loading" class="editor-layout">
        <!-- Left: File tree -->
        <div class="file-tree-panel">
          <div class="search-box">
            <el-input
              v-model="store.fileSearchQuery"
              :placeholder="t('search.placeholder')"
              :prefix-icon="Search"
              clearable
              size="small"
              @keyup.enter="handleBlueprintSearch"
              @clear="store.clearFileSearch()"
            />
          </div>

          <!-- Search results -->
          <div v-if="store.fileSearchResults" class="file-tree-list">
            <div v-if="store.fileSearchLoading" class="search-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              {{ t('search.searching') }}
            </div>
            <div v-else-if="store.fileSearchResults.total_matches === 0" class="search-empty">
              {{ t('search.noResults') }}
            </div>
            <div v-else class="search-results">
              <div class="search-summary">
                {{ t('search.matchCount', { count: store.fileSearchResults.total_matches, files: store.fileSearchResults.results.length }) }}
              </div>
              <div v-for="fileResult in store.fileSearchResults.results" :key="fileResult.file_path" class="search-file-group">
                <div class="search-file-header" @click="toggleSearchFile(fileResult.file_path)">
                  <span class="dir-arrow">{{ collapsedSearchFiles.has(fileResult.file_path) ? '▶' : '▼' }}</span>
                  <span class="search-file-name">{{ fileResult.file_path }}</span>
                  <span class="search-match-count">{{ fileResult.matches.length }}</span>
                </div>
                <div v-if="!collapsedSearchFiles.has(fileResult.file_path)" class="search-matches">
                  <div
                    v-for="match in fileResult.matches"
                    :key="match.line_number"
                    class="search-match-item"
                    @click="openSearchResult(fileResult.file_path, match.line_number)"
                  >
                    <span class="search-line-num">{{ match.line_number }}</span>
                    <span class="search-line-content" v-html="highlightMatch(match.line_content, store.fileSearchQuery)"></span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Normal file tree -->
          <div v-else class="file-tree-list">
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

        <!-- Right: Code editor with optional version panel -->
        <div class="editor-panel">
          <template v-if="store.currentFile">
            <div class="editor-with-version-panel">
              <div class="editor-content-wrapper">
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

                <!-- Version view mode bar -->
                <div v-if="versionViewState.mode !== 'normal'" class="version-mode-bar">
                  <span v-if="versionViewState.mode === 'view'">
                    {{ t('versionPanel.viewingVersion', { n: versionViewState.versionNum }) }}
                  </span>
                  <span v-else>
                    {{ t('versionPanel.comparingVersion', { n: versionViewState.versionNum }) }}
                  </span>
                  <el-button size="small" @click="exitVersionMode">
                    {{ t('versionPanel.back') }}
                  </el-button>
                </div>

                <!-- Compare mode -->
                <VersionDiffView
                  v-if="versionViewState.mode === 'compare'"
                  :diffLines="versionViewState.diffLines"
                  class="version-compare-area"
                />

                <!-- View mode -->
                <CodeEditor
                  v-else-if="versionViewState.mode === 'view'"
                  :value="versionViewState.content"
                  :language="editorLanguage"
                  :readOnly="true"
                  class="version-view-area"
                />

                <!-- Normal mode -->
                <CodeEditor
                  v-else
                  v-model:value="store.editContent"
                  :language="editorLanguage"
                  :variable-map="variableMap"
                  :target-line="blueprintTargetLine"
                  @highlight-done="blueprintTargetLine = null"
                />
              </div>

              <!-- Version History Panel -->
              <VersionHistoryPanel
                v-if="store.versionDrawerOpen"
                :versions="store.versionList"
                :loading="store.versionLoading"
                :hasMore="store.versionList.length < store.versionTotal"
                :fetchContent="handleFetchVersionContent"
                :restoreHandler="handleBpRestoreVersion"
                :latestContent="store.currentFile?.content || ''"
                @view="onVersionView"
                @compare="onVersionCompare"
                @close="closeBlueprintVersionHistory"
                @restore="onBlueprintVersionRestored"
                @load-more="store.fetchMoreVersions()"
              />
            </div>
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
      size="420px"
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
          <div class="var-value-row">
            <template v-if="blueprintVarValues[varInfo.name]">
              <code class="var-current-value">
                {{ blueprintVarValues[varInfo.name].type === 'secret' ? '******' : blueprintVarValues[varInfo.name].value }}
              </code>
              <el-button size="small" text @click="editBlueprintVar(blueprintVarValues[varInfo.name])">
                {{ t('management.editVar') }}
              </el-button>
            </template>
            <template v-else>
              <el-tag size="small" type="info">{{ t('management.notSet') }}</el-tag>
              <el-button size="small" text type="primary" @click="createBlueprintVar(varInfo.name)">
                {{ t('management.setDefault') }}
              </el-button>
            </template>
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
          {{ t('management.noVariablesInTemplates') }}
        </div>
        <el-button
          class="new-var-btn"
          size="small"
          @click="createBlueprintVar()"
        >
          {{ t('management.newVariable') }}
        </el-button>
      </div>
      <VariableDialog />
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
import { ref, computed, onMounted, onUnmounted, watch, defineAsyncComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useBlueprintStore } from '../stores/blueprint'
import { useAgentStore } from '../stores/agent'
import { useVariableStore } from '../stores/variable'
import { fetchVariablesByScope, fetchBlueprintFileVersion } from '../api'
import DeriveAgentDialog from './DeriveAgentDialog.vue'
import BlueprintDiffView from './BlueprintDiffView.vue'
import VersionHistoryPanel from './VersionHistoryPanel.vue'
import VersionDiffView from './VersionDiffView.vue'
import VariableDialog from './VariableDialog.vue'
import { Search, Loading } from '@element-plus/icons-vue'

const CodeEditor = defineAsyncComponent(() => import('./CodeEditor.vue'))

const { t } = useI18n()
const store = useBlueprintStore()
const agentStore = useAgentStore()
const variableStore = useVariableStore()
const blueprintVarValues = ref({})

// Local state
const newName = ref('')
const newDescription = ref('')
const addFileDialogVisible = ref(false)
const newFilePath = ref('')
const variablesDrawerVisible = ref(false)

// Version history view state
const versionViewState = ref({
  mode: 'normal',
  versionNum: null,
  content: null,
  diffLines: null,
})

function exitVersionMode() {
  versionViewState.value = { mode: 'normal', versionNum: null, content: null, diffLines: null }
}

async function handleFetchVersionContent(version) {
  const bp = store.currentBlueprint
  if (!bp) throw new Error('No blueprint selected')
  const filePath = store.versionFilePath
  const detail = await fetchBlueprintFileVersion(bp.id, filePath, version.version_num)
  return detail.content
}

async function handleBpRestoreVersion(version) {
  await store.restoreVersion(store.versionFilePath, version.version_num)
}

function onVersionView({ content, versionNum }) {
  versionViewState.value = { mode: 'view', versionNum, content, diffLines: null }
}

function onVersionCompare({ diffLines, versionNum }) {
  versionViewState.value = { mode: 'compare', versionNum, content: null, diffLines }
}

function closeBlueprintVersionHistory() {
  store.closeVersionDrawer()
  exitVersionMode()
}

function onBlueprintVersionRestored() {
  exitVersionMode()
}

// Reset version view state when switching files
watch(() => store.currentFile, () => {
  exitVersionMode()
})

// File search
const collapsedSearchFiles = ref(new Set())
const blueprintTargetLine = ref(null)

function handleBlueprintSearch() {
  if (store.fileSearchQuery.trim()) {
    collapsedSearchFiles.value = new Set()
    store.searchBlueprintFiles(store.fileSearchQuery)
  }
}

function toggleSearchFile(filePath) {
  const next = new Set(collapsedSearchFiles.value)
  if (next.has(filePath)) next.delete(filePath)
  else next.add(filePath)
  collapsedSearchFiles.value = next
}

async function openSearchResult(filePath, lineNumber) {
  await store.selectFile(filePath)
  blueprintTargetLine.value = lineNumber
}

function highlightMatch(text, query) {
  if (!query) return text
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escaped})`, 'gi')
  return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(regex, '<mark>$1</mark>')
}

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

async function loadBlueprintVariables() {
  if (!store.currentBlueprint?.agent_id) return
  try {
    const vars = await fetchVariablesByScope('blueprint', store.currentBlueprint.agent_id)
    const map = {}
    for (const v of vars) {
      map[v.name] = v
    }
    blueprintVarValues.value = map
  } catch {
    blueprintVarValues.value = {}
  }
}

async function openVariablesDrawer() {
  variablesDrawerVisible.value = true
  await loadBlueprintVariables()
}

function editBlueprintVar(variable) {
  variableStore.openEditDialog(variable)
}

function createBlueprintVar(name = '') {
  variableStore.openCreateDialog({
    scope: 'blueprint',
    agent_id: store.currentBlueprint?.agent_id,
    name,
  })
}

watch(() => variableStore.dialogVisible, async (visible) => {
  if (!visible && variablesDrawerVisible.value) {
    await loadBlueprintVariables()
  }
})

function getPendingCount(blueprintId) {
  const bp = store.pendingChangesSummary.blueprints.find(b => b.blueprint_id === blueprintId)
  return bp?.pending_count || 0
}

function enterDiffView(bp) {
  store.currentBlueprint = bp
  store.viewMode = 'diff'
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

@media (max-width: 768px) {
  .editor-layout {
    flex-direction: column;
  }
  .file-tree-panel {
    width: 100% !important;
    min-width: unset;
    border-right: none;
    border-bottom: 1px solid var(--border-color, #333);
    padding-right: 0;
    max-height: 40vh;
  }
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

/* File search */
.search-box {
  padding: 6px 8px;
  flex-shrink: 0;
}
.search-loading, .search-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: #909399;
  font-size: 13px;
}
.search-summary {
  padding: 4px 8px;
  font-size: 11px;
  color: #909399;
}
.search-file-group {
  margin-bottom: 2px;
}
.search-file-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: #bbb;
  background: rgba(255, 255, 255, 0.03);
}
.search-file-header:hover {
  background: rgba(255, 255, 255, 0.06);
}
.search-file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}
.search-match-count {
  font-size: 10px;
  color: #909399;
  background: rgba(255, 255, 255, 0.1);
  padding: 0 6px;
  border-radius: 8px;
}
.search-match-item {
  display: flex;
  gap: 8px;
  padding: 3px 8px 3px 20px;
  cursor: pointer;
  font-size: 12px;
  line-height: 1.5;
  transition: background 0.15s;
}
.search-match-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.search-line-num {
  color: #909399;
  font-family: monospace;
  min-width: 28px;
  text-align: right;
  flex-shrink: 0;
}
.search-line-content {
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #bbb;
}
.search-line-content :deep(mark) {
  background: #ffd54f;
  color: #333;
  padding: 0 1px;
  border-radius: 2px;
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
.var-value-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 4px 8px;
}
.var-current-value {
  font-family: monospace;
  font-size: 12px;
  color: #606266;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.new-var-btn {
  margin-top: 16px;
  width: 100%;
}

/* Version history panel integration */
.editor-with-version-panel {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.editor-content-wrapper {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.version-mode-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: rgba(56, 139, 253, 0.1);
  border-bottom: 1px solid rgba(56, 139, 253, 0.3);
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
}
.version-compare-area, .version-view-area {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
</style>

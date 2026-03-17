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
      </div>
      <div v-loading="store.loading" class="editor-layout">
        <!-- Left: File tree -->
        <div class="file-tree-panel">
          <div class="file-section">
            <div class="section-header">{{ t('management.coreFiles') }}</div>
            <div
              v-for="f in coreFiles"
              :key="f.file_path"
              class="file-item"
              :class="{ active: store.currentFile?.file_path === f.file_path }"
              @click="store.selectFile(f.file_path)"
            >
              <span class="file-name">{{ f.file_path }}</span>
              <el-popconfirm
                :title="t('common.confirm') + '?'"
                @confirm="handleDeleteFile(f.file_path)"
              >
                <template #reference>
                  <el-button text size="small" type="danger" @click.stop>×</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <div class="file-section">
            <div class="section-header">{{ t('management.skillFiles') }}</div>
            <div
              v-for="f in skillFiles"
              :key="f.file_path"
              class="file-item"
              :class="{ active: store.currentFile?.file_path === f.file_path }"
              @click="store.selectFile(f.file_path)"
            >
              <span class="file-name">{{ f.file_path }}</span>
              <el-popconfirm
                :title="t('common.confirm') + '?'"
                @confirm="handleDeleteFile(f.file_path)"
              >
                <template #reference>
                  <el-button text size="small" type="danger" @click.stop>×</el-button>
                </template>
              </el-popconfirm>
            </div>
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
              <el-button
                type="primary"
                size="small"
                :loading="store.saving"
                @click="handleSave"
              >
                {{ t('common.save') }}
              </el-button>
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

    <!-- Create Blueprint Dialog -->
    <el-dialog
      v-model="store.createDialogVisible"
      :title="t('management.createBlueprint')"
      width="460px"
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
      <template #footer>
        <el-button @click="store.createDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleCreate">{{ t('common.confirm') }}</el-button>
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
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useBlueprintStore } from '../stores/blueprint'
import CodeEditor from './CodeEditor.vue'
import DeriveAgentDialog from './DeriveAgentDialog.vue'

const { t } = useI18n()
const store = useBlueprintStore()

// Local state
const newName = ref('')
const newDescription = ref('')
const addFileDialogVisible = ref(false)
const newFilePath = ref('')

onMounted(() => store.loadBlueprints())

// File tree computed
const coreFiles = computed(() =>
  store.currentBlueprint?.files?.filter(f => !f.file_path.startsWith('skills/')) || []
)
const skillFiles = computed(() =>
  store.currentBlueprint?.files?.filter(f => f.file_path.startsWith('skills/')) || []
)

// Build variable map for CodeEditor highlighting
const variableMap = computed(() => {
  const vars = store.currentBlueprint?.referenced_variables || []
  const map = {}
  for (const v of vars) {
    map[v] = { value: v }  // v is already a string (variable name)
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

// Handlers
async function handleCreate() {
  if (!newName.value.trim()) return
  try {
    await store.createNewBlueprint(newName.value.trim(), newDescription.value.trim())
    ElMessage.success(t('management.blueprintCreated'))
    store.createDialogVisible = false
    newName.value = ''
    newDescription.value = ''
  } catch {
    ElMessage.error(t('management.createFailed'))
  }
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
}
.file-section {
  margin-bottom: 12px;
}
.section-header {
  font-size: 12px;
  font-weight: bold;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  padding: 4px 0;
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
  overflow: hidden;
  text-overflow: ellipsis;
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
</style>

<template>
  <div class="file-toolbar">
    <div class="toolbar-left">
      <el-icon><Document /></el-icon>
      <span class="file-name">{{ store.currentFile?.name }}</span>
      <el-tag v-if="store.showTranslation" size="small" type="warning">{{ t('fileToolbar.chineseTranslation') }}</el-tag>
      <el-tag v-else size="small" type="info">{{ t('fileToolbar.original') }}</el-tag>
      <!-- Inherited from blueprint badge -->
      <el-tag
        v-if="store.derivationStatus?.is_derived && templateStore.isInherited"
        size="small"
        type="warning"
        effect="light"
      >📌 From blueprint (will detach on save)</el-tag>
    </div>
    <div class="toolbar-right">
      <!-- Restore to Blueprint button (for overridden files in derived agents) -->
      <el-popconfirm
        v-if="store.derivationStatus?.is_derived && store.isFileOverridden(store.currentFile?.path)"
        title="Restore this file to its blueprint version? Your local changes will be lost."
        confirm-button-text="Restore"
        :cancel-button-text="t('common.cancel')"
        confirm-button-type="danger"
        @confirm="doRestoreToBlueprint"
      >
        <template #reference>
          <el-button size="small" type="danger" :icon="Refresh">
            ↩ Restore to Blueprint
          </el-button>
        </template>
      </el-popconfirm>

      <!-- Batch translate button -->
      <el-button
        v-if="store.selectedFiles.size > 0"
        size="small"
        type="warning"
        :icon="MagicStick"
        :loading="store.batchTranslating"
        @click="doBatchTranslate"
      >
        {{ store.batchTranslating
          ? t('fileToolbar.translating', { current: store.batchProgress.current, total: store.batchProgress.total })
          : t('fileToolbar.batchTranslate', { count: store.selectedFiles.size }) }}
      </el-button>

      <!-- Translation toggle -->
      <el-button-group v-if="store.currentTranslation">
        <el-button
          size="small"
          :type="!store.showTranslation ? 'primary' : 'default'"
          @click="store.showTranslation = false"
        >{{ t('fileToolbar.originalText') }}</el-button>
        <el-button
          size="small"
          :type="store.showTranslation ? 'primary' : 'default'"
          @click="store.showTranslation = true"
        >{{ t('fileToolbar.translation') }}</el-button>
      </el-button-group>

      <!-- Translate button -->
      <el-button
        size="small"
        :icon="MagicStick"
        :loading="store.translating"
        @click="store.translate()"
      >
        {{ store.translating ? t('fileToolbar.translatingAction') : t('fileToolbar.translateAction') }}
      </el-button>

      <!-- Version history button -->
      <el-button
        v-if="store.isVersionManaged"
        size="small"
        :icon="Clock"
        :type="store.versionDrawerOpen ? 'primary' : 'default'"
        @click="store.versionDrawerOpen ? store.closeVersionDrawer() : store.openVersionDrawer()"
      >{{ t('fileToolbar.versionHistory') }}</el-button>

      <!-- Variables button -->
      <el-button
        v-if="store.currentAgent"
        size="small"
        :icon="Setting"
        @click="store.openVariablesDrawer()"
      >{{ t('fileToolbar.variables') }}</el-button>

      <!-- Edit / View toggle -->
      <el-button
        v-if="!store.isEditing"
        size="small"
        :icon="EditPen"
        @click="store.startEditing()"
      >{{ t('fileToolbar.edit') }}</el-button>
      <el-button
        v-else
        size="small"
        type="warning"
        :icon="View"
        @click="store.stopEditing()"
      >{{ t('fileToolbar.backToView') }}</el-button>

      <!-- Copy button -->
      <el-button
        size="small"
        :icon="DocumentCopy"
        @click="copyContent"
      >{{ t('fileToolbar.copy') }}</el-button>

      <!-- Save button -->
      <el-button
        v-if="store.isEditing"
        size="small"
        type="danger"
        :icon="Upload"
        :loading="store.saving"
        @click="showSaveDialog = true"
      >{{ t('fileToolbar.saveToFile') }}</el-button>
    </div>

    <!-- Save confirmation dialog -->
    <el-dialog
      v-model="showSaveDialog"
      :title="t('fileToolbar.saveFile')"
      width="440px"
      :close-on-click-modal="false"
      append-to-body
    >
      <div class="save-warning">{{ t('fileToolbar.saveConfirmMessage') }}</div>
      <el-input
        v-model="commitMsg"
        type="textarea"
        :rows="2"
        :placeholder="t('fileToolbar.editDescription')"
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="showSaveDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="danger" :loading="store.saving" @click="saveContent">{{ t('fileToolbar.confirmSave') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Document, EditPen, View, DocumentCopy, MagicStick, Upload, Clock, Refresh, Setting } from '@element-plus/icons-vue'
import { useAgentStore } from '../stores/agent'
import { useTemplateStore } from '../stores/template'
import { restoreToBlueprint } from '../api'

const { t } = useI18n()
const store = useAgentStore()
const templateStore = useTemplateStore()
const showSaveDialog = ref(false)
const commitMsg = ref('')

async function doBatchTranslate() {
  try {
    await store.batchTranslateSelected()
    ElMessage.success(t('fileToolbar.batchTranslateComplete'))
  } catch (e) {
    ElMessage.error(t('fileToolbar.batchTranslateFailed') + ': ' + (e.message || e))
  }
}

async function saveContent() {
  try {
    const msg = commitMsg.value.trim() || null
    await store.saveToFile(msg)
    ElMessage.success(t('fileToolbar.savedToFile'))
    showSaveDialog.value = false
    commitMsg.value = ''
  } catch (e) {
    ElMessage.error(t('fileToolbar.saveFailed') + ': ' + (e.response?.data?.detail || e.message || e))
  }
}

async function copyContent() {
  const content = store.isEditing
    ? store.editContent
    : store.displayContent
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success(t('fileToolbar.copiedToClipboard'))
  } catch {
    const ta = document.createElement('textarea')
    ta.value = content
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success(t('fileToolbar.copiedToClipboard'))
  }
}

async function doRestoreToBlueprint() {
  try {
    await restoreToBlueprint(store.currentAgent.name, store.currentFile.path)
    ElMessage.success('File restored to blueprint version')
    // Reload file content and derivation status
    await store.selectFile(store.currentFile.path)
    await store.loadDerivationStatus()
  } catch (e) {
    ElMessage.error('Restore failed: ' + (e.response?.data?.detail || e.message || e))
  }
}
</script>

<style scoped>
.file-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #fafbfc;
  border-bottom: 1px solid #e4e7ed;
  gap: 8px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
}
.file-name {
  color: #303133;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.save-warning {
  font-size: 14px;
  color: #e6a23c;
}
</style>

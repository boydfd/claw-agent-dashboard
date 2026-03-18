<template>
  <div class="file-toolbar">
    <div class="toolbar-left">
      <el-icon><Document /></el-icon>
      <span class="file-name">{{ store.currentFile?.name }}</span>
      <el-tag v-if="store.showTranslation" size="small" type="warning">{{ t('fileToolbar.chineseTranslation') }}</el-tag>
      <el-tag v-else size="small" type="info">{{ t('fileToolbar.original') }}</el-tag>
    </div>
    <div class="toolbar-right">
      <!-- Resync from Blueprint button (for overridden files in derived agents) -->
      <el-popconfirm
        v-if="store.derivationStatus?.is_derived && store.isFileOverridden(store.currentFile?.path)"
        :title="t('management.resyncConfirm', { file: store.currentFile?.name })"
        :confirm-button-text="t('management.confirmResync')"
        :cancel-button-text="t('common.cancel')"
        @confirm="doResync"
      >
        <template #reference>
          <el-button size="small" type="warning" :icon="Refresh">
            {{ t('management.resyncFromBlueprint') }}
          </el-button>
        </template>
      </el-popconfirm>

      <!-- Restore All from Blueprint button (for derived agents with any overrides) -->
      <el-popconfirm
        v-if="store.derivationStatus?.is_derived && hasAnyOverrides"
        :title="t('management.resyncAllConfirm')"
        :confirm-button-text="t('management.confirmResyncAll')"
        :cancel-button-text="t('common.cancel')"
        @confirm="doResyncAll"
      >
        <template #reference>
          <el-button size="small" type="danger" :icon="Refresh">
            {{ t('management.resyncAllFromBlueprint') }}
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
        @click="store.openVersionDrawer()"
      >{{ t('fileToolbar.versionHistory') }}</el-button>

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
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Document, EditPen, View, DocumentCopy, MagicStick, Upload, Clock, Refresh } from '@element-plus/icons-vue'
import { useAgentStore } from '../stores/agent'
import { resyncFile, resyncAll } from '../api'

const { t } = useI18n()
const store = useAgentStore()
const showSaveDialog = ref(false)
const commitMsg = ref('')

const hasAnyOverrides = computed(() => {
  const files = store.derivationStatus?.files
  return files?.some(f => f.is_overridden) || false
})

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

async function doResync() {
  try {
    await resyncFile(store.currentAgent.name, store.currentFile.path)
    ElMessage.success(t('management.resyncSuccess'))
    // Reload file content and derivation status
    await store.selectFile(store.currentFile.path)
    await store.loadDerivationStatus()
  } catch (e) {
    ElMessage.error(t('management.resyncFailed'))
  }
}

async function doResyncAll() {
  try {
    await resyncAll(store.currentAgent.name)
    ElMessage.success(t('management.resyncAllSuccess'))
    // Reload current file and derivation status
    if (store.currentFile) {
      await store.selectFile(store.currentFile.path)
    }
    await store.loadDerivationStatus()
  } catch (e) {
    ElMessage.error(t('management.resyncAllFailed'))
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

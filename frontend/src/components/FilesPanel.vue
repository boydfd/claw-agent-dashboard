<template>
  <div class="files-panel" :class="{ 'mobile-layout': isMobile }">
    <!-- File tree (desktop always, mobile when no file selected) -->
    <div
      v-if="!isMobile || !hasFileSelected"
      class="file-tree-pane"
      :style="!isMobile ? { width: treeWidth + 'px' } : {}"
    >
      <FileTreePanel />
    </div>

    <!-- Draggable divider (desktop only) -->
    <div v-if="!isMobile" class="split-divider" @mousedown="startDrag"></div>

    <!-- File viewer (desktop always, mobile when file selected) -->
    <div
      v-if="!isMobile || hasFileSelected"
      class="file-viewer-pane"
    >
      <!-- Mobile back button -->
      <div v-if="isMobile && hasFileSelected" class="mobile-back-bar">
        <el-button text @click="store.currentFile = null">
          <el-icon><ArrowLeft /></el-icon> {{ t('mainPanel.files') }}
        </el-button>
      </div>
      <FileViewer />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useAgentStore } from '../stores/agent'
import { useResponsive } from '../composables/useResponsive'
import FileTreePanel from './FileTreePanel.vue'
import FileViewer from './FileViewer.vue'

const { t } = useI18n()
const store = useAgentStore()
const { isMobile } = useResponsive()

const hasFileSelected = computed(() => !!store.currentFile)

const treeWidth = ref(240)
let isDragging = false
let dragStartX = 0
let dragStartWidth = 0

function startDrag(e) {
  isDragging = true
  dragStartX = e.clientX
  dragStartWidth = treeWidth.value
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onDrag(e) {
  if (!isDragging) return
  const delta = e.clientX - dragStartX
  treeWidth.value = Math.max(160, Math.min(400, dragStartWidth + delta))
}

function stopDrag() {
  isDragging = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onUnmounted(() => {
  stopDrag()
})
</script>

<style scoped>
.files-panel {
  display: flex;
  height: 100%;
  overflow: hidden;
}
.files-panel.mobile-layout {
  flex-direction: column;
}
.files-panel.mobile-layout .file-tree-pane {
  width: 100% !important;
  border-right: none;
  flex: 1;
}
.files-panel.mobile-layout .file-viewer-pane {
  flex: 1;
}
.file-tree-pane {
  flex-shrink: 0;
  overflow: hidden;
  border-right: 1px solid #e4e7ed;
}
.split-divider {
  width: 6px;
  cursor: col-resize;
  background: transparent;
  flex-shrink: 0;
  transition: background 0.15s;
}
.split-divider:hover {
  background: #c0c4cc;
}
.file-viewer-pane {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.mobile-back-bar {
  padding: 6px 8px;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}
</style>

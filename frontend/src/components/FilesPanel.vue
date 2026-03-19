<template>
  <div class="files-panel">
    <!-- File tree -->
    <div class="file-tree-pane" :style="{ width: treeWidth + 'px' }">
      <FileTreePanel />
    </div>

    <!-- Draggable divider -->
    <div class="split-divider" @mousedown="startDrag"></div>

    <!-- File viewer -->
    <div class="file-viewer-pane">
      <FileViewer />
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import FileTreePanel from './FileTreePanel.vue'
import FileViewer from './FileViewer.vue'

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
}
</style>

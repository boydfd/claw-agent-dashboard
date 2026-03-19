<template>
  <div class="file-viewer">
    <!-- Empty state: no file selected -->
    <div v-if="!store.currentFile" class="empty-state">
      <div class="empty-icon">📂</div>
      <p>{{ t('mainPanel.selectFile') }}</p>
    </div>

    <!-- File content -->
    <div v-else class="file-content">
      <!-- Toolbar -->
      <FileToolbar />

      <!-- Template render warnings -->
      <div v-if="templateStore.renderWarnings.length > 0" class="render-warnings">
        <el-alert
          :title="`${templateStore.renderWarnings.length} unresolved variable(s)`"
          type="warning"
          :closable="false"
          show-icon
        />
      </div>

      <!-- Loading -->
      <div v-if="store.loading" class="content-loading">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      </div>

      <!-- Editor mode -->
      <div v-else-if="store.isEditing" class="editor-wrapper">
        <CodeEditor
          :value="store.editContent"
          :language="store.displayLanguage"
          :variable-map="variableMap"
          @update:value="store.editContent = $event"
        />
      </div>

      <!-- View mode -->
      <div v-else class="view-wrapper">
        <MarkdownRenderer
          v-if="store.displayLanguage === 'markdown'"
          :content="store.displayContent"
        />
        <div v-else class="code-view">
          <pre><code v-html="highlightedCode"></code></pre>
        </div>
      </div>

      <!-- Footer: file path -->
      <div class="file-footer">
        <span class="host-path">📁 {{ store.currentFile.host_path }}</span>
      </div>
    </div>

    <!-- Version history drawer -->
    <VersionDrawer />

    <!-- Agent variables drawer -->
    <AgentVariablesDrawer />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loading } from '@element-plus/icons-vue'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { useAgentStore } from '../stores/agent'
import { useTemplateStore } from '../stores/template'
import { fetchAgentVariables } from '../api'
import FileToolbar from './FileToolbar.vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import CodeEditor from './CodeEditor.vue'
import VersionDrawer from './VersionDrawer.vue'
import AgentVariablesDrawer from './AgentVariablesDrawer.vue'

const { t } = useI18n()
const store = useAgentStore()
const templateStore = useTemplateStore()

const variableMap = ref({})

// Load variables when template loads (for CodeEditor hover tooltips)
watch(() => templateStore.currentTemplate, async (tmpl) => {
  if (tmpl && store.currentAgent?.id) {
    try {
      const vars = await fetchAgentVariables(store.currentAgent.id)
      const map = {}
      for (const v of vars) {
        map[v.name] = { value: v.value, scope: v.scope, type: v.type }
      }
      variableMap.value = map
    } catch {
      variableMap.value = {}
    }
  } else {
    variableMap.value = {}
  }
})

const highlightedCode = computed(() => {
  if (!store.currentFile) return ''
  const lang = store.displayLanguage
  const code = store.displayContent
  try {
    if (hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
  } catch {}
  return hljs.highlightAuto(code).value
})
</script>

<style scoped>
.file-viewer {
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
  font-size: 64px;
  margin-bottom: 16px;
}
.file-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.content-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.view-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.editor-wrapper {
  flex: 1;
  overflow: hidden;
}
.code-view {
  font-size: 14px;
  line-height: 1.6;
}
.code-view pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
.file-footer {
  padding: 8px 16px;
  background: #f5f7fa;
  border-top: 1px solid #e4e7ed;
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
}
.render-warnings {
  padding: 0 16px;
}
.host-path {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

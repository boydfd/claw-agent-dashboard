<template>
  <div class="file-viewer">
    <!-- Empty state: no file selected -->
    <div v-if="!store.currentFile" class="empty-state">
      <div class="empty-icon">📂</div>
      <p>{{ t('mainPanel.selectFile') }}</p>
    </div>

    <!-- File content with optional version history panel -->
    <div v-else class="file-content-wrapper">
      <div class="file-content">
        <!-- Toolbar -->
        <FileToolbar />

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

        <!-- Compare mode: show diff -->
        <div v-else-if="versionViewState.mode === 'compare'" class="version-compare-area">
          <VersionDiffView :diffLines="versionViewState.diffLines" />
        </div>

        <!-- View mode: read-only content -->
        <div v-else-if="versionViewState.mode === 'view'" class="version-view-area">
          <CodeEditor
            :value="versionViewState.content"
            :language="store.displayLanguage"
            :readOnly="true"
          />
        </div>

        <!-- Normal: Editor mode -->
        <div v-else-if="store.isEditing" class="editor-wrapper">
          <CodeEditor
            :value="store.editContent"
            :language="store.displayLanguage"
            :variable-map="variableMap"
            @update:value="store.editContent = $event"
          />
        </div>

        <!-- Normal: View mode -->
        <div v-else ref="viewWrapperRef" class="view-wrapper">
          <MarkdownRenderer
            v-if="store.displayLanguage === 'markdown'"
            ref="markdownRef"
            :content="store.displayContent"
          />
          <div v-else class="code-view">
            <pre class="code-view-pre"><div
              v-for="line in highlightedLines"
              :key="line.num"
              class="code-line"
              :class="{ 'highlight-fade': line.num === highlightLineNum }"
              :data-line="line.num"
              v-html="line.html || '&nbsp;'"
            ></div></pre>
          </div>
        </div>

        <!-- Footer: file path -->
        <div class="file-footer">
          <span class="host-path">📁 {{ store.currentFile.host_path }}</span>
        </div>
      </div>

      <!-- Version History Panel -->
      <VersionHistoryPanel
        v-if="store.versionDrawerOpen"
        :versions="store.versionList"
        :loading="store.versionLoading"
        :hasMore="store.versionList.length < store.versionTotal"
        :fetchContent="handleFetchVersionContent"
        :onRestore="handleRestoreVersion"
        :latestContent="store.currentFile?.content || ''"
        @view="onVersionView"
        @compare="onVersionCompare"
        @close="closeVersionHistory"
        @restore="onVersionRestored"
        @load-more="store.fetchMoreVersions()"
      />
    </div>

    <!-- Agent variables drawer -->
    <AgentVariablesDrawer />
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loading } from '@element-plus/icons-vue'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { useAgentStore } from '../stores/agent'
import { useTemplateStore } from '../stores/template'
import { fetchAgentVariables, fetchVersionDetail } from '../api'
import FileToolbar from './FileToolbar.vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import CodeEditor from './CodeEditor.vue'
import VersionHistoryPanel from './VersionHistoryPanel.vue'
import VersionDiffView from './VersionDiffView.vue'
import AgentVariablesDrawer from './AgentVariablesDrawer.vue'

const { t } = useI18n()
const store = useAgentStore()
const templateStore = useTemplateStore()

const viewWrapperRef = ref(null)
const markdownRef = ref(null)
const variableMap = ref({})

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
  const detail = await fetchVersionDetail(version.id)
  return detail.content
}

async function handleRestoreVersion(version) {
  await store.restoreVersion(version.id)
}

function onVersionView({ content, versionNum }) {
  versionViewState.value = { mode: 'view', versionNum, content, diffLines: null }
}

function onVersionCompare({ diffLines, versionNum }) {
  versionViewState.value = { mode: 'compare', versionNum, content: null, diffLines }
}

function closeVersionHistory() {
  store.closeVersionDrawer()
  exitVersionMode()
}

function onVersionRestored() {
  exitVersionMode()
}

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

// Tag-balancing line splitter for hljs output
function splitHtmlLines(html) {
  const rawLines = html.split('\n')
  const result = []
  let openTags = [] // stack of '<span class="...">' strings

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i]
    // Prepend carried-over open tags, will close them at end
    const prefix = openTags.join('')

    // Scan this line for <span> opens and </span> closes to update stack
    const tagRegex = /<(\/?)span([^>]*)>/g
    let match
    while ((match = tagRegex.exec(line)) !== null) {
      if (match[1] === '/') {
        openTags.pop()
      } else {
        openTags.push(`<span${match[2]}>`)
      }
    }

    // Close all currently-open spans at end of this line (visual only)
    result.push({
      num: i + 1,
      html: prefix + line + '</span>'.repeat(openTags.length),
    })
    // openTags carries forward to next line (re-opened via prefix)
  }
  return result
}

const highlightedLines = computed(() => {
  if (!store.currentFile) return []
  const lang = store.displayLanguage
  const code = store.displayContent
  let html
  try {
    if (hljs.getLanguage(lang)) {
      html = hljs.highlight(code, { language: lang }).value
    } else {
      html = hljs.highlightAuto(code).value
    }
  } catch {
    html = hljs.highlightAuto(code).value
  }
  return splitHtmlLines(html)
})

const highlightLineNum = ref(null)
let highlightTimeout = null

watch(() => store.targetLineNumber, async (lineNum) => {
  if (!lineNum) return
  await nextTick()
  if (highlightTimeout) clearTimeout(highlightTimeout)

  if (store.displayLanguage === 'markdown') {
    // Markdown mode: find the target line text in rendered DOM
    const container = markdownRef.value?.$el
    if (container) {
      const query = store.fileSearchQuery
      if (!query) { store.targetLineNumber = null; return }

      // Count how many times the query appears in source lines BEFORE lineNum
      const sourceLines = (store.displayContent || '').split('\n')
      let occurrenceBefore = 0
      for (let i = 0; i < lineNum - 1; i++) {
        if ((sourceLines[i] || '').toLowerCase().includes(query.toLowerCase())) {
          occurrenceBefore++
        }
      }

      // Walk the rendered DOM and find the Nth occurrence of query text
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
      let targetNode = null
      let matchCount = 0
      while (walker.nextNode()) {
        if (walker.currentNode.textContent.toLowerCase().includes(query.toLowerCase())) {
          if (matchCount === occurrenceBefore) {
            targetNode = walker.currentNode
            break
          }
          matchCount++
        }
      }
      if (targetNode) {
        // Find the closest block-level parent to highlight
        let block = targetNode.parentElement
        const blockTags = new Set(['P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'LI', 'BLOCKQUOTE', 'PRE', 'TR', 'DIV', 'TABLE'])
        while (block && block !== container && !blockTags.has(block.tagName)) {
          block = block.parentElement
        }
        if (block && block !== container) {
          block.scrollIntoView({ block: 'center' })
          block.classList.add('md-highlight-fade')
          highlightTimeout = setTimeout(() => {
            block.classList.remove('md-highlight-fade')
            highlightTimeout = null
          }, 4000)
        }
      }
    }
  } else {
    // Code view mode
    highlightLineNum.value = lineNum
    const el = document.querySelector(`.code-line[data-line="${lineNum}"]`)
    if (el) {
      el.scrollIntoView({ block: 'center' })
    }
    highlightTimeout = setTimeout(() => {
      highlightLineNum.value = null
      highlightTimeout = null
    }, 4000)
  }

  store.targetLineNumber = null
}, { flush: 'post' })
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
.file-content-wrapper {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
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
.code-line {
  min-height: 1em;
}
@keyframes highlight-fade {
  0%   { background: rgba(255, 213, 79, 0.5); }
  100% { background: transparent; }
}
.code-line.highlight-fade {
  animation: highlight-fade 4s ease-out forwards;
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

<style>
/* Markdown highlight (unscoped so it applies inside MarkdownRenderer's v-html) */
@keyframes md-highlight-fade {
  0%   { background: rgba(255, 213, 79, 0.5); }
  100% { background: transparent; }
}
.md-highlight-fade {
  animation: md-highlight-fade 4s ease-out forwards;
}
</style>

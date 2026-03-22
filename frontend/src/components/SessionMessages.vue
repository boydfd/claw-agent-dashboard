<template>
  <div class="session-messages">
    <!-- Loading state -->
    <div v-if="loading && !messages.length" class="messages-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      Loading messages...
    </div>

    <!-- Message list + pagination -->
    <template v-else-if="messages.length">
      <!-- Pagination top -->
      <div class="pagination-bar">
        <span class="page-info mono">{{ total }} messages</span>
        <el-pagination
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next, jumper"
          small
          @current-change="onPageChange"
        />
      </div>

      <!-- Messages -->
      <div class="messages-list" ref="messagesListRef">
        <div
          v-for="(msg, idx) in filteredMessages"
          :key="idx"
          class="message-item"
          :class="'message-' + msg.role"
        >
          <!-- Message header: time + role tag -->
          <div class="message-header">
            <span class="message-time mono">{{ formatTime(msg.timestamp) }}</span>
            <el-tag :type="roleTagType(msg.role)" size="small" class="role-tag">
              {{ msg.role }}
            </el-tag>
            <span v-if="msg.model && viewMode === 'detailed'" class="message-model mono">{{ msg.provider ? `${msg.provider}/${msg.model}` : msg.model }}</span>
            <span v-if="msg.usage && viewMode === 'detailed'" class="message-usage mono">
              {{ formatTokenCount(msg.usage.input || 0) }}in / {{ formatTokenCount(msg.usage.output || 0) }}out
            </span>
          </div>

          <!-- Content blocks -->
          <div class="message-content">
            <div
              v-for="(block, bidx) in msg.content"
              :key="bidx"
              class="content-block"
              :class="'block-' + block.type"
            >
              <!-- Text block: markdown for user/assistant, plain for others -->
              <template v-if="block.type === 'text'">
                <div
                  v-if="shouldRenderMarkdown(msg.role)"
                  class="markdown-content"
                >
                  <div
                    class="md-rendered markdown-body"
                    :class="{ collapsed: isBlockCollapsed(idx, bidx, block.text) }"
                    v-html="renderMarkdown(block.text)"
                    @click.self="toggleBlock(idx, bidx)"
                  ></div>
                  <div
                    v-if="isLongContent(block.text)"
                    class="expand-hint"
                    @click="toggleBlock(idx, bidx)"
                  >
                    {{ isBlockCollapsed(idx, bidx, block.text) ? `Click to expand (${countLines(block.text)} lines)` : 'Click to collapse' }}
                  </div>
                </div>
                <div v-else class="text-content"
                  :class="{ collapsed: isBlockCollapsed(idx, bidx, block.text), clickable: isLongContent(block.text) }"
                  @click="toggleBlock(idx, bidx)"
                >
                  <pre class="text-pre" v-text="getDisplayText(idx, bidx, block.text)"></pre>
                  <div
                    v-if="isLongContent(block.text)"
                    class="expand-hint"
                    @click.stop="toggleBlock(idx, bidx)"
                  >
                    {{ isBlockCollapsed(idx, bidx, block.text) ? `Click to expand (${countLines(block.text)} lines)` : 'Click to collapse' }}
                  </div>
                </div>
              </template>

              <!-- Thinking block -->
              <template v-else-if="block.type === 'thinking'">
                <div
                  class="thinking-header"
                  @click="toggleBlock(idx, bidx)"
                >
                  <el-icon class="thinking-icon"><View /></el-icon>
                  <span class="thinking-label">Thinking</span>
                  <el-icon class="expand-arrow">
                    <component :is="isBlockCollapsed(idx, bidx, block.text) ? 'ArrowRight' : 'ArrowDown'" />
                  </el-icon>
                </div>
                <div v-if="!isBlockCollapsed(idx, bidx, block.text)" class="thinking-content">
                  <pre class="text-pre" v-text="block.text"></pre>
                </div>
              </template>

              <!-- Tool call block -->
              <template v-else-if="block.type === 'toolCall'">
                <div class="tool-call">
                  <el-icon class="tool-icon"><Setting /></el-icon>
                  <span class="tool-name mono">{{ block.name }}</span>
                  <span
                    v-if="block.arguments"
                    class="tool-args clickable"
                    :class="{ collapsed: isBlockCollapsed(idx, bidx, block.arguments) }"
                    @click="toggleBlock(idx, bidx)"
                  >
                    <pre class="text-pre" v-text="getDisplayText(idx, bidx, formatArguments(block.arguments))"></pre>
                  </span>
                </div>
                <div
                  v-if="block.arguments && isLongContent(formatArguments(block.arguments))"
                  class="expand-hint"
                  @click="toggleBlock(idx, bidx)"
                >
                  {{ isBlockCollapsed(idx, bidx, block.arguments) ? 'Click to expand arguments' : 'Click to collapse' }}
                </div>
              </template>

              <!-- Tool result block: smart display with mode switch -->
              <template v-else-if="block.type === 'toolResult'">
                <div
                  class="tool-result"
                  :class="{ 'tool-error': block.isError }"
                >
                  <div class="tool-result-header">
                    <el-icon><component :is="block.isError ? 'CircleCloseFilled' : 'CircleCheckFilled'" /></el-icon>
                    <span>{{ block.isError ? 'Error' : 'Result' }}</span>
                    <!-- Mode switch buttons -->
                    <div class="mode-switch">
                      <el-button-group size="small">
                        <el-button
                          :type="getResultMode(idx, bidx, block.text) === 'markdown' ? 'primary' : ''"
                          text
                          size="small"
                          @click.stop="setResultMode(idx, bidx, 'markdown')"
                        >MD</el-button>
                        <el-button
                          :type="getResultMode(idx, bidx, block.text) === 'text' ? 'primary' : ''"
                          text
                          size="small"
                          @click.stop="setResultMode(idx, bidx, 'text')"
                        >Text</el-button>
                        <el-button
                          v-if="isJsonParseable(block.text)"
                          :type="getResultMode(idx, bidx, block.text) === 'json' ? 'primary' : ''"
                          text
                          size="small"
                          @click.stop="setResultMode(idx, bidx, 'json')"
                        >JSON</el-button>
                      </el-button-group>
                    </div>
                  </div>

                  <!-- JSON mode -->
                  <div v-if="getResultMode(idx, bidx, block.text) === 'json' && isJsonParseable(block.text)" class="json-content">
                    <pre class="hljs"><code v-html="highlightJson(block.text)"></code></pre>
                  </div>
                  <!-- Markdown mode -->
                  <div v-else-if="getResultMode(idx, bidx, block.text) === 'markdown'" class="markdown-content">
                    <div
                      class="md-rendered markdown-body"
                      :class="{ collapsed: isBlockCollapsed(idx, bidx, block.text) }"
                      v-html="renderMarkdown(block.text || '')"
                    ></div>
                    <div
                      v-if="isLongContent(block.text)"
                      class="expand-hint"
                      @click="toggleBlock(idx, bidx)"
                    >
                      {{ isBlockCollapsed(idx, bidx, block.text) ? `Click to expand` : 'Click to collapse' }}
                    </div>
                  </div>
                  <!-- Text mode (default fallback) -->
                  <div v-else class="text-content"
                    :class="{ collapsed: isBlockCollapsed(idx, bidx, block.text), clickable: isLongContent(block.text) }"
                    @click="toggleBlock(idx, bidx)"
                  >
                    <pre class="text-pre" v-text="getDisplayText(idx, bidx, block.text)"></pre>
                    <div
                      v-if="isLongContent(block.text)"
                      class="expand-hint"
                      @click.stop="toggleBlock(idx, bidx)"
                    >
                      {{ isBlockCollapsed(idx, bidx, block.text) ? `Click to expand` : 'Click to collapse' }}
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination bottom -->
      <div class="pagination-bar bottom">
        <el-pagination
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          small
          @current-change="onPageChange"
        />
      </div>
    </template>

    <!-- Empty state -->
    <div v-else class="messages-empty">
      No messages found in this session
    </div>

    <!-- Compose bar -->
    <div class="compose-bar" v-if="sessionKey">
      <div class="compose-toolbar">
        <div class="toggle-group">
          <el-button-group size="small">
            <el-button :type="viewMode === 'chat' ? 'primary' : ''" @click="viewMode = 'chat'">
              {{ t('sessionCompose.viewChat') }}
            </el-button>
            <el-button :type="viewMode === 'detailed' ? 'primary' : ''" @click="viewMode = 'detailed'">
              {{ t('sessionCompose.viewDetail') }}
            </el-button>
          </el-button-group>
        </div>
        <div class="toggle-group">
          <el-button-group size="small">
            <el-button :type="sendMode === 'envelope' ? 'primary' : ''" @click="sendMode = 'envelope'">
              {{ t('sessionCompose.modeEnvelope') }}
            </el-button>
            <el-button :type="sendMode === 'raw' ? 'primary' : ''" @click="sendMode = 'raw'">
              {{ t('sessionCompose.modeRaw') }}
            </el-button>
          </el-button-group>
        </div>
        <span v-if="sendMode === 'envelope' && fromName" class="from-name-tag" @click="showFromDialog = true; fromInput = fromName">
          {{ fromName }}
        </span>
      </div>
      <div class="compose-input">
        <el-input
          v-model="composeText"
          type="textarea"
          :rows="2"
          :placeholder="t('sessionCompose.placeholder')"
          @keydown="handleKeydown"
          :disabled="sending"
        />
        <el-button
          type="primary"
          :disabled="!canSend"
          :loading="sending"
          @click="handleSend"
        >
          {{ sending ? t('sessionCompose.sending') : t('sessionCompose.send') }}
        </el-button>
      </div>
    </div>

    <!-- From name dialog -->
    <el-dialog v-model="showFromDialog" :title="t('sessionCompose.fromLabel')" width="360px" append-to-body>
      <el-input v-model="fromInput" :placeholder="t('sessionCompose.fromPlaceholder')" @keydown.enter="saveFromName" />
      <template #footer>
        <el-button @click="showFromDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveFromName" :disabled="!fromInput.trim()">OK</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, watch, nextTick, computed } from 'vue'
import { Loading, View, Setting, ArrowRight, ArrowDown, CircleCloseFilled, CircleCheckFilled } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { useI18n } from 'vue-i18n'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useAgentStore } from '../stores/agent'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  loading: { type: Boolean, default: false },
  targetMessageIndex: { type: Number, default: null },
  sessionKey: { type: String, default: '' },
  agentName: { type: String, default: '' },
  sessionStatus: { type: String, default: '' },
})

const emit = defineEmits(['page-change', 'highlight-done'])

const messagesListRef = ref(null)

// Search result highlight: watch both targetMessageIndex and messages
// to handle async page load timing
let msgHighlightTimeout = null

watch(
  [() => props.targetMessageIndex, () => props.messages],
  async ([msgIndex, msgs]) => {
    if (msgIndex == null || !msgs.length) return
    await nextTick()

    if (msgHighlightTimeout) clearTimeout(msgHighlightTimeout)

    const localIdx = msgIndex % props.pageSize
    const items = messagesListRef.value?.querySelectorAll('.message-item')
    if (items && items[localIdx]) {
      items[localIdx].classList.add('highlight-fade')
      items[localIdx].scrollIntoView({ block: 'center', behavior: 'smooth' })
      msgHighlightTimeout = setTimeout(() => {
        items[localIdx]?.classList.remove('highlight-fade')
        msgHighlightTimeout = null
      }, 4000)
    }
    emit('highlight-done')
  },
  { flush: 'post' }
)

// markdown-it instance (shared with MarkdownRenderer pattern)
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
      } catch { /* fallthrough */ }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  },
})

// Track which blocks are expanded
const expandedBlocks = reactive({})
// Track toolResult display mode per block: 'json' | 'markdown' | 'text'
const resultModes = reactive({})

const COLLAPSE_THRESHOLD = 8 // lines
const COLLAPSE_CHAR_THRESHOLD = 500 // chars — catches long single-line content (images, base64, URLs)

function blockKey(msgIdx, blockIdx) {
  return `${msgIdx}-${blockIdx}`
}

function countLines(text) {
  if (!text || typeof text !== 'string') return 0
  return text.split('\n').length
}

function isLongContent(text) {
  if (!text || typeof text !== 'string') return false
  return countLines(text) > COLLAPSE_THRESHOLD || text.length > COLLAPSE_CHAR_THRESHOLD
}

function isBlockCollapsed(msgIdx, blockIdx, text) {
  const key = blockKey(msgIdx, blockIdx)
  if (key in expandedBlocks) {
    return !expandedBlocks[key]
  }
  return isLongContent(text)
}

function toggleBlock(msgIdx, blockIdx) {
  const key = blockKey(msgIdx, blockIdx)
  if (key in expandedBlocks) {
    expandedBlocks[key] = !expandedBlocks[key]
  } else {
    expandedBlocks[key] = true
  }
}

function getDisplayText(msgIdx, blockIdx, text) {
  if (!text || typeof text !== 'string') return ''
  if (isBlockCollapsed(msgIdx, blockIdx, text)) {
    const lines = text.split('\n')
    // Truncate by lines if multi-line
    if (lines.length > COLLAPSE_THRESHOLD) {
      return lines.slice(0, COLLAPSE_THRESHOLD).join('\n') + '\n...'
    }
    // Truncate by chars if single long line (e.g., base64 image)
    if (text.length > COLLAPSE_CHAR_THRESHOLD) {
      return text.substring(0, COLLAPSE_CHAR_THRESHOLD) + '...'
    }
  }
  return text
}

// Markdown rendering
function renderMarkdown(text) {
  if (!text || typeof text !== 'string') return ''
  return md.render(text)
}

function shouldRenderMarkdown(role) {
  return role === 'user' || role === 'assistant'
}

// JSON detection and highlighting
function isJsonParseable(text) {
  if (!text || typeof text !== 'string') return false
  const trimmed = text.trim()
  if (!(trimmed.startsWith('{') || trimmed.startsWith('['))) return false
  try {
    JSON.parse(trimmed)
    return true
  } catch {
    return false
  }
}

function highlightJson(text) {
  if (!text || typeof text !== 'string') return ''
  try {
    const formatted = JSON.stringify(JSON.parse(text.trim()), null, 2)
    return hljs.highlight(formatted, { language: 'json' }).value
  } catch {
    return md.utils.escapeHtml(text)
  }
}

// toolResult mode management
function getResultMode(msgIdx, blockIdx, text) {
  const key = blockKey(msgIdx, blockIdx)
  if (key in resultModes) return resultModes[key]
  // Default: json if parseable, else markdown
  return isJsonParseable(text) ? 'json' : 'markdown'
}

function setResultMode(msgIdx, blockIdx, mode) {
  const key = blockKey(msgIdx, blockIdx)
  resultModes[key] = mode
}

function formatArguments(args) {
  if (!args) return ''
  if (typeof args === 'string') {
    try {
      const parsed = JSON.parse(args)
      return JSON.stringify(parsed, null, 2)
    } catch {
      return args
    }
  }
  return JSON.stringify(args, null, 2)
}

function formatTime(timestamp) {
  if (!timestamp) return '--:--:--'
  try {
    const d = new Date(timestamp)
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return timestamp.substring(11, 19) || '--:--:--'
  }
}

function roleTagType(role) {
  const map = {
    user: '',
    assistant: 'success',
    system: 'warning',
    toolResult: 'info',
  }
  return map[role] || 'info'
}

function formatTokenCount(count) {
  if (count >= 1_000_000) return (count / 1_000_000).toFixed(1) + 'M'
  if (count >= 1000) return Math.round(count / 1000) + 'k'
  return String(count)
}

function onPageChange(page) {
  // Clear expanded states when changing page
  Object.keys(expandedBlocks).forEach(k => delete expandedBlocks[k])
  Object.keys(resultModes).forEach(k => delete resultModes[k])
  emit('page-change', page)
  nextTick(() => {
    if (messagesListRef.value) {
      messagesListRef.value.scrollTop = 0
    }
  })
}

const store = useAgentStore()
const { t } = useI18n()

// Compose state
const viewMode = ref(localStorage.getItem('session-compose:viewMode') || 'detailed')
const sendMode = ref(localStorage.getItem('session-compose:sendMode') || 'envelope')
const composeText = ref('')
const sending = ref(false)
const fromName = ref(localStorage.getItem('session-compose:from') || '')
const showFromDialog = ref(false)
const fromInput = ref('')

// Persist mode changes
watch(viewMode, (v) => localStorage.setItem('session-compose:viewMode', v))
watch(sendMode, (v) => localStorage.setItem('session-compose:sendMode', v))

function stripDirectiveTags(text) {
  if (!text || (!text.includes('[[') && !text.includes('MEDIA:'))) return text
  return text
    .replace(/\[\[\s*(?:reply_to_current|reply_to\s*:\s*[^\]\n]+)\s*\]\]/gi, '')
    .replace(/\[\[\s*audio_as_voice\s*\]\]/gi, '')
    .replace(/^MEDIA:\S+.*$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

const filteredMessages = computed(() => {
  if (viewMode.value === 'detailed') return props.messages
  return props.messages
    .filter(msg => {
      if (msg.role === 'user') return true
      if (msg.role === 'assistant') {
        return msg.content?.some(b => b.type === 'text' && b.text?.trim())
      }
      return false
    })
    .map(msg => {
      if (msg.role !== 'assistant') return msg
      const filtered = msg.content
        .filter(b => b.type === 'text' && b.text?.trim())
        .map(b => ({ ...b, text: stripDirectiveTags(b.text) }))
        .filter(b => b.text?.trim())
      return { ...msg, content: filtered }
    })
    .filter(msg => msg.role !== 'assistant' || msg.content?.length > 0)
})

const canSend = computed(() => composeText.value.trim().length > 0 && !sending.value)
const isAgentBusy = computed(() => props.sessionStatus === 'working')

async function handleSend() {
  if (!canSend.value) return
  if (sendMode.value === 'envelope' && !fromName.value) {
    showFromDialog.value = true
    fromInput.value = ''
    return
  }
  if (isAgentBusy.value) {
    try {
      await ElMessageBox.confirm(t('sessionCompose.busyConfirm'), { type: 'warning' })
    } catch { return }
  }
  sending.value = true
  try {
    const envelopeContext = sendMode.value === 'envelope' ? {
      channel: 'agent-preview',
      sender: fromName.value,
      chat_type: 'group',
    } : undefined
    const result = await store.sendMessage(
      props.agentName, props.sessionKey, composeText.value,
      sendMode.value, envelopeContext,
    )
    if (result.ok) {
      composeText.value = ''
      ElMessage.success(t('sessionCompose.sendSuccess'))
    } else {
      ElMessage.error(result.error || t('sessionCompose.sendError'))
    }
  } catch (e) {
    ElMessage.error(t('sessionCompose.sendError'))
  } finally {
    sending.value = false
  }
}

function saveFromName() {
  fromName.value = fromInput.value.trim()
  localStorage.setItem('session-compose:from', fromName.value)
  showFromDialog.value = false
  if (fromName.value) handleSend()
}

function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    handleSend()
  } else if (e.key === 'Escape') {
    composeText.value = ''
  }
}
</script>

<style scoped>
.session-messages {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.messages-loading,
.messages-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 40px 16px;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  justify-content: center;
  flex: 1;
}

/* Pagination */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  flex-shrink: 0;
}

.pagination-bar.bottom {
  border-bottom: none;
  border-top: 1px solid var(--el-border-color-extra-light);
  justify-content: center;
}

.page-info {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* Messages */
.messages-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.message-item {
  padding: 10px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  border-left: 3px solid transparent;
}

.message-item:last-child {
  margin-bottom: 0;
}

@keyframes highlight-fade {
  0%   { background: rgba(255, 213, 79, 0.5); }
  100% { background: transparent; }
}
.message-item.highlight-fade {
  animation: highlight-fade 4s ease-out forwards;
}

.message-user {
  border-left-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.message-assistant {
  border-left-color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}

.message-system {
  border-left-color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}

.message-toolResult {
  border-left-color: var(--el-color-info);
  background: var(--el-fill-color-light);
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.message-time {
  color: var(--el-text-color-placeholder);
  font-size: 11px;
  flex-shrink: 0;
}

.role-tag {
  flex-shrink: 0;
}

.message-model {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.message-usage {
  color: var(--el-text-color-placeholder);
  font-size: 10px;
  margin-left: auto;
}

.mono {
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
}

/* Content blocks */
.content-block {
  margin-bottom: 6px;
}

.content-block:last-child {
  margin-bottom: 0;
}

/* Markdown rendered content */
.markdown-content {
  position: relative;
}

.md-rendered {
  font-size: 13px;
  line-height: 1.6;
}

.md-rendered.collapsed {
  max-height: 200px;
  overflow: hidden;
  position: relative;
  word-break: break-all;
}

.md-rendered.collapsed::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40px;
  background: linear-gradient(transparent, var(--el-bg-color-overlay));
  pointer-events: none;
}

.message-user .md-rendered.collapsed::after {
  background: linear-gradient(transparent, var(--el-color-primary-light-9));
}
.message-assistant .md-rendered.collapsed::after {
  background: linear-gradient(transparent, var(--el-color-success-light-9));
}

/* Plain text content */
.text-content {
  position: relative;
}

.text-content.clickable {
  cursor: pointer;
}

.text-content.collapsed {
  position: relative;
}

.text-content.collapsed::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 24px;
  background: linear-gradient(transparent, var(--el-bg-color-overlay));
  pointer-events: none;
}

.message-user .text-content.collapsed::after {
  background: linear-gradient(transparent, var(--el-color-primary-light-9));
}
.message-assistant .text-content.collapsed::after {
  background: linear-gradient(transparent, var(--el-color-success-light-9));
}
.message-system .text-content.collapsed::after {
  background: linear-gradient(transparent, var(--el-color-warning-light-9));
}

.text-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
  line-height: 1.5;
  color: var(--el-text-color-regular);
}

.expand-hint {
  text-align: center;
  font-size: 11px;
  color: var(--el-color-primary);
  cursor: pointer;
  padding: 4px 0;
  user-select: none;
}

.expand-hint:hover {
  text-decoration: underline;
}

/* Thinking block */
.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  font-size: 12px;
  color: var(--el-text-color-secondary);
  user-select: none;
}

.thinking-header:hover {
  background: var(--el-fill-color);
}

.thinking-icon {
  color: var(--el-color-warning);
}

.thinking-label {
  font-weight: 500;
  font-style: italic;
}

.expand-arrow {
  margin-left: auto;
  font-size: 12px;
}

.thinking-content {
  padding: 8px 10px;
  margin-top: 4px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  border-left: 2px solid var(--el-color-warning-light-5);
  max-height: 400px;
  overflow-y: auto;
}

.thinking-content .text-pre {
  color: var(--el-text-color-secondary);
  font-style: italic;
}

/* Tool call block */
.tool-call {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  font-size: 12px;
}

.tool-icon {
  color: var(--el-color-primary);
  margin-top: 2px;
  flex-shrink: 0;
}

.tool-name {
  font-weight: 600;
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.tool-args {
  flex: 1;
  min-width: 0;
}

.tool-args.clickable {
  cursor: pointer;
}

.tool-args .text-pre {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

/* Tool result block */
.tool-result {
  padding: 6px 10px;
  border-radius: 4px;
  background: var(--el-fill-color-lighter);
  border-left: 2px solid var(--el-color-success-light-5);
}

.tool-result.tool-error {
  background: var(--el-color-danger-light-9);
  border-left-color: var(--el-color-danger);
}

.tool-result-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  color: var(--el-color-success);
  margin-bottom: 6px;
}

.tool-error .tool-result-header {
  color: var(--el-color-danger);
}

.mode-switch {
  margin-left: auto;
}

.mode-switch .el-button {
  font-size: 10px;
  padding: 2px 6px;
}

/* JSON content */
.json-content {
  max-height: 400px;
  overflow: auto;
  border-radius: 4px;
}

.json-content pre {
  margin: 0;
  padding: 8px;
  font-size: 12px;
  background: #f6f8fa;
  border-radius: 4px;
}

.json-content code {
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
}

/* Compose bar */
.compose-bar {
  border-top: 1px solid var(--el-border-color);
  padding: 8px 12px;
  background: var(--el-bg-color);
  flex-shrink: 0;
}

.compose-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.compose-input {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.compose-input .el-textarea {
  flex: 1;
}

.compose-input .el-button {
  flex-shrink: 0;
  height: 54px;
}

.from-name-tag {
  font-size: 12px;
  color: var(--el-color-primary);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
}

.from-name-tag:hover {
  background: var(--el-color-primary-light-7);
}

@media (max-width: 768px) {
  .compose-toolbar {
    gap: 4px;
  }
  .compose-input .el-button {
    height: 40px;
  }
}
</style>

<!-- Global markdown-body styles (unscoped) -->
<style>
.session-messages .markdown-body {
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}
.session-messages .markdown-body h1 { font-size: 1.4em; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 0.2em; margin: 0.5em 0; }
.session-messages .markdown-body h2 { font-size: 1.2em; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 0.2em; margin: 0.4em 0; }
.session-messages .markdown-body h3 { font-size: 1.1em; margin: 0.4em 0; }
.session-messages .markdown-body p { margin: 0.3em 0; }
.session-messages .markdown-body ul, .session-messages .markdown-body ol { padding-left: 1.5em; margin: 0.3em 0; }
.session-messages .markdown-body li { margin: 0.15em 0; }
.session-messages .markdown-body blockquote {
  border-left: 3px solid var(--el-border-color);
  padding: 0 0.8em;
  color: var(--el-text-color-secondary);
  margin: 0.3em 0;
}
.session-messages .markdown-body code {
  background: rgba(0,0,0,0.06);
  padding: 0.15em 0.3em;
  border-radius: 3px;
  font-size: 85%;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
}
.session-messages .markdown-body pre {
  background: #f6f8fa;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0.4em 0;
}
.session-messages .markdown-body pre code {
  background: none;
  padding: 0;
  font-size: 12px;
}
.session-messages .markdown-body table {
  border-collapse: collapse;
  margin: 0.4em 0;
  font-size: 12px;
}
.session-messages .markdown-body th, .session-messages .markdown-body td {
  border: 1px solid var(--el-border-color-lighter);
  padding: 4px 8px;
}
.session-messages .markdown-body th {
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.session-messages .markdown-body a {
  color: var(--el-color-primary);
  text-decoration: none;
}
.session-messages .markdown-body a:hover {
  text-decoration: underline;
}
.session-messages .markdown-body img {
  max-width: 100%;
}
</style>

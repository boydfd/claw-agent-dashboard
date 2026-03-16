import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchAgents,
  fetchAgentFiles,
  fetchAgentSkills,
  fetchSkillFiles,
  fetchFileContent,
  fetchTranslation,
  translateFile as apiTranslate,
  saveFile as apiSaveFile,
  fetchAgentMemory,
  fetchAgentOtherFiles,
  fetchGlobalSkillSources,
  fetchGlobalSkills,
  fetchGlobalSkillFiles,
  fetchGlobalSkillFileContent,
  batchTranslate as apiBatchTranslate,
  fetchAgentDetail,
  fetchSessionMessages,
  fetchModels,
  createNewSession as apiCreateNewSession,
  fetchFileVersions as apiFetchVersions,
  fetchVersionDetail as apiFetchVersionDetail,
  restoreVersion as apiRestoreVersion,
  fetchVersionDiff as apiFetchVersionDiff,
} from '../api'
import { useTemplateStore } from './template'

export const useAgentStore = defineStore('agent', () => {
  // State
  const agents = ref([])
  const currentAgent = ref(null)
  const agentFiles = ref([])
  const agentSkills = ref([])
  const skillFilesMap = ref({})
  const currentFile = ref(null)
  const currentTranslation = ref(null)
  const showTranslation = ref(false)
  const isEditing = ref(false)
  const editContent = ref('')
  const loading = ref(false)
  const translating = ref(false)
  const saving = ref(false)

  // Feature 1: Memory files
  const agentMemory = ref([])

  // Feature 2: Other files
  const agentOtherFiles = ref([])

  // Feature 3: Global Skills
  const globalSkillSources = ref([])
  const globalSkills = ref({})        // { source: [skills] }
  const globalSkillFilesMap = ref({}) // { "source/skillName": [files] }

  // Feature 4: Batch translate
  const selectedFiles = ref(new Set())
  const batchTranslating = ref(false)
  const batchProgress = ref({ current: 0, total: 0 })

  // Status dashboard
  const agentDetail = ref(null)
  const statusLoading = ref(false)
  let statusInterval = null

  // Session messages (expandable session cards)
  const expandedSessions = ref(new Set())
  const sessionMessages = ref({})       // { sessionId: { messages: [], total: 0, has_more: false } }
  const sessionMessagesLoading = ref({}) // { sessionId: bool }

  // Session panel (split pane selection + pagination)
  const selectedSessionId = ref(null)
  const sessionPage = ref(1)             // current page number (1-based)
  const sessionPageSize = ref(50)

  // New session
  const availableModels = ref([])
  const defaultModel = ref(null)

  // Actions
  async function loadAgents() {
    loading.value = true
    try {
      agents.value = await fetchAgents()
    } finally {
      loading.value = false
    }
  }

  async function selectAgent(agent) {
    currentAgent.value = agent
    currentFile.value = null
    currentTranslation.value = null
    showTranslation.value = false
    isEditing.value = false
    selectedFiles.value = new Set()
    loading.value = true
    try {
      const [files, skills, memory, otherFiles] = await Promise.all([
        fetchAgentFiles(agent.name),
        fetchAgentSkills(agent.name),
        fetchAgentMemory(agent.name),
        fetchAgentOtherFiles(agent.name),
      ])
      agentFiles.value = files
      agentSkills.value = skills
      agentMemory.value = memory
      agentOtherFiles.value = otherFiles
      skillFilesMap.value = {}
      // Load agent detail
      await loadAgentDetail()
    } finally {
      loading.value = false
    }
  }

  async function selectAgentByName(shortName) {
    if (!shortName) {
      currentAgent.value = null
      return
    }
    // Ensure agents are loaded
    if (agents.value.length === 0) {
      await loadAgents()
    }
    const fullName = `workspace-${shortName}`
    const agent = agents.value.find(a => a.name === fullName)
    if (agent) {
      await selectAgent(agent)
    }
    // If not found, currentAgent stays null → empty state shown
  }

  async function loadSkillFiles(skillName) {
    if (skillFilesMap.value[skillName]) return
    const files = await fetchSkillFiles(currentAgent.value.name, skillName)
    skillFilesMap.value[skillName] = files
  }

  async function selectFile(path) {
    if (!currentAgent.value) return
    loading.value = true
    showTranslation.value = false
    isEditing.value = false
    try {
      currentFile.value = await fetchFileContent(currentAgent.value.name, path)
      editContent.value = currentFile.value.content
      // Check translation
      if (currentFile.value.has_translation) {
        try {
          currentTranslation.value = await fetchTranslation(currentAgent.value.name, path)
        } catch {
          currentTranslation.value = null
        }
      } else {
        currentTranslation.value = null
      }
      // Template layer: load template (lazy-creates if needed)
      const templateStore = useTemplateStore()
      if (currentAgent.value?.id) {
        await templateStore.loadTemplate(currentAgent.value.id, currentFile.value.path)
        // Use rendered content for preview display
        currentFile.value.content = templateStore.renderedContent
        // Template raw content for editing
        editContent.value = templateStore.currentTemplate?.content || currentFile.value.content
      }
    } finally {
      loading.value = false
    }
  }

  async function translate() {
    if (!currentAgent.value || !currentFile.value) return
    translating.value = true
    try {
      currentTranslation.value = await apiTranslate(
        currentAgent.value.name,
        currentFile.value.path
      )
      showTranslation.value = true
      currentFile.value.has_translation = true
    } finally {
      translating.value = false
    }
  }

  function toggleTranslation() {
    showTranslation.value = !showTranslation.value
  }

  function startEditing() {
    const templateStore = useTemplateStore()
    let content
    if (templateStore.currentTemplate) {
      // Template mode: edit raw template with ${VAR} placeholders
      content = templateStore.currentTemplate.content
    } else if (showTranslation.value && currentTranslation.value) {
      content = currentTranslation.value.content
    } else {
      content = currentFile.value?.content || ''
    }
    editContent.value = content
    isEditing.value = true
  }

  function stopEditing() {
    isEditing.value = false
  }

  async function saveToFile(commitMsg = null) {
    if (!currentAgent.value || !currentFile.value) return
    saving.value = true
    try {
      const templateStore = useTemplateStore()
      if (templateStore.currentTemplate) {
        await templateStore.saveTemplate(editContent.value, commitMsg)
        currentFile.value.content = templateStore.renderedContent
        return true
      }
      // else: fallback to existing direct save for global files
      await apiSaveFile(currentAgent.value.name, currentFile.value.path, editContent.value, commitMsg)
      // Update the in-memory content
      currentFile.value.content = editContent.value
      return true
    } finally {
      saving.value = false
    }
  }

  // Feature 1: Load memory files
  async function loadMemory() {
    if (!currentAgent.value) return
    agentMemory.value = await fetchAgentMemory(currentAgent.value.name)
  }

  // Feature 3: Global Skills actions
  async function loadGlobalSkillSources() {
    globalSkillSources.value = await fetchGlobalSkillSources()
  }

  async function loadGlobalSkills(source) {
    if (globalSkills.value[source]) return
    const skills = await fetchGlobalSkills(source)
    globalSkills.value = { ...globalSkills.value, [source]: skills }
  }

  async function loadGlobalSkillFiles(source, skillName) {
    const key = `${source}/${skillName}`
    if (globalSkillFilesMap.value[key]) return
    const files = await fetchGlobalSkillFiles(source, skillName)
    globalSkillFilesMap.value = { ...globalSkillFilesMap.value, [key]: files }
  }

  async function selectGlobalFile(source, path) {
    loading.value = true
    showTranslation.value = false
    isEditing.value = false
    try {
      const templateStore = useTemplateStore()
      templateStore.clearTemplate()
      currentFile.value = await fetchGlobalSkillFileContent(source, path)
      currentFile.value._globalSource = source
      editContent.value = currentFile.value.content
      // Check translation
      const pseudoAgent = `__global_${source}__`
      if (currentFile.value.has_translation) {
        try {
          currentTranslation.value = await fetchTranslation(pseudoAgent, path)
        } catch {
          currentTranslation.value = null
        }
      } else {
        currentTranslation.value = null
      }
    } finally {
      loading.value = false
    }
  }

  // Feature 4: Batch translate actions
  function toggleFileSelection(agent, path) {
    const key = `${agent}::${path}`
    const newSet = new Set(selectedFiles.value)
    if (newSet.has(key)) {
      newSet.delete(key)
    } else {
      newSet.add(key)
    }
    selectedFiles.value = newSet
  }

  function isFileSelected(agent, path) {
    return selectedFiles.value.has(`${agent}::${path}`)
  }

  function clearSelection() {
    selectedFiles.value = new Set()
  }

  async function batchTranslateSelected() {
    if (selectedFiles.value.size === 0) return
    batchTranslating.value = true
    batchProgress.value = { current: 0, total: selectedFiles.value.size }

    const items = Array.from(selectedFiles.value).map((key) => {
      const [agent, ...rest] = key.split('::')
      const path = rest.join('::')
      return { agent, path }
    })

    try {
      const response = await apiBatchTranslate(items)
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6))
              if (event.type === 'progress' || event.type === 'translated' || event.type === 'error') {
                batchProgress.value = { current: event.current, total: event.total }
              }
              if (event.type === 'done') {
                batchProgress.value = { current: event.total, total: event.total }
              }
            } catch {
              // ignore parse errors
            }
          }
        }
      }
    } finally {
      batchTranslating.value = false
      selectedFiles.value = new Set()
    }
  }

  // Status dashboard actions
  async function loadAgentDetail() {
    if (!currentAgent.value) return
    statusLoading.value = true
    try {
      // Map workspace-xxx to agents/xxx for the API
      const name = currentAgent.value.name.replace('workspace-', '')
      agentDetail.value = await fetchAgentDetail(`agents/${name}`)
    } catch (e) {
      console.error('Failed to load agent detail:', e)
      agentDetail.value = null
    } finally {
      statusLoading.value = false
    }
  }

  function startStatusAutoRefresh(intervalMs = 10000) {
    stopStatusAutoRefresh()
    statusInterval = setInterval(() => {
      loadAgentDetail()
      _autoRefreshSessionMessages()
    }, intervalMs)
  }

  function stopStatusAutoRefresh() {
    if (statusInterval) {
      clearInterval(statusInterval)
      statusInterval = null
    }
  }

  async function _autoRefreshSessionMessages() {
    const sid = selectedSessionId.value
    if (!sid || !currentAgent.value) return
    const existing = sessionMessages.value[sid]
    if (!existing) return
    const total = existing.total || 0
    const limit = sessionPageSize.value
    const lastPage = Math.max(1, Math.ceil(total / limit))
    // Only auto-refresh if user is on the last page (viewing newest messages)
    if (sessionPage.value !== lastPage && total > 0) return
    // Reload last page — jumpToLast recalculates total and fetches latest
    const name = currentAgent.value.name.replace('workspace-', '')
    try {
      const probe = await fetchSessionMessages(`agents/${name}`, sid, 0, 1)
      const newTotal = probe.total || 0
      if (newTotal === total && newTotal > 0) return // no new messages, skip
      const newLastPage = Math.max(1, Math.ceil(newTotal / limit))
      const lastOffset = (newLastPage - 1) * limit
      const data = await fetchSessionMessages(`agents/${name}`, sid, lastOffset, limit)
      sessionMessages.value = { ...sessionMessages.value, [sid]: data }
      sessionPage.value = newLastPage
    } catch (e) {
      // Silently ignore auto-refresh errors
    }
  }

  // Session messages actions
  function toggleSessionExpand(sessionId) {
    const newSet = new Set(expandedSessions.value)
    if (newSet.has(sessionId)) {
      newSet.delete(sessionId)
    } else {
      newSet.add(sessionId)
      // Auto-load messages on first expand
      if (!sessionMessages.value[sessionId]) {
        loadSessionMessages(sessionId)
      }
    }
    expandedSessions.value = newSet
  }

  function isSessionExpanded(sessionId) {
    return expandedSessions.value.has(sessionId)
  }

  async function loadSessionMessages(sessionId, offset = 0, limit = 50) {
    if (!currentAgent.value) return
    const name = currentAgent.value.name.replace('workspace-', '')

    sessionMessagesLoading.value = { ...sessionMessagesLoading.value, [sessionId]: true }
    try {
      const data = await fetchSessionMessages(`agents/${name}`, sessionId, offset, limit)
      if (offset === 0) {
        // Fresh load
        sessionMessages.value = {
          ...sessionMessages.value,
          [sessionId]: data,
        }
      } else {
        // Append (load more)
        const existing = sessionMessages.value[sessionId] || { messages: [] }
        sessionMessages.value = {
          ...sessionMessages.value,
          [sessionId]: {
            messages: [...existing.messages, ...data.messages],
            total: data.total,
            has_more: data.has_more,
          },
        }
      }
    } catch (e) {
      console.error('Failed to load session messages:', e)
    } finally {
      sessionMessagesLoading.value = { ...sessionMessagesLoading.value, [sessionId]: false }
    }
  }

  function loadMoreSessionMessages(sessionId) {
    const existing = sessionMessages.value[sessionId]
    if (!existing || !existing.has_more) return
    const offset = existing.messages.length
    loadSessionMessages(sessionId, offset, 50)
  }

  // Session panel actions (split pane + pagination)
  function selectSession(sessionId) {
    selectedSessionId.value = sessionId
    // Default to last page — we need to first load page 1 to know total, then jump
    sessionPage.value = 1
    loadSessionPage(sessionId, 1, true)
  }

  async function loadSessionPage(sessionId, page, jumpToLast = false) {
    if (!currentAgent.value) return
    const name = currentAgent.value.name.replace('workspace-', '')
    const limit = sessionPageSize.value
    const offset = (page - 1) * limit

    sessionMessagesLoading.value = { ...sessionMessagesLoading.value, [sessionId]: true }
    try {
      if (jumpToLast) {
        // First request: offset=0 limit=1 to get total, then compute last page
        const probe = await fetchSessionMessages(`agents/${name}`, sessionId, 0, 1)
        const total = probe.total || 0
        const lastPage = Math.max(1, Math.ceil(total / limit))
        sessionPage.value = lastPage
        const lastOffset = (lastPage - 1) * limit
        const data = await fetchSessionMessages(`agents/${name}`, sessionId, lastOffset, limit)
        sessionMessages.value = {
          ...sessionMessages.value,
          [sessionId]: data,
        }
      } else {
        sessionPage.value = page
        const data = await fetchSessionMessages(`agents/${name}`, sessionId, offset, limit)
        sessionMessages.value = {
          ...sessionMessages.value,
          [sessionId]: data,
        }
      }
    } catch (e) {
      console.error('Failed to load session page:', e)
    } finally {
      sessionMessagesLoading.value = { ...sessionMessagesLoading.value, [sessionId]: false }
    }
  }

  // New session actions
  async function loadModels() {
    try {
      const data = await fetchModels()
      availableModels.value = data.models || []
      defaultModel.value = data.default || null
    } catch (e) {
      console.error('Failed to load models:', e)
      availableModels.value = []
      defaultModel.value = null
    }
  }

  async function createSession(agent, model, message, sessionKey) {
    return await apiCreateNewSession(agent, model, message, sessionKey)
  }

  // Computed
  const displayContent = computed(() => {
    if (showTranslation.value && currentTranslation.value) {
      return currentTranslation.value.content
    }
    return currentFile.value?.content || ''
  })

  const displayLanguage = computed(() => {
    return currentFile.value?.language || 'plaintext'
  })

  // Version history
  const versionDrawerOpen = ref(false)
  const versionList = ref([])
  const versionTotal = ref(0)
  const versionLoading = ref(false)
  const versionDiff = ref(null)
  const versionPreview = ref(null) // version content being previewed

  const isVersionManaged = computed(() => {
    if (!currentFile.value) return false
    const path = currentFile.value.path || ''
    // Core .md files at root or skills/* files
    if (path.startsWith('skills/')) return true
    if (!path.includes('/') && path.endsWith('.md')) return true
    return false
  })

  async function fetchVersions(limit = 20, offset = 0) {
    if (!currentAgent.value || !currentFile.value) return
    versionLoading.value = true
    try {
      const data = await apiFetchVersions(
        currentAgent.value.name, currentFile.value.path, limit, offset
      )
      versionList.value = data.versions
      versionTotal.value = data.total
    } catch (e) {
      console.error('Failed to fetch versions:', e)
      versionList.value = []
      versionTotal.value = 0
    } finally {
      versionLoading.value = false
    }
  }

  async function fetchVersionDetail(versionId) {
    return await apiFetchVersionDetail(versionId)
  }

  async function restoreVersion(versionId) {
    if (!currentAgent.value || !currentFile.value) return
    const result = await apiRestoreVersion(
      currentAgent.value.name, currentFile.value.path, versionId
    )
    // Refresh file content and version list
    currentFile.value = await fetchFileContent(currentAgent.value.name, currentFile.value.path)
    editContent.value = currentFile.value.content
    await fetchVersions()
    return result
  }

  async function fetchDiff(fromId, toId) {
    if (!currentAgent.value || !currentFile.value) return
    const data = await apiFetchVersionDiff(
      currentAgent.value.name, currentFile.value.path, fromId, toId
    )
    versionDiff.value = data.diff
    return data.diff
  }

  function openVersionDrawer() {
    versionDrawerOpen.value = true
    versionDiff.value = null
    versionPreview.value = null
    fetchVersions()
  }

  function closeVersionDrawer() {
    versionDrawerOpen.value = false
    versionDiff.value = null
    versionPreview.value = null
  }

  return {
    agents,
    currentAgent,
    agentFiles,
    agentSkills,
    skillFilesMap,
    currentFile,
    currentTranslation,
    showTranslation,
    isEditing,
    editContent,
    loading,
    translating,
    saving,
    displayContent,
    displayLanguage,
    // Feature 1: Memory
    agentMemory,
    loadMemory,
    // Feature 2: Other files
    agentOtherFiles,
    // Feature 3: Global Skills
    globalSkillSources,
    globalSkills,
    globalSkillFilesMap,
    loadGlobalSkillSources,
    loadGlobalSkills,
    loadGlobalSkillFiles,
    selectGlobalFile,
    // Feature 4: Batch translate
    selectedFiles,
    batchTranslating,
    batchProgress,
    toggleFileSelection,
    isFileSelected,
    clearSelection,
    batchTranslateSelected,
    // Core actions
    loadAgents,
    selectAgent,
    selectAgentByName,
    loadSkillFiles,
    selectFile,
    translate,
    toggleTranslation,
    startEditing,
    stopEditing,
    saveToFile,
    // Status dashboard
    agentDetail,
    statusLoading,
    loadAgentDetail,
    startStatusAutoRefresh,
    stopStatusAutoRefresh,
    // Session messages
    expandedSessions,
    sessionMessages,
    sessionMessagesLoading,
    toggleSessionExpand,
    isSessionExpanded,
    loadSessionMessages,
    loadMoreSessionMessages,
    // Session panel (split pane + pagination)
    selectedSessionId,
    sessionPage,
    sessionPageSize,
    selectSession,
    loadSessionPage,
    // New session
    availableModels,
    defaultModel,
    loadModels,
    createSession,
    // Version history
    versionDrawerOpen,
    versionList,
    versionTotal,
    versionLoading,
    versionDiff,
    versionPreview,
    isVersionManaged,
    fetchVersions,
    fetchVersionDetail,
    restoreVersion,
    fetchDiff,
    openVersionDrawer,
    closeVersionDrawer,
  }
})

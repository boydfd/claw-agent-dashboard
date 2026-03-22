import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchBlueprints,
  createBlueprint as apiCreate,
  fetchBlueprint,
  updateBlueprint as apiUpdate,
  deleteBlueprint as apiDelete,
  fetchBlueprintFiles,
  addBlueprintFile as apiAddFile,
  fetchBlueprintFile,
  updateBlueprintFile as apiUpdateFile,
  deleteBlueprintFile as apiDeleteFile,
  fetchBlueprintVariables,
  deriveAgent as apiDerive,
  fetchPendingChangesSummary,
  fetchBlueprintPendingChanges,
  acceptPendingChange as apiAcceptChange,
  rejectPendingChange as apiRejectChange,
  acceptAllPendingChanges as apiAcceptAll,
  fetchBlueprintFileVersions,
  fetchBlueprintFileVersion,
  restoreBlueprintFileVersion,
} from '../api'

export const useBlueprintStore = defineStore('blueprint', () => {
  // State
  const blueprints = ref([])
  const loading = ref(false)
  const currentBlueprint = ref(null)  // selected for editing
  const currentFile = ref(null)       // selected file in editor
  const editContent = ref('')
  const saving = ref(false)

  // Dialogs
  const createDialogVisible = ref(false)
  const deriveDialogVisible = ref(false)
  const deriveBlueprintId = ref(null)

  // View mode: 'list' or 'editor'
  const viewMode = ref('list')

  // Pending changes (filesystem sync)
  const pendingChangesSummary = ref({ blueprints: [], total_pending: 0 })
  const currentPendingChanges = ref(null)  // detailed changes for one blueprint
  const pendingLoading = ref(false)
  const pollTimer = ref(null)

  // Version history
  const versionDrawerOpen = ref(false)
  const versionFilePath = ref(null)
  const versionList = ref([])
  const versionTotal = ref(0)
  const versionLoading = ref(false)

  // File search
  const fileSearchQuery = ref('')
  const fileSearchResults = ref(null)
  const fileSearchLoading = ref(false)

  // Actions
  async function loadBlueprints() {
    loading.value = true
    try {
      blueprints.value = await fetchBlueprints()
    } finally {
      loading.value = false
    }
  }

  async function selectBlueprint(blueprintId) {
    loading.value = true
    try {
      currentBlueprint.value = await fetchBlueprint(blueprintId)
      currentFile.value = null
      editContent.value = ''
      viewMode.value = 'editor'
    } finally {
      loading.value = false
    }
  }

  function backToList() {
    viewMode.value = 'list'
    currentBlueprint.value = null
    currentFile.value = null
    editContent.value = ''
  }

  async function selectFile(filePath) {
    if (!currentBlueprint.value) return
    loading.value = true
    try {
      const template = await fetchBlueprintFile(currentBlueprint.value.id, filePath)
      currentFile.value = {
        file_path: template.file_path,
        content: template.content,
        id: template.id,
      }
      editContent.value = template.content
    } finally {
      loading.value = false
    }
  }

  async function saveCurrentFile() {
    if (!currentBlueprint.value || !currentFile.value) return
    saving.value = true
    try {
      await apiUpdateFile(
        currentBlueprint.value.id,
        currentFile.value.file_path,
        editContent.value
      )
      currentFile.value.content = editContent.value
      // Refresh blueprint to update variable list etc.
      currentBlueprint.value = await fetchBlueprint(currentBlueprint.value.id)
    } finally {
      saving.value = false
    }
  }

  async function addFile(filePath, content = '') {
    if (!currentBlueprint.value) return
    const template = await apiAddFile(currentBlueprint.value.id, {
      file_path: filePath,
      content: content,
    })
    // Refresh
    currentBlueprint.value = await fetchBlueprint(currentBlueprint.value.id)
    return template
  }

  async function deleteFile(filePath) {
    if (!currentBlueprint.value) return
    await apiDeleteFile(currentBlueprint.value.id, filePath)
    if (currentFile.value?.file_path === filePath) {
      currentFile.value = null
      editContent.value = ''
    }
    currentBlueprint.value = await fetchBlueprint(currentBlueprint.value.id)
  }

  async function createNewBlueprint(name, description, sourceAgentId = null, excludePatterns = null) {
    const data = { name, description }
    if (sourceAgentId) {
      data.source_agent_id = sourceAgentId
    }
    if (excludePatterns && excludePatterns.length > 0) {
      data.exclude_patterns = excludePatterns
    }
    const bp = await apiCreate(data)
    await loadBlueprints()
    return bp
  }

  async function deleteBlueprint(blueprintId, confirm = false) {
    const result = await apiDelete(blueprintId, confirm)
    if (result.deleted) {
      await loadBlueprints()
    }
    return result
  }

  function openDeriveDialog(blueprintId) {
    deriveBlueprintId.value = blueprintId
    deriveDialogVisible.value = true
  }

  async function derive(blueprintId, agentName, variables, createOpenclaw) {
    return await apiDerive(blueprintId, {
      agent_name: agentName,
      variables: variables,
      create_openclaw_agent: createOpenclaw,
    })
  }

  // --- Pending Changes ---
  async function loadPendingChangesSummary() {
    try {
      pendingChangesSummary.value = await fetchPendingChangesSummary()
    } catch (e) {
      console.error('Failed to load pending changes summary:', e)
    }
  }

  async function loadBlueprintPendingChanges(blueprintId) {
    pendingLoading.value = true
    try {
      currentPendingChanges.value = await fetchBlueprintPendingChanges(blueprintId)
    } finally {
      pendingLoading.value = false
    }
  }

  async function acceptChange(blueprintId, changeId) {
    const result = await apiAcceptChange(blueprintId, changeId)
    await loadBlueprintPendingChanges(blueprintId)
    await loadPendingChangesSummary()
    return result
  }

  async function rejectChange(blueprintId, changeId) {
    const result = await apiRejectChange(blueprintId, changeId)
    await loadBlueprintPendingChanges(blueprintId)
    await loadPendingChangesSummary()
    return result
  }

  async function acceptAllChanges(blueprintId) {
    const result = await apiAcceptAll(blueprintId)
    await loadBlueprintPendingChanges(blueprintId)
    await loadPendingChangesSummary()
    return result
  }

  function startPendingPolling() {
    if (pollTimer.value) return
    loadPendingChangesSummary()
    pollTimer.value = setInterval(loadPendingChangesSummary, 30000)
  }

  function stopPendingPolling() {
    if (pollTimer.value) {
      clearInterval(pollTimer.value)
      pollTimer.value = null
    }
  }

  // --- Version History ---
  async function openVersionDrawer(filePath) {
    if (!currentBlueprint.value) return
    versionFilePath.value = filePath
    versionList.value = []
    versionTotal.value = 0
    versionDrawerOpen.value = true
    versionLoading.value = true
    try {
      const data = await fetchBlueprintFileVersions(currentBlueprint.value.id, filePath)
      versionList.value = data.versions
      versionTotal.value = data.total
    } catch (e) {
      console.error('[blueprint] Failed to load version history:', e)
      ElMessage.error(e?.response?.data?.detail || e.message || 'Failed to load version history')
    } finally {
      versionLoading.value = false
    }
  }

  function closeVersionDrawer() {
    versionDrawerOpen.value = false
    versionFilePath.value = null
    versionList.value = []
    versionTotal.value = 0
  }

  async function fetchMoreVersions() {
    if (!currentBlueprint.value || !versionFilePath.value) return
    versionLoading.value = true
    try {
      const data = await fetchBlueprintFileVersions(
        currentBlueprint.value.id, versionFilePath.value, 20, versionList.value.length
      )
      versionList.value.push(...data.versions)
      versionTotal.value = data.total
    } finally {
      versionLoading.value = false
    }
  }

  async function restoreVersion(filePath, versionNum) {
    if (!currentBlueprint.value) return
    await restoreBlueprintFileVersion(currentBlueprint.value.id, filePath, versionNum)
    const data = await fetchBlueprintFileVersions(
      currentBlueprint.value.id, filePath, 20, 0
    )
    versionList.value = data.versions
    versionTotal.value = data.total
    if (currentFile.value && currentFile.value.file_path === filePath) {
      await selectFile(currentFile.value.file_path)
    }
  }

  // --- File Search ---
  async function searchBlueprintFiles(query) {
    if (!currentBlueprint.value?.name || !query.trim()) {
      fileSearchResults.value = null
      return
    }
    fileSearchLoading.value = true
    try {
      const { searchFiles: searchFilesApi } = await import('../api')
      const result = await searchFilesApi('blueprint', currentBlueprint.value.name, query)
      fileSearchResults.value = result
    } catch (e) {
      console.error('Blueprint file search failed:', e)
      fileSearchResults.value = { query, total_matches: 0, results: [] }
    } finally {
      fileSearchLoading.value = false
    }
  }

  function clearFileSearch() {
    fileSearchQuery.value = ''
    fileSearchResults.value = null
  }

  return {
    blueprints, loading, currentBlueprint, currentFile,
    editContent, saving,
    createDialogVisible, deriveDialogVisible, deriveBlueprintId,
    viewMode,
    loadBlueprints, selectBlueprint, backToList,
    selectFile, saveCurrentFile, addFile, deleteFile,
    createNewBlueprint, deleteBlueprint,
    openDeriveDialog, derive,
    pendingChangesSummary, currentPendingChanges, pendingLoading,
    loadPendingChangesSummary, loadBlueprintPendingChanges,
    acceptChange, rejectChange, acceptAllChanges,
    startPendingPolling, stopPendingPolling,
    // Version history
    versionDrawerOpen, versionFilePath, versionList, versionTotal, versionLoading,
    openVersionDrawer, closeVersionDrawer, fetchMoreVersions, restoreVersion,
    // File search
    fileSearchQuery, fileSearchResults, fileSearchLoading,
    searchBlueprintFiles, clearFileSearch,
  }
})

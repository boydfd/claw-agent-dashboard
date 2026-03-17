import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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

  async function createNewBlueprint(name, description) {
    const bp = await apiCreate({ name, description })
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

  return {
    blueprints, loading, currentBlueprint, currentFile,
    editContent, saving,
    createDialogVisible, deriveDialogVisible, deriveBlueprintId,
    viewMode,
    loadBlueprints, selectBlueprint, backToList,
    selectFile, saveCurrentFile, addFile, deleteFile,
    createNewBlueprint, deleteBlueprint,
    openDeriveDialog, derive,
  }
})

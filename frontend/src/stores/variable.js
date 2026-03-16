import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchVariables,
  createVariable as apiCreate,
  updateVariable as apiUpdate,
  deleteVariable as apiDelete,
  batchApplyTemplates,
} from '../api'

export const useVariableStore = defineStore('variable', () => {
  const variables = ref([])
  const loading = ref(false)
  const scopeFilter = ref('all') // 'all' | 'global' | 'agent'
  const searchQuery = ref('')
  const dialogVisible = ref(false)
  const editingVariable = ref(null) // null = create mode, object = edit mode
  const impactDialogVisible = ref(false)
  const impactData = ref(null) // { variable, affected_templates, mode: 'update'|'delete' }

  const filteredVariables = computed(() => {
    let list = variables.value
    if (scopeFilter.value === 'global') {
      list = list.filter(v => v.scope === 'global')
    } else if (scopeFilter.value === 'agent') {
      list = list.filter(v => v.scope === 'agent')
    }
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      list = list.filter(v =>
        v.name.toLowerCase().includes(q) ||
        (v.description || '').toLowerCase().includes(q)
      )
    }
    return list
  })

  async function loadVariables() {
    loading.value = true
    try {
      variables.value = await fetchVariables()
    } finally {
      loading.value = false
    }
  }

  function openCreateDialog() {
    editingVariable.value = null
    dialogVisible.value = true
  }

  function openEditDialog(variable) {
    editingVariable.value = { ...variable }
    dialogVisible.value = true
  }

  function closeDialog() {
    dialogVisible.value = false
    editingVariable.value = null
  }

  async function saveVariable(data) {
    if (editingVariable.value) {
      const result = await apiUpdate(editingVariable.value.id, data)
      if (result.affected_templates && result.affected_templates.length > 0) {
        impactData.value = {
          variable: result.variable,
          affected_templates: result.affected_templates,
          mode: 'update',
        }
        impactDialogVisible.value = true
      }
      await loadVariables()
      return result
    } else {
      const result = await apiCreate(data)
      await loadVariables()
      return result
    }
  }

  async function removeVariable(variableId) {
    const result = await apiDelete(variableId, false)
    if (result.needs_confirmation) {
      impactData.value = {
        variable: variables.value.find(v => v.id === variableId),
        affected_templates: result.affected_templates,
        mode: 'delete',
      }
      impactDialogVisible.value = true
      return result
    }
    await loadVariables()
    return result
  }

  async function confirmDelete(variableId) {
    await apiDelete(variableId, true)
    impactDialogVisible.value = false
    impactData.value = null
    await loadVariables()
  }

  async function applyAffectedTemplates() {
    if (!impactData.value) return
    const ids = impactData.value.affected_templates.map(t => t.id)
    const result = await batchApplyTemplates(ids)
    impactDialogVisible.value = false
    impactData.value = null
    return result
  }

  function closeImpactDialog() {
    impactDialogVisible.value = false
    impactData.value = null
  }

  return {
    variables, loading, scopeFilter, searchQuery,
    dialogVisible, editingVariable,
    impactDialogVisible, impactData,
    filteredVariables,
    loadVariables, openCreateDialog, openEditDialog, closeDialog,
    saveVariable, removeVariable, confirmDelete,
    applyAffectedTemplates, closeImpactDialog,
  }
})

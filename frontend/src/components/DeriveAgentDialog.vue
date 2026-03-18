<template>
  <el-dialog
    :model-value="store.deriveDialogVisible"
    :title="t('management.deriveTitle', { name: blueprintName })"
    width="520px"
    @close="handleClose"
  >
    <p class="derive-subtitle">{{ t('management.deriveSubtitle') }}</p>

    <el-form :model="form" label-position="top">
      <!-- Agent Name -->
      <el-form-item :label="t('management.agentName')">
        <el-input v-model="form.agentName" placeholder="my-agent" />
        <div class="field-hint" v-if="form.agentName">
          {{ t('management.agentNameHint', { name: form.agentName }) }}
        </div>
      </el-form-item>

      <!-- Variables -->
      <el-form-item
        v-if="referencedVariables.length > 0"
        :label="t('management.variablesSection')"
      >
        <div class="variables-list">
          <div
            v-for="varName in referencedVariables"
            :key="varName"
            class="variable-row"
          >
            <div class="variable-header">
              <span class="variable-name">{{ '!{' + varName + '}' }}</span>
              <el-tag
                v-if="isOverridden(varName)"
                size="small"
                type="primary"
              >{{ t('management.overridden') }}</el-tag>
              <el-tag
                v-else
                size="small"
                type="info"
              >{{ t('management.inherited') }}</el-tag>
            </div>
            <el-input
              :model-value="getVariableValue(varName)"
              @update:model-value="(val) => setVariable(varName, val)"
              :placeholder="variableDefaults[varName] || ''"
              style="font-family: monospace"
            />
            <div v-if="isOverridden(varName) && variableDefaults[varName]" class="field-hint">
              {{ t('management.blueprintDefault', { value: variableDefaults[varName] }) }}
            </div>
          </div>
        </div>
      </el-form-item>

      <!-- OpenClaw Integration -->
      <el-form-item :label="t('management.openclawIntegration')">
        <div class="switch-row">
          <el-switch v-model="form.createOpenclaw" />
          <span class="switch-hint">{{ t('management.registerOpenclaw') }}</span>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">{{ t('common.cancel') }}</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="!form.agentName"
        @click="handleSubmit"
      >
        {{ t('management.createAgent') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useBlueprintStore } from '../stores/blueprint'
import { fetchBlueprint, fetchVariablesByScope } from '../api'

const { t } = useI18n()
const store = useBlueprintStore()
const submitting = ref(false)

const blueprintName = ref('')
const referencedVariables = ref([])
const variableDefaults = ref({})
const variableOverrides = ref({})

const form = reactive({
  agentName: '',
  createOpenclaw: true,
})

function isOverridden(varName) {
  return varName in variableOverrides.value
}

function getVariableValue(varName) {
  return variableOverrides.value[varName] ?? variableDefaults.value[varName] ?? ''
}

function setVariable(varName, value) {
  if (value === variableDefaults.value[varName]) {
    delete variableOverrides.value[varName]
  } else {
    variableOverrides.value[varName] = value
  }
}

function resetForm() {
  form.agentName = ''
  form.createOpenclaw = true
  blueprintName.value = ''
  referencedVariables.value = []
  variableDefaults.value = {}
  variableOverrides.value = {}
}

watch(() => store.deriveDialogVisible, async (visible) => {
  if (!visible || !store.deriveBlueprintId) return
  resetForm()

  try {
    const bp = await fetchBlueprint(store.deriveBlueprintId)
    blueprintName.value = bp.name || ''
    const rawVars = bp.referenced_variables || []
    referencedVariables.value = rawVars.map(v => v.name)

    // Fetch variable defaults from the blueprint's virtual agent
    if (bp.agent_id && referencedVariables.value.length > 0) {
      try {
        const vars = await fetchVariablesByScope('blueprint', bp.agent_id)
        const defaults = {}
        for (const v of vars) {
          if (referencedVariables.value.includes(v.name)) {
            defaults[v.name] = v.value ?? ''
          }
        }
        variableDefaults.value = defaults
      } catch {
        // Variables endpoint may not return results for virtual agent; use empty defaults
      }
    }
  } catch {
    ElMessage.error(t('management.deriveFailed'))
  }
})

function handleClose() {
  store.deriveDialogVisible = false
  store.deriveBlueprintId = null
}

async function handleSubmit() {
  submitting.value = true
  try {
    await store.derive(
      store.deriveBlueprintId,
      form.agentName,
      variableOverrides.value,
      form.createOpenclaw,
    )
    ElMessage.success(t('management.deriveSuccess'))
    handleClose()
    await store.loadBlueprints()
  } catch {
    ElMessage.error(t('management.deriveFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.derive-subtitle {
  color: #909399;
  font-size: 13px;
  margin: 0 0 16px 0;
}
.variables-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.variable-row {
  width: 100%;
}
.variable-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.variable-name {
  font-family: monospace;
  font-weight: bold;
  font-size: 13px;
  color: #e6a23c;
}
.field-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.switch-hint {
  font-size: 12px;
  color: #909399;
}
</style>

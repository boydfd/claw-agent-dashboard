<template>
  <el-dialog
    :model-value="store.dialogVisible"
    :title="store.editingVariable ? t('management.editVariable') : t('management.createVariable')"
    width="480px"
    @close="store.closeDialog()"
  >
    <el-form :model="form" label-position="top">
      <el-form-item :label="t('management.varName')">
        <el-input
          v-model="form.name"
          placeholder="API_KEY"
          :disabled="!!store.editingVariable"
          style="font-family: monospace"
        />
      </el-form-item>
      <el-form-item :label="t('management.varType')">
        <el-radio-group v-model="form.type">
          <el-radio value="text">{{ t('management.typeText') }}</el-radio>
          <el-radio value="secret">{{ t('management.typeSecret') }}</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item :label="t('management.varScope')">
        <el-radio-group v-model="form.scope" @change="onScopeChange">
          <el-radio value="global">{{ t('management.scopeGlobal') }}</el-radio>
          <el-radio value="agent">{{ t('management.filterAgent') }}</el-radio>
        </el-radio-group>
        <el-select
          v-if="form.scope === 'agent'"
          v-model="form.agent_id"
          :placeholder="t('management.selectAgent')"
          style="margin-left: 12px; width: 200px"
        >
          <el-option
            v-for="agent in agentStore.agents"
            :key="agent.id"
            :label="agent.display_name"
            :value="agent.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('management.varValue')">
        <el-input
          v-model="form.value"
          :type="form.type === 'secret' ? 'password' : 'text'"
          :placeholder="store.editingVariable && form.type === 'secret' ? t('management.secretKeepCurrent') : ''"
          style="font-family: monospace"
          show-password
        />
      </el-form-item>
      <el-form-item :label="t('management.varDescription')">
        <el-input v-model="form.description" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="store.closeDialog()">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" @click="handleSave" :loading="saving">
        {{ t('common.save') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useVariableStore } from '../stores/variable'
import { useAgentStore } from '../stores/agent'

const { t } = useI18n()
const store = useVariableStore()
const agentStore = useAgentStore()
const saving = ref(false)

const form = ref({
  name: '',
  value: '',
  type: 'text',
  scope: 'global',
  agent_id: null,
  description: '',
})

watch(() => store.dialogVisible, (visible) => {
  if (visible) {
    if (store.editingVariable) {
      form.value = {
        name: store.editingVariable.name,
        value: '',
        type: store.editingVariable.type,
        scope: store.editingVariable.scope,
        agent_id: store.editingVariable.agent_id,
        description: store.editingVariable.description || '',
      }
    } else {
      form.value = { name: '', value: '', type: 'text', scope: 'global', agent_id: null, description: '' }
    }
  }
})

function onScopeChange(scope) {
  if (scope === 'global') {
    form.value.agent_id = null
  }
}

async function handleSave() {
  saving.value = true
  try {
    const data = { ...form.value }
    const isEdit = !!store.editingVariable
    if (isEdit && data.type === 'secret' && !data.value) {
      data.value = '******'
    }
    await store.saveVariable(data)
    store.closeDialog()
    ElMessage.success(t(isEdit ? 'management.variableUpdated' : 'management.variableCreated'))
  } catch {
    ElMessage.error(t(store.editingVariable ? 'management.updateFailed' : 'management.createFailed'))
  } finally {
    saving.value = false
  }
}
</script>

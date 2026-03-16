<template>
  <div class="variables-panel">
    <div class="variables-toolbar">
      <el-button type="primary" @click="store.openCreateDialog()">
        {{ t('management.newVariable') }}
      </el-button>
      <div class="scope-filter">
        <el-button-group>
          <el-button
            v-for="f in ['all', 'global', 'agent']"
            :key="f"
            :type="store.scopeFilter === f ? 'primary' : 'default'"
            size="small"
            @click="store.scopeFilter = f"
          >
            {{ t(`management.filter${f.charAt(0).toUpperCase() + f.slice(1)}`) }}
          </el-button>
        </el-button-group>
      </div>
      <el-input
        v-model="store.searchQuery"
        :placeholder="t('management.searchPlaceholder')"
        class="search-input"
        clearable
        size="small"
      />
    </div>
    <el-table
      :data="store.filteredVariables"
      v-loading="store.loading"
      stripe
      class="variables-table"
    >
      <el-table-column prop="name" :label="t('management.colName')" width="180">
        <template #default="{ row }">
          <code class="var-name">{{ row.name }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="type" :label="t('management.colType')" width="100">
        <template #default="{ row }">
          <el-tag :type="row.type === 'secret' ? 'warning' : 'info'" size="small">
            {{ t(`management.type${row.type.charAt(0).toUpperCase() + row.type.slice(1)}`) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="value" :label="t('management.colValue')" width="200">
        <template #default="{ row }">
          <code class="var-value">{{ row.value }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="scope" :label="t('management.colScope')" width="160">
        <template #default="{ row }">
          <el-tag :type="row.scope === 'global' ? 'success' : 'primary'" size="small">
            {{ row.scope === 'global' ? t('management.scopeGlobal') : agentDisplayName(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" :label="t('management.colDescription')" />
      <el-table-column :label="t('management.colActions')" width="100" align="right">
        <template #default="{ row }">
          <el-button text size="small" @click="store.openEditDialog(row)">Edit</el-button>
          <el-button text size="small" type="danger" @click="handleDelete(row)">Del</el-button>
        </template>
      </el-table-column>
    </el-table>
    <VariableDialog />
    <ImpactTreeDialog />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useVariableStore } from '../stores/variable'
import { useAgentStore } from '../stores/agent'
import VariableDialog from './VariableDialog.vue'
import ImpactTreeDialog from './ImpactTreeDialog.vue'

const { t } = useI18n()
const store = useVariableStore()
const agentStore = useAgentStore()

onMounted(async () => {
  await Promise.all([
    store.loadVariables(),
    agentStore.loadAgents(),
  ])
})

function agentDisplayName(row) {
  if (!row.agent_id) return ''
  const agent = agentStore.agents.find(a => a.id === row.agent_id)
  return agent ? agent.display_name : `Agent #${row.agent_id}`
}

async function handleDelete(row) {
  try {
    await store.removeVariable(row.id)
  } catch {
    ElMessage.error(t('management.deleteFailed'))
  }
}
</script>

<style scoped>
.variables-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.search-input {
  margin-left: auto;
  width: 200px;
}
.var-name {
  font-family: monospace;
  color: var(--primary-color, #e94560);
}
.var-value {
  font-family: monospace;
  color: #aaa;
}
.variables-table {
  width: 100%;
}
</style>

<template>
  <el-dialog
    :model-value="store.impactDialogVisible"
    :title="t('management.impactTitle')"
    width="560px"
    @close="store.closeImpactDialog()"
  >
    <template v-if="store.impactData">
      <div class="impact-header">
        <span class="impact-message">
          {{ impactMessage }}
        </span>
      </div>
      <div class="impact-tree">
        <div v-for="(agentGroup, agentName) in groupedTemplates" :key="agentName" class="tree-agent">
          <div class="tree-agent-header" @click="toggleAgent(agentName)">
            <span class="tree-arrow">{{ expandedAgents.has(agentName) ? '▼' : '▶' }}</span>
            <span class="tree-agent-name">{{ agentName }}</span>
            <span class="tree-count">{{ t('management.files', { n: agentGroup.length }) }}</span>
          </div>
          <div v-if="expandedAgents.has(agentName)" class="tree-files">
            <div
              v-for="(tmpl, idx) in agentGroup"
              :key="tmpl.id"
              class="tree-file"
            >
              <span class="tree-connector">{{ idx === agentGroup.length - 1 ? '└─' : '├─' }}</span>
              <span class="tree-file-name">{{ tmpl.file_path }}</span>
              <span class="tree-refs">{{ t('management.refs', { n: tmpl.ref_count }) }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="impact-summary">
        {{ t('management.impactSummary', {
          agents: Object.keys(groupedTemplates).length,
          files: store.impactData.affected_templates.length,
          refs: totalRefs,
        }) }}
      </div>
    </template>
    <template #footer>
      <el-button @click="store.closeImpactDialog()">
        {{ t(isDelete ? 'common.cancel' : 'management.impactSkip') }}
      </el-button>
      <el-button
        :type="isDelete ? 'danger' : 'warning'"
        @click="handleConfirm"
        :loading="applying"
      >
        {{ t(isDelete ? 'management.impactConfirmDelete' : 'management.impactApply') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useVariableStore } from '../stores/variable'

const { t } = useI18n()
const store = useVariableStore()
const applying = ref(false)
const expandedAgents = ref(new Set())

const isDelete = computed(() => store.impactData?.mode === 'delete')

const impactMessage = computed(() => {
  const varName = store.impactData?.variable?.name || ''
  const displayName = '${' + varName + '}'
  const key = isDelete.value ? 'management.impactDeleteMessage' : 'management.impactMessage'
  return t(key, { name: displayName })
})

const groupedTemplates = computed(() => {
  if (!store.impactData?.affected_templates) return {}
  const groups = {}
  for (const tmpl of store.impactData.affected_templates) {
    const name = tmpl.agent_name
    if (!groups[name]) groups[name] = []
    groups[name].push(tmpl)
  }
  return groups
})

// Expand all agents by default when impact data changes
watch(() => store.impactData, (data) => {
  if (data?.affected_templates) {
    const names = [...new Set(data.affected_templates.map(t => t.agent_name))]
    expandedAgents.value = new Set(names)
  }
})

const totalRefs = computed(() => {
  if (!store.impactData?.affected_templates) return 0
  return store.impactData.affected_templates.reduce((sum, t) => sum + t.ref_count, 0)
})

function toggleAgent(name) {
  const next = new Set(expandedAgents.value)
  if (next.has(name)) {
    next.delete(name)
  } else {
    next.add(name)
  }
  expandedAgents.value = next
}

async function handleConfirm() {
  applying.value = true
  try {
    if (isDelete.value) {
      await store.confirmDelete(store.impactData.variable.id)
      ElMessage.success(t('management.variableDeleted'))
    } else {
      await store.applyAffectedTemplates()
      ElMessage.success(t('management.applySuccess'))
    }
  } catch {
    ElMessage.error(t(isDelete.value ? 'management.deleteFailed' : 'management.applyFailed'))
  } finally {
    applying.value = false
  }
}
</script>

<style scoped>
.impact-header {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}
.impact-message {
  color: #e6a23c;
  font-weight: bold;
}
.impact-tree {
  border: 1px solid var(--border-color, #333);
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
  font-family: monospace;
  font-size: 13px;
  line-height: 2;
}
.tree-agent-header {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}
.tree-arrow {
  color: var(--primary-color, #e94560);
  width: 14px;
}
.tree-agent-name {
  color: #67c23a;
  font-weight: bold;
}
.tree-count {
  color: #666;
  font-size: 11px;
  margin-left: 6px;
}
.tree-files {
  margin-left: 24px;
}
.tree-file {
  display: flex;
  align-items: center;
  gap: 4px;
}
.tree-connector {
  color: #555;
}
.tree-file-name {
  color: #ddd;
}
.tree-refs {
  color: var(--primary-color, #e94560);
  font-size: 11px;
  margin-left: 6px;
}
.impact-summary {
  background: #2a1a0f;
  border: 1px solid #5a3a1a;
  border-radius: 6px;
  padding: 10px 14px;
  color: #e6a23c;
  font-size: 12px;
}
</style>

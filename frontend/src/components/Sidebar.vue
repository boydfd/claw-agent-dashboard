<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <span>📦 {{ t('sidebar.agents') }}</span>
    </div>

    <el-scrollbar>
      <!-- ===== Global Skills Section ===== -->
      <div v-if="store.globalSkillSources.length > 0" class="global-skills-section">
        <div class="section-header" @click="globalSkillsExpanded = !globalSkillsExpanded">
          <el-icon>
            <ArrowRight v-if="!globalSkillsExpanded" />
            <ArrowDown v-else />
          </el-icon>
          <span>🌐 {{ t('sidebar.globalSkills') }}</span>
        </div>

        <div v-if="globalSkillsExpanded" class="global-skills-content">
          <div v-for="src in store.globalSkillSources" :key="src.source" class="source-group">
            <div class="source-header" @click="toggleSource(src.source)">
              <el-icon>
                <ArrowRight v-if="!expandedSources[src.source]" />
                <ArrowDown v-else />
              </el-icon>
              <el-icon><Folder /></el-icon>
              <span>{{ src.name }}</span>
            </div>

            <div v-if="expandedSources[src.source]" class="source-skills">
              <div
                v-for="skill in (store.globalSkills[src.source] || [])"
                :key="skill.name"
                class="skill-group"
              >
                <div class="skill-header" @click="toggleGlobalSkill(src.source, skill.name)">
                  <el-icon>
                    <ArrowRight v-if="!expandedGlobalSkills[src.source + '/' + skill.name]" />
                    <ArrowDown v-else />
                  </el-icon>
                  <el-icon><Files /></el-icon>
                  <span class="skill-name">{{ skill.display_name }}</span>
                </div>

                <div v-if="expandedGlobalSkills[src.source + '/' + skill.name]" class="skill-files">
                  <FileTree
                    :files="store.globalSkillFilesMap[src.source + '/' + skill.name] || []"
                    :current-path="store.currentFile?.path"
                    @select="store.selectGlobalFile(src.source, $event)"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== Agent List ===== -->
      <div v-if="store.loading && store.agents.length === 0" class="loading-tip">
        <el-icon class="is-loading"><Loading /></el-icon> {{ t('sidebar.loading') }}
      </div>

      <div v-for="agent in store.agents" :key="agent.name" class="agent-group">
        <!-- Agent header -->
        <div
          class="agent-header"
          :class="{ active: store.currentAgent?.name === agent.name }"
          @click="selectAgent(agent)"
        >
          <span class="agent-status-dot" :class="getAgentDotClass(agent.name)"></span>
          <el-icon><FolderOpened v-if="store.currentAgent?.name === agent.name" /><Folder v-else /></el-icon>
          <span class="agent-name">{{ agent.display_name }}</span>
          <span class="agent-dirname">{{ agent.name }}</span>
        </div>

        <!-- Agent files + skills + memory + other files (when expanded) -->
        <div v-if="store.currentAgent?.name === agent.name" class="agent-content">
          <!-- Blueprint derivation badge -->
          <span v-if="store.derivationStatus?.is_derived" class="derived-badge">
            🔗 {{ t('management.derivedFrom', { name: store.derivationStatus.blueprint_name }) }}
          </span>

          <!-- Core files -->
          <div class="section-label">{{ t('sidebar.coreFiles') }}</div>
          <div
            v-for="file in store.agentFiles"
            :key="file.path"
            class="file-item"
            :class="{ active: store.currentFile?.path === file.path && !store.currentFile?._globalSource }"
          >
            <el-checkbox
              class="file-checkbox"
              :model-value="store.isFileSelected(agent.name, file.path)"
              @change="store.toggleFileSelection(agent.name, file.path)"
              @click.stop
              size="small"
            />
            <div class="file-item-content" @click="store.selectFile(file.path)">
              <el-icon><Document /></el-icon>
              <span>{{ file.name }}</span>
              <span v-if="store.isFileSynced(file.path) === true" class="sync-icon synced" title="Synced">🔗</span>
              <span v-else-if="store.isFileSynced(file.path) === false" class="sync-icon overridden" title="Overridden">✏️</span>
              <el-tag v-if="file.has_translation" size="small" type="success" class="trans-tag">{{ t('sidebar.translated') }}</el-tag>
            </div>
          </div>

          <!-- Other files -->
          <div v-if="store.agentOtherFiles.length > 0">
            <div class="section-label clickable" @click="otherFilesExpanded = !otherFilesExpanded">
              <el-icon style="font-size: 10px; margin-right: 2px">
                <ArrowRight v-if="!otherFilesExpanded" />
                <ArrowDown v-else />
              </el-icon>
              {{ t('sidebar.otherFiles') }}
            </div>
            <div v-if="otherFilesExpanded" class="other-files-section">
              <FileTree
                :files="store.agentOtherFiles"
                :current-path="store.currentFile?.path"
                @select="store.selectFile($event)"
              />
            </div>
          </div>

          <!-- Skills -->
          <div v-if="store.agentSkills.length > 0" class="section-label">{{ t('sidebar.skills') }}</div>
          <div v-for="skill in store.agentSkills" :key="skill.name" class="skill-group">
            <div class="skill-header" @click="toggleSkill(skill.name)">
              <el-icon>
                <ArrowRight v-if="!expandedSkills[skill.name]" />
                <ArrowDown v-else />
              </el-icon>
              <el-icon><Files /></el-icon>
              <span class="skill-name">{{ skill.display_name }}</span>
            </div>

            <!-- Skill files -->
            <div v-if="expandedSkills[skill.name]" class="skill-files">
              <FileTree
                :files="store.skillFilesMap[skill.name] || []"
                :current-path="store.currentFile?.path"
                @select="store.selectFile($event)"
              />
            </div>
          </div>

          <!-- Memory -->
          <div v-if="store.agentMemory.length > 0">
            <div class="section-label clickable" @click="memoryExpanded = !memoryExpanded">
              <el-icon style="font-size: 10px; margin-right: 2px">
                <ArrowRight v-if="!memoryExpanded" />
                <ArrowDown v-else />
              </el-icon>
              {{ t('sidebar.memory') }}
            </div>
            <div v-if="memoryExpanded">
              <div
                v-for="file in store.agentMemory"
                :key="file.path"
                class="file-item"
                :class="{ active: store.currentFile?.path === file.path && !store.currentFile?._globalSource }"
              >
                <el-checkbox
                  class="file-checkbox"
                  :model-value="store.isFileSelected(agent.name, file.path)"
                  @change="store.toggleFileSelection(agent.name, file.path)"
                  @click.stop
                  size="small"
                />
                <div class="file-item-content" @click="store.selectFile(file.path)">
                  <el-icon><Document /></el-icon>
                  <span>{{ file.name }}</span>
                  <el-tag v-if="file.has_translation" size="small" type="success" class="trans-tag">{{ t('sidebar.translated') }}</el-tag>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!store.loading && store.agents.length === 0" class="empty-tip">
        {{ t('sidebar.noAgents') }}
      </div>
    </el-scrollbar>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  Folder, FolderOpened, Document, Files,
  ArrowRight, ArrowDown, Loading,
} from '@element-plus/icons-vue'
import { useAgentStore } from '../stores/agent'
import { useDashboardStore } from '../stores/dashboard'
import FileTree from './FileTree.vue'

const router = useRouter()
const { t } = useI18n()
const store = useAgentStore()
const dashboardStore = useDashboardStore()
const expandedSkills = reactive({})
const expandedSources = reactive({})
const expandedGlobalSkills = reactive({})
const globalSkillsExpanded = ref(false)
const memoryExpanded = ref(false)
const otherFilesExpanded = ref(false)

function selectAgent(agent) {
  // Navigate via router — short name without 'workspace-' prefix
  const shortName = agent.name.replace('workspace-', '')
  router.push(`/agents/${shortName}`)
}

function getAgentDotClass(agentName) {
  if (!dashboardStore.allAgentsStatus?.length) return 'dot-unknown'
  // Match workspace-xxx format to xxx
  const shortName = agentName.replace('workspace-', '')
  const agentStatus = dashboardStore.allAgentsStatus.find(a => a.agent_name === shortName)
  if (!agentStatus) return 'dot-unknown'
  const map = {
    working: 'dot-working',
    active: 'dot-active',
    idle: 'dot-idle',
    dormant: 'dot-dormant',
    error: 'dot-error',
    unknown: 'dot-unknown',
  }
  return map[agentStatus.status] || 'dot-unknown'
}

async function toggleSkill(skillName) {
  expandedSkills[skillName] = !expandedSkills[skillName]
  if (expandedSkills[skillName]) {
    await store.loadSkillFiles(skillName)
  }
}

async function toggleSource(source) {
  expandedSources[source] = !expandedSources[source]
  if (expandedSources[source]) {
    await store.loadGlobalSkills(source)
  }
}

async function toggleGlobalSkill(source, skillName) {
  const key = `${source}/${skillName}`
  expandedGlobalSkills[key] = !expandedGlobalSkills[key]
  if (expandedGlobalSkills[key]) {
    await store.loadGlobalSkillFiles(source, skillName)
  }
}
</script>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.sidebar-header {
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid #e4e7ed;
  color: #303133;
}
.loading-tip, .empty-tip {
  padding: 20px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

/* Global skills */
.global-skills-section {
  border-bottom: 1px solid #ebeef5;
}
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  transition: background 0.2s;
}
.section-header:hover {
  background: #f5f7fa;
}
.global-skills-content {
  padding-bottom: 4px;
}
.source-group {
  margin-left: 0;
}
.source-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px 6px 28px;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  transition: background 0.15s;
}
.source-header:hover {
  background: #f0f2f5;
}
.source-skills {
  padding-left: 12px;
}

/* Agent */
.agent-group {
  border-bottom: 1px solid #ebeef5;
}
.agent-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}
.agent-header:hover {
  background: #ecf5ff;
}
.agent-header.active {
  background: #e6f0ff;
  color: #409eff;
}
.agent-name {
  font-weight: 500;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.agent-dirname {
  font-size: 11px;
  color: #909399;
  display: none;
}
.agent-header:hover .agent-dirname {
  display: inline;
}
.agent-content {
  padding-bottom: 4px;
}
.section-label {
  padding: 6px 16px 2px 28px;
  font-size: 11px;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.section-label.clickable {
  cursor: pointer;
  display: flex;
  align-items: center;
}
.section-label.clickable:hover {
  color: #606266;
}
.file-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 16px 4px 32px;
  font-size: 13px;
  transition: background 0.15s;
}
.file-item:hover {
  background: #f0f2f5;
}
.file-item.active {
  background: #e6f0ff;
  color: #409eff;
}
.file-checkbox {
  flex-shrink: 0;
}
.file-item-content {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  flex: 1;
  min-width: 0;
  padding: 2px 0;
}
.file-item-content span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trans-tag {
  margin-left: auto;
  font-size: 10px !important;
  height: 18px !important;
  line-height: 16px !important;
  padding: 0 4px !important;
  flex-shrink: 0;
}
.skill-group {
  margin-left: 0;
}
.skill-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px 6px 28px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}
.skill-header:hover {
  background: #f0f2f5;
}
.skill-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.skill-files {
  padding-left: 20px;
}
.other-files-section {
  padding-left: 20px;
}

/* Agent status dots */
.agent-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-active {
  background: #67c23a;
  box-shadow: 0 0 4px #67c23a;
}
.dot-working {
  background: #e6a23c;
  box-shadow: 0 0 4px #e6a23c;
  animation: dot-pulse 1.5s ease-in-out infinite;
}
@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 4px #e6a23c; }
  50% { box-shadow: 0 0 8px #e6a23c; }
}
.dot-idle {
  background: #909399;
}
.dot-dormant {
  background: #c0c4cc;
}
.dot-error {
  background: #f56c6c;
  box-shadow: 0 0 4px #f56c6c;
}
.dot-unknown {
  background: #dcdfe6;
}

.derived-badge {
  display: block;
  font-size: 11px;
  color: var(--el-color-primary);
  padding: 4px 8px;
  margin-bottom: 4px;
}

.sync-icon {
  margin-left: 4px;
  font-size: 11px;
}

.sync-icon.synced {
  opacity: 0.5;
}

.sync-icon.overridden {
  color: var(--el-color-warning);
}
</style>

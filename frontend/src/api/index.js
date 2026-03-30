import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// Agents
export const fetchAgents = () => api.get('/agents').then(r => r.data)
export const fetchAgentFiles = (name) => api.get(`/agents/${name}/files`).then(r => r.data)
export const fetchAgentSkills = (name) => api.get(`/agents/${name}/skills`).then(r => r.data)
export const fetchSkillFiles = (name, skill) => api.get(`/agents/${name}/skill-files/${skill}`).then(r => r.data)
export const fetchFileContent = (name, path) => api.get(`/agents/${name}/file`, { params: { path } }).then(r => r.data)

// Memory files
export const fetchAgentMemory = (name) => api.get(`/agents/${name}/memory`).then(r => r.data)

// Other files (non-core, non-skill, non-memory)
export const fetchAgentOtherFiles = (name) => api.get(`/agents/${name}/other-files`).then(r => r.data)

// Save file (with version tracking)
export const saveFile = (name, path, content, commitMsg = null) => {
  const body = { content }
  if (commitMsg) body.commit_msg = commitMsg
  return api.put(`/agents/${name}/file`, body, { params: { path } }).then(r => r.data)
}

// Translate
export const translateFile = (agent, path) => api.post('/translate', { agent, path }).then(r => r.data)
export const fetchTranslation = (agent, path) => api.get(`/translate/${agent}`, { params: { path } }).then(r => r.data)
export const checkTranslation = (agent, path) => api.get(`/translate/${agent}/exists`, { params: { path } }).then(r => r.data)

// Batch translate (SSE streaming)
export const batchTranslate = (items) => {
  return fetch('/api/translate/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  })
}

// Global Skills
export const fetchGlobalSkillSources = () => api.get('/global-skills').then(r => r.data)
export const fetchGlobalSkills = (source) => api.get(`/global-skills/${source}/skills`).then(r => r.data)
export const fetchGlobalSkillFiles = (source, skillName) => api.get(`/global-skills/${source}/skill-files/${skillName}`).then(r => r.data)
export const fetchGlobalSkillFileContent = (source, path) => api.get(`/global-skills/${source}/file`, { params: { path } }).then(r => r.data)

// Status
export const fetchFullStatus = () => api.get('/status').then(r => r.data)
export const fetchSystemStatus = () => api.get('/status/system').then(r => r.data)
export const fetchGatewayStatus = () => api.get('/status/gateway').then(r => r.data)
export const fetchAgentDetail = (agentName) => api.get(`/status/agent/${agentName}`).then(r => r.data)
export const fetchRecentEvents = (agent = null, limit = 100) => {
  const params = { limit }
  if (agent) params.agent = agent
  return api.get('/status/events', { params }).then(r => r.data)
}
export const fetchSessionMessages = (agentName, sessionId, offset = 0, limit = 50) => {
  return api.get(`/status/session/${agentName}/${sessionId}/messages`, {
    params: { offset, limit },
  }).then(r => r.data)
}

// Models & New Session
export const fetchModels = () => api.get('/status/models').then(r => r.data)
export const createNewSession = (agent, sessionKey = null) =>
  api.post('/status/session/new', { agent, session_key: sessionKey }).then(r => r.data)

export const switchSessionModel = (agent, model, sessionKey) =>
  api.post('/status/session/model', { agent, model, session_key: sessionKey }).then(r => r.data)

export function sendSessionMessage(agent, sessionKey, message, mode, envelopeContext) {
  return api.post('/status/session/send', {
    agent,
    session_key: sessionKey,
    message,
    mode,
    envelope_context: envelopeContext,
  }).then(r => r.data)
}

// Security (read-only audit)
export const fetchSecurityAudit = () => api.get('/security/audit').then(r => r.data)

// Settings
export const fetchSettings = () => api.get('/settings').then(r => r.data)
export const updateSettings = (data) => api.put('/settings', data).then(r => r.data)

// Versions
export const fetchFileVersions = (agentName, filePath, limit = 20, offset = 0) =>
  api.get(`/versions/${agentName}/${filePath}`, { params: { limit, offset } }).then(r => r.data)
export const fetchVersionDetail = (versionId) =>
  api.get(`/versions/detail/${versionId}`).then(r => r.data)
export const restoreVersion = (agentName, filePath, versionId) =>
  api.post(`/versions/${agentName}/${filePath}/restore`, { version_id: versionId }).then(r => r.data)
export const fetchVersionDiff = (agentName, filePath, fromId, toId) =>
  api.get(`/versions/${agentName}/${filePath}/diff`, { params: { from_version_id: fromId, to_version_id: toId } }).then(r => r.data)

export default api

// Variables
export const fetchVariables = () => api.get('/variables').then(r => r.data)
export const fetchAgentVariables = (agentId) => api.get(`/variables/agent/${agentId}`).then(r => r.data)
export const fetchVariablesByScope = (scope, agentId) => api.get('/variables', { params: { scope, agent_id: agentId } }).then(r => r.data)
export const createVariable = (data) => api.post('/variables', data).then(r => r.data)
export const updateVariable = (id, data) => api.put(`/variables/${id}`, data).then(r => r.data)
export const deleteVariable = (id, confirm = false) => api.delete(`/variables/${id}`, { params: { confirm } }).then(r => r.data)
export const fetchVariableReferences = (id) => api.get(`/variables/${id}/references`).then(r => r.data)

// Templates
export const fetchAgentTemplates = (agentId) => api.get(`/templates/agent/${agentId}`).then(r => r.data)
export const lookupTemplate = (agentId, filePath) => api.get('/templates/lookup', { params: { agent_id: agentId, file_path: filePath } }).then(r => r.data)
export const fetchTemplate = (id) => api.get(`/templates/${id}`).then(r => r.data)
export const fetchRenderedTemplate = (id, agentId = null) => api.get(`/templates/${id}/rendered`, agentId ? { params: { agent_id: agentId } } : {}).then(r => r.data)
export const updateTemplate = (id, content, commitMsg = null) => {
  const body = { content }
  if (commitMsg) body.commit_msg = commitMsg
  return api.put(`/templates/${id}`, body).then(r => r.data)
}
export const applyTemplate = (id) => api.post(`/templates/${id}/apply`).then(r => r.data)
export const batchApplyTemplates = (templateIds) => api.post('/templates/batch-apply', { template_ids: templateIds }).then(r => r.data)

// Blueprints
export const fetchBlueprints = () => api.get('/blueprints').then(r => r.data)
export const createBlueprint = (data) => api.post('/blueprints', data).then(r => r.data)
export const fetchBlueprint = (id) => api.get(`/blueprints/${id}`).then(r => r.data)
export const updateBlueprint = (id, data) => api.put(`/blueprints/${id}`, data).then(r => r.data)
export const deleteBlueprint = (id, confirm = false) => api.delete(`/blueprints/${id}`, { params: { confirm } }).then(r => r.data)

// Blueprint files
// Encode each path segment for URL safety while preserving / separators
const encodeFilePath = (p) => p.split('/').map(encodeURIComponent).join('/')

export const fetchBlueprintFiles = (id) => api.get(`/blueprints/${id}/files`).then(r => r.data)
export const addBlueprintFile = (id, data) => api.post(`/blueprints/${id}/files`, data).then(r => r.data)
export const fetchBlueprintFile = (id, filePath) => api.get(`/blueprints/${id}/files/${encodeFilePath(filePath)}`).then(r => r.data)
export const updateBlueprintFile = (id, filePath, content) => api.put(`/blueprints/${id}/files/${encodeFilePath(filePath)}`, { content }).then(r => r.data)
export const deleteBlueprintFile = (id, filePath) => api.delete(`/blueprints/${id}/files/${encodeFilePath(filePath)}`).then(r => r.data)

// Blueprint variables and derivations
export const fetchBlueprintVariables = (id) => api.get(`/blueprints/${id}/variables`).then(r => r.data)
export const fetchBlueprintDerivations = (id) => api.get(`/blueprints/${id}/derivations`).then(r => r.data)
export const deriveAgent = (id, data) => api.post(`/blueprints/${id}/derive`, data).then(r => r.data)

// Agent derivation status
export const fetchDerivationStatus = (agentName) => api.get(`/agents/${agentName}/derivation-status`).then(r => r.data)
// Agent file detach/restore from blueprint
export const detachFromBlueprint = (agentName, path) => api.post(`/agents/${agentName}/file/detach`, null, { params: { path } }).then(r => r.data)
export const restoreToBlueprint = (agentName, path) => api.post(`/agents/${agentName}/file/restore-blueprint`, null, { params: { path } }).then(r => r.data)

// Blueprint pending changes (filesystem sync)
export const fetchPendingChangesSummary = () => api.get('/blueprints/pending-changes').then(r => r.data)
export const fetchBlueprintPendingChanges = (id) => api.get(`/blueprints/${id}/pending-changes`).then(r => r.data)
export const acceptPendingChange = (bpId, changeId) => api.post(`/blueprints/${bpId}/pending-changes/${changeId}/accept`).then(r => r.data)
export const rejectPendingChange = (bpId, changeId) => api.post(`/blueprints/${bpId}/pending-changes/${changeId}/reject`).then(r => r.data)
export const acceptAllPendingChanges = (bpId) => api.post(`/blueprints/${bpId}/pending-changes/accept-all`).then(r => r.data)

// Agent pending changes (disk file sync)
export const fetchAgentPendingChanges = (agentName) => api.get(`/agents/${agentName}/pending-changes`).then(r => r.data)
export const acceptAgentPendingChange = (agentName, changeId) => api.post(`/agents/${agentName}/pending-changes/${changeId}/accept`).then(r => r.data)
export const rejectAgentPendingChange = (agentName, changeId) => api.post(`/agents/${agentName}/pending-changes/${changeId}/reject`).then(r => r.data)
export const acceptAllAgentPendingChanges = (agentName) => api.post(`/agents/${agentName}/pending-changes/accept-all`).then(r => r.data)
export const rejectAllAgentPendingChanges = (agentName) => api.post(`/agents/${agentName}/pending-changes/reject-all`).then(r => r.data)

// Blueprint file versions
export const fetchBlueprintFileVersions = (bpId, filePath, limit = 20, offset = 0) => api.get(`/blueprints/${bpId}/files/${encodeFilePath(filePath)}/versions`, { params: { limit, offset } }).then(r => r.data)
export const fetchBlueprintFileVersion = (bpId, filePath, versionNum) => api.get(`/blueprints/${bpId}/files/${encodeFilePath(filePath)}/versions/${versionNum}`).then(r => r.data)
export const restoreBlueprintFileVersion = (bpId, filePath, versionNum) => api.post(`/blueprints/${bpId}/files/${encodeFilePath(filePath)}/restore/${versionNum}`).then(r => r.data)

// Search
export const fetchSearchStatus = () => api.get('/search/status').then(r => r.data)
export const searchFiles = (scope, name, query, caseSensitive = false, maxResults = 200) =>
  api.get('/search/files', { params: { scope, name, query, case_sensitive: caseSensitive, max_results: maxResults } }).then(r => r.data)
export const searchSessions = (agentName, query, maxResults = 50) =>
  api.get('/search/sessions', { params: { agent_name: agentName, query, max_results: maxResults } }).then(r => r.data)

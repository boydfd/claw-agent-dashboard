<template>
  <div class="security-view">
    <div class="security-header">
      <div class="security-title-block">
        <h1 class="security-title">{{ t('security.title') }}</h1>
        <p class="security-sub">{{ t('security.subtitle') }}</p>
      </div>
      <div class="security-actions">
        <el-popover
          placement="bottom-end"
          trigger="click"
          width="520"
          popper-class="notice-popper"
        >
          <template #reference>
            <el-badge :value="noticeCount" :hidden="noticeCount === 0" :max="99" class="notice-badge">
              <el-button size="small">
                {{ t('security.noticeCenter') }}
              </el-button>
            </el-badge>
          </template>
          <div class="notice-popover">
            <p class="notice-popover-title">
              {{ t('security.noticeCenter') }} ·
              {{ t('security.noticeWarningInfo', { w: warningNoticeCount, i: infoNoticeCount }) }}
            </p>
            <div v-if="report?.findings?.length" class="notice-list">
              <div v-for="(f, i) in report.findings" :key="`notice-${i}`" class="notice-item">
                <el-tag size="small" :type="f.severity === 'warning' ? 'warning' : 'info'">{{ f.severity }}</el-tag>
                <span class="notice-code">{{ f.code }}</span>
                <span class="notice-msg">{{ f.message }}</span>
              </div>
            </div>
            <p v-else class="muted">{{ t('security.noNotices') }}</p>
          </div>
        </el-popover>
        <el-button :loading="loading" @click="load">
          {{ t('security.refresh') }}
        </el-button>
        <el-button type="primary" :disabled="!report" @click="exportJson">
          {{ t('security.exportJson') }}
        </el-button>
      </div>
    </div>

    <el-skeleton v-if="loading && !report" :rows="8" animated />
    <el-alert
      v-else-if="error"
      type="error"
      :title="t('security.loadFailed')"
      :description="error"
      show-icon
      :closable="false"
    />

    <template v-else-if="report">
      <!-- Summary cards -->
      <section
        v-if="report.summary"
        class="security-section"
        :class="{ collapsed: !isSectionOpen('summary') }"
      >
        <h2 class="section-heading" @click="toggleSection('summary')">{{ t('security.sectionSummary') }}</h2>
        <el-row :gutter="12" class="summary-row">
          <el-col :span="6" :xs="12">
            <el-card shadow="never" class="summary-card">
              <div class="summary-value">{{ report.summary.agents_scanned }}</div>
              <div class="summary-label">{{ t('security.summaryAgents') }}</div>
            </el-card>
          </el-col>
          <el-col :span="6" :xs="12">
            <el-card shadow="never" class="summary-card">
              <div class="summary-value">
                {{ report.summary.findings_warning }} / {{ report.summary.findings_info }}
              </div>
              <div class="summary-label">{{ t('security.summaryFindings') }}</div>
            </el-card>
          </el-col>
          <el-col :span="6" :xs="12">
            <el-card shadow="never" class="summary-card">
              <div class="summary-value">
                {{ report.summary.content_hits_warning }} / {{ report.summary.content_hits_info }}
              </div>
              <div class="summary-label">{{ t('security.summaryContentHits') }}</div>
            </el-card>
          </el-col>
          <el-col :span="6" :xs="12">
            <el-card shadow="never" class="summary-card">
              <div class="summary-value">{{ report.summary.agents_missing_tools_md }}</div>
              <div class="summary-label">{{ t('security.summaryMissingTools') }}</div>
            </el-card>
          </el-col>
        </el-row>
      </section>

      <el-tabs v-model="activeSecurityTab" class="security-tabs">
        <el-tab-pane name="session">
          <template #label>
            <span class="tab-label-with-badge">
              <span>{{ t('security.tabSessionFindings') }}</span>
              <el-badge :value="sessionTabCount" :hidden="sessionTabCount === 0" :max="999" />
              <el-icon class="tab-help-icon" @click.stop="showSessionRuleHelp = true">
                <QuestionFilled />
              </el-icon>
            </span>
          </template>
          <section class="security-section" :class="{ collapsed: !isSectionOpen('sessionRisks') }">
            <h2 class="section-heading" @click="toggleSection('sessionRisks')">{{ t('security.sectionSessionRisks') }}</h2>
            <p class="muted">
              {{ t('security.sessionRiskHint') }}
              <template v-if="report.session_risks">
                · {{ t('security.sessionRiskScanned', { n: report.session_risks.scanned_files || 0 }) }}
              </template>
            </p>
            <div class="session-finding-controls">
              <el-input
                v-model="sessionRiskFilter"
                clearable
                size="small"
                class="table-filter session-search-input"
                :placeholder="t('security.filterSessionFindings')"
              />
              <el-switch
                v-model="showInfoSessionFindings"
                :active-text="t('security.showInfoFindings')"
                :inactive-text="t('security.hideInfoFindings')"
              />
              <el-popover placement="bottom-start" trigger="click" width="480">
                <template #reference>
                  <el-button size="small">{{ t('security.advancedFilters') }}</el-button>
                </template>
                <div class="advanced-filter-panel">
                  <el-select v-model="sessionFindingRiskLevel" clearable size="small" class="session-filter-select" :placeholder="t('security.filterByRiskLevel')">
                    <el-option value="warning" :label="t('security.riskWarning')" />
                    <el-option value="info" :label="t('security.riskInfo')" />
                  </el-select>
                  <el-select v-model="sessionFindingRule" clearable size="small" class="session-filter-select" :placeholder="t('security.filterByRule')">
                    <el-option v-for="r in sessionFindingRuleOptions" :key="r" :value="r" :label="r" />
                  </el-select>
                  <el-select v-model="sessionFindingAgent" clearable size="small" class="session-filter-select" :placeholder="t('security.filterByAgent')">
                    <el-option v-for="a in sessionFindingAgentOptions" :key="a" :value="a" :label="a" />
                  </el-select>
                  <el-select v-model="sessionFindingRole" clearable size="small" class="session-filter-select" :placeholder="t('security.filterByRole')">
                    <el-option v-for="r in sessionFindingRoleOptions" :key="r" :value="r" :label="r" />
                  </el-select>
                </div>
              </el-popover>
            </div>
            <el-table
              v-if="filteredSessionRisks.length"
              :data="pagedSessionRisks"
              stripe
              size="small"
              class="audit-table session-risk-table"
              :max-height="sessionRiskTableHeight"
            >
          <el-table-column :label="t('security.riskLevel')" width="88">
            <template #default="{ row }">
              <el-tag :type="row.severity === 'warning' ? 'warning' : 'info'" size="small">
                {{ row.severity }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="rule" :label="t('security.colRule')" width="180" show-overflow-tooltip />
          <el-table-column prop="agent_name" :label="t('security.colAgent')" width="130" show-overflow-tooltip />
          <el-table-column prop="session_file" :label="t('security.sessionFile')" width="160" show-overflow-tooltip />
          <el-table-column prop="role" :label="t('security.sessionRole')" width="78" />
          <el-table-column prop="risk_score" :label="t('security.sessionRiskScore')" width="78" align="right" sortable :sort-method="sortByRiskScore" />
          <el-table-column :label="t('security.sessionModelSignals')" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ (row.model_signals || []).join(', ') || '—' }}
            </template>
          </el-table-column>
          <el-table-column :label="t('security.sessionEvidence')" min-width="280">
            <template #default="{ row }">
              <div class="session-context" v-html="highlightRiskContext(row.context, row.matched_text)"></div>
            </template>
          </el-table-column>
            </el-table>
            <div v-if="filteredSessionRisks.length" class="session-risk-pagination">
              <el-pagination
                v-model:current-page="sessionRiskPage"
                v-model:page-size="sessionRiskPageSize"
                size="small"
                background
                layout="total, prev, pager, next, sizes"
                :total="filteredSessionRisks.length"
                :page-sizes="[10, 20, 30, 50]"
              />
            </div>
            <p v-else class="muted">{{ t('security.sessionFindingNone') }}</p>
          </section>
        </el-tab-pane>
        <el-tab-pane name="config">
          <template #label>
            <span class="tab-label-with-badge">
              <span>{{ t('security.tabConfigFindings') }}</span>
              <el-badge :value="configTabCount" :hidden="configTabCount === 0" :max="999" />
              <el-icon class="tab-help-icon" @click.stop="showConfigRuleHelp = true">
                <QuestionFilled />
              </el-icon>
            </span>
          </template>

      <section class="security-section" :class="{ collapsed: !isSectionOpen('architecture') }">
        <h2 class="section-heading" @click="toggleSection('architecture')">{{ t('security.sectionArchitecture') }}</h2>
        <p class="muted">{{ t('security.architectureHint') }}</p>
        <div class="risk-legend">
          <span class="legend-item"><i class="dot risk-high"></i>{{ t('security.riskHigh') }}</span>
          <span class="legend-item"><i class="dot risk-medium"></i>{{ t('security.riskMedium') }}</span>
          <span class="legend-item"><i class="dot risk-low"></i>{{ t('security.riskLow') }}</span>
        </div>
        <div class="layer-matrix">
          <div class="layer-card block-network" :class="`risk-${getArchitectureLayer('gatewayNetwork').risk}`">
            <div class="layer-head">
              <div class="layer-title">{{ getArchitectureLayer('gatewayNetwork').title }}</div>
              <el-tag size="small" :type="riskTagType(getArchitectureLayer('gatewayNetwork').risk)">
                {{ getArchitectureLayer('gatewayNetwork').riskLabel }}
              </el-tag>
            </div>
            <div class="layer-path"><code>{{ getArchitectureLayer('gatewayNetwork').path }}</code></div>
            <p v-if="getArchitectureLayer('gatewayNetwork').hits.length" class="layer-hits">
              {{ t('security.architectureHitCount', { n: getArchitectureLayer('gatewayNetwork').hits.length }) }}:
              {{ getArchitectureLayer('gatewayNetwork').hits.map(h => h.id).join(', ') }}
            </p>
            <p v-else class="layer-hits muted">{{ t('security.architectureNoHits') }}</p>
          </div>
          <div class="layer-card block-auth" :class="`risk-${getArchitectureLayer('gatewayAuth').risk}`">
            <div class="layer-head">
              <div class="layer-title">{{ getArchitectureLayer('gatewayAuth').title }}</div>
              <el-tag size="small" :type="riskTagType(getArchitectureLayer('gatewayAuth').risk)">
                {{ getArchitectureLayer('gatewayAuth').riskLabel }}
              </el-tag>
            </div>
            <div class="layer-path"><code>{{ getArchitectureLayer('gatewayAuth').path }}</code></div>
            <p v-if="getArchitectureLayer('gatewayAuth').hits.length" class="layer-hits">
              {{ t('security.architectureHitCount', { n: getArchitectureLayer('gatewayAuth').hits.length }) }}:
              {{ getArchitectureLayer('gatewayAuth').hits.map(h => h.id).join(', ') }}
            </p>
            <p v-else class="layer-hits muted">{{ t('security.architectureNoHits') }}</p>
          </div>
          <div class="layer-card block-registry" :class="`risk-${getArchitectureLayer('registry').risk}`">
            <div class="layer-head">
              <div class="layer-title">{{ getArchitectureLayer('registry').title }}</div>
              <el-tag size="small" :type="riskTagType(getArchitectureLayer('registry').risk)">
                {{ getArchitectureLayer('registry').riskLabel }}
              </el-tag>
            </div>
            <div class="layer-path"><code>{{ getArchitectureLayer('registry').path }}</code></div>
            <p v-if="getArchitectureLayer('registry').hits.length" class="layer-hits">
              {{ t('security.architectureHitCount', { n: getArchitectureLayer('registry').hits.length }) }}:
              {{ getArchitectureLayer('registry').hits.map(h => h.id).join(', ') }}
            </p>
            <p v-else class="layer-hits muted">{{ t('security.architectureNoHits') }}</p>
          </div>
          <div class="layer-card block-secrets" :class="`risk-${getArchitectureLayer('secrets').risk}`">
            <div class="layer-head">
              <div class="layer-title">{{ getArchitectureLayer('secrets').title }}</div>
              <el-tag size="small" :type="riskTagType(getArchitectureLayer('secrets').risk)">
                {{ getArchitectureLayer('secrets').riskLabel }}
              </el-tag>
            </div>
            <div class="layer-path"><code>{{ getArchitectureLayer('secrets').path }}</code></div>
            <p v-if="getArchitectureLayer('secrets').hits.length" class="layer-hits">
              {{ t('security.architectureHitCount', { n: getArchitectureLayer('secrets').hits.length }) }}:
              {{ getArchitectureLayer('secrets').hits.map(h => h.id).join(', ') }}
            </p>
            <p v-else class="layer-hits muted">{{ t('security.architectureNoHits') }}</p>
          </div>
          <div class="layer-card block-runtime" :class="`risk-${getArchitectureLayer('runtime').risk}`">
            <div class="layer-head">
              <div class="layer-title">{{ getArchitectureLayer('runtime').title }}</div>
              <el-tag size="small" :type="riskTagType(getArchitectureLayer('runtime').risk)">
                {{ getArchitectureLayer('runtime').riskLabel }}
              </el-tag>
            </div>
            <div class="layer-path"><code>{{ getArchitectureLayer('runtime').path }}</code></div>
            <p v-if="getArchitectureLayer('runtime').hits.length" class="layer-hits">
              {{ t('security.architectureHitCount', { n: getArchitectureLayer('runtime').hits.length }) }}:
              {{ getArchitectureLayer('runtime').hits.map(h => h.id).join(', ') }}
            </p>
            <p v-else class="layer-hits muted">{{ t('security.architectureNoHits') }}</p>
          </div>
        </div>
      </section>

      <section class="security-section" :class="{ collapsed: !isSectionOpen('dashboard') }">
        <h2 class="section-heading" @click="toggleSection('dashboard')">{{ t('security.sectionDashboard') }}</h2>
        <el-descriptions :column="1" border size="small" class="desc-block">
          <el-descriptions-item :label="t('security.corsAllowAll')">
            {{ report.dashboard?.cors_allow_all ? t('common.yes') : t('common.no') }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="report.dashboard?.allowed_origins_count != null"
            :label="t('security.corsOriginsCount')"
          >
            {{ report.dashboard.allowed_origins_count }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.gatewayUrl')">
            {{ report.dashboard?.gateway_url || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.gatewayToken')">
            {{ report.dashboard?.gateway_token_configured ? t('security.configured') : t('security.notConfigured') }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.agentsDir')">
            <code class="path-code">{{ report.dashboard?.agents_dir }}</code>
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.globalSkillsDir')">
            <code class="path-code">{{ report.dashboard?.global_skills_dir }}</code>
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.sharedSkillsDir')">
            <code class="path-code">{{ report.dashboard?.shared_skills_dir }}</code>
          </el-descriptions-item>
        </el-descriptions>
      </section>

      <section class="security-section" :class="{ collapsed: !isSectionOpen('openclaw') }">
        <h2 class="section-heading" @click="toggleSection('openclaw')">{{ t('security.sectionOpenclaw') }}</h2>
        <el-descriptions :column="1" border size="small" class="desc-block">
          <el-descriptions-item :label="t('security.openclawPath')">
            <code class="path-code">{{ report.dashboard?.openclaw_config?.path }}</code>
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.openclawExists')">
            {{ report.dashboard?.openclaw_config?.exists ? t('common.yes') : t('common.no') }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.openclawParsed')">
            {{ report.dashboard?.openclaw_config?.parsed ? t('common.yes') : t('common.no') }}
          </el-descriptions-item>
          <el-descriptions-item v-if="report.dashboard?.openclaw_config?.parse_error" :label="t('security.parseError')">
            {{ report.dashboard.openclaw_config.parse_error }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.openclawTopKeys')">
            {{ (report.dashboard?.openclaw_config?.top_level_keys || []).join(', ') || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.openclawAgentsList')">
            {{ report.dashboard?.openclaw_config?.agents_in_registry_count ?? '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.openclawBindings')">
            {{ report.dashboard?.openclaw_config?.bindings_count ?? '—' }}
          </el-descriptions-item>
          <template v-if="report.dashboard?.openclaw_config?.parsed">
            <el-descriptions-item :label="t('security.openclawGatewayBind')">
              {{ report.dashboard.openclaw_config.gateway_bind ?? '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('security.openclawAuthMode')">
              {{ report.dashboard.openclaw_config.gateway_auth_mode ?? '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('security.openclawTokenSet')">
              {{
                report.dashboard.openclaw_config.gateway_auth_token_configured == null
                  ? '—'
                  : report.dashboard.openclaw_config.gateway_auth_token_configured
                    ? t('common.yes')
                    : t('common.no')
              }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('security.openclawPasswordSet')">
              {{
                report.dashboard.openclaw_config.gateway_auth_password_configured == null
                  ? '—'
                  : report.dashboard.openclaw_config.gateway_auth_password_configured
                    ? t('common.yes')
                    : t('common.no')
              }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('security.openclawSecretRefCount')">
              {{ report.dashboard.openclaw_config.secrets?.secret_ref_count ?? 0 }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('security.openclawInlineSecretCount')">
              {{ report.dashboard.openclaw_config.secrets?.inline_secret_like_count ?? 0 }}
            </el-descriptions-item>
          </template>
        </el-descriptions>
        <p
          v-if="report.dashboard?.openclaw_config?.secrets?.secret_ref_paths?.length"
          class="muted"
        >
          {{ t('security.openclawSecretRefPaths') }}:
          {{ report.dashboard.openclaw_config.secrets.secret_ref_paths.join(', ') }}
        </p>
      </section>

      <section
        v-if="report.dashboard?.openclaw_config?.parsed"
        class="security-section"
        :class="{ collapsed: !isSectionOpen('openclawSecurity') }"
      >
        <h2 class="section-heading" @click="toggleSection('openclawSecurity')">{{ t('security.sectionOpenclawSecurity') }}</h2>
        <div class="section-inline-actions">
          <el-button
            size="small"
            :disabled="!report.dashboard?.openclaw_config?.raw_text"
            @click="showOpenclawInspect = true"
          >
            {{ t('security.inspectOpenclaw') }}
          </el-button>
        </div>
        <p class="muted">{{ t('security.openclawSecurityHint') }}</p>
        <el-table
          v-if="(report.dashboard.openclaw_config.security_recommendations || []).length"
          :data="report.dashboard.openclaw_config.security_recommendations"
          stripe
          size="small"
          class="audit-table"
        >
          <el-table-column :label="t('security.severity')" width="88">
            <template #default="{ row }">
              <el-tag :type="row.severity === 'warning' ? 'warning' : 'info'" size="small">
                {{ row.severity }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('security.openclawRecId')" width="200">
            <template #default="{ row }">
              <code class="rec-id">{{ row.id }}</code>
            </template>
          </el-table-column>
          <el-table-column :label="t('security.openclawRecTitle')" min-width="140">
            <template #default="{ row }">{{ openclawRecField(row.id, 'title') }}</template>
          </el-table-column>
          <el-table-column :label="t('security.openclawRecDetail')" min-width="220">
            <template #default="{ row }">{{ openclawRecField(row.id, 'detail') }}</template>
          </el-table-column>
          <el-table-column :label="t('security.openclawRecRemediation')" min-width="220">
            <template #default="{ row }">{{ openclawRecField(row.id, 'remediation') }}</template>
          </el-table-column>
        </el-table>
        <p v-else class="muted">{{ t('security.openclawNoRecs') }}</p>
      </section>

      <el-dialog
        v-model="showOpenclawInspect"
        :title="t('security.inspectOpenclawTitle')"
        width="min(960px, 92vw)"
        append-to-body
        destroy-on-close
      >
        <p v-if="report.dashboard?.openclaw_config?.raw_text_truncated" class="muted inspect-note">
          {{ t('security.inspectOpenclawTruncated') }}
        </p>
        <pre class="openclaw-raw">{{ report.dashboard?.openclaw_config?.raw_text || t('security.inspectOpenclawUnavailable') }}</pre>
      </el-dialog>

      <section class="security-section" :class="{ collapsed: !isSectionOpen('externalIntel') }">
        <h2 class="section-heading" @click="toggleSection('externalIntel')">{{ t('security.sectionExternal') }}</h2>
        <p class="muted">{{ t('security.externalIntelHint') }}</p>

        <div class="security-subsection">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 8px;">
            <div style="font-weight: 600; color: var(--el-text-color-primary)">{{ t('security.vtTitle') }}</div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <el-tag v-if="vtEnabled" size="small" type="info">
                {{ t('security.vtScanned') }}: {{ vtScannedFiles }}
              </el-tag>
              <el-tag
                v-if="vtEnabled"
                size="small"
                :type="vtMaliciousHits > 0 ? 'danger' : vtSuspiciousHits > 0 ? 'warning' : 'success'"
              >
                {{ t('security.vtMalicious') }}: {{ vtMaliciousHits }} / {{ t('security.vtSuspicious') }}: {{ vtSuspiciousHits }}
              </el-tag>
            </div>
          </div>

          <p v-if="!vtEnabled" class="muted">{{ t('security.vtDisabled') }}</p>

          <div v-else-if="vtHits.length" style="max-height: 320px; overflow: auto;">
            <el-table :data="vtHits" stripe size="small" class="audit-table">
              <el-table-column :label="t('security.colScope')" width="140">
                <template #default="{ row }">
                  {{ row.scope === 'global_skill' ? t('security.scopeGlobalSkill') : t('security.scopeAgent') }}
                </template>
              </el-table-column>
              <el-table-column :label="t('security.colAgent')" width="140">
                <template #default="{ row }">
                  {{ row.agent_name || '—' }}
                </template>
              </el-table-column>
              <el-table-column :label="t('security.colGlobalSource')" min-width="140">
                <template #default="{ row }">
                  {{ row.global_source || '—' }}
                </template>
              </el-table-column>
              <el-table-column :label="t('security.colPath')" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">
                  <code class="path-code">{{ row.path || '—' }}</code>
                </template>
              </el-table-column>
              <el-table-column label="SHA-256" min-width="190" show-overflow-tooltip>
                <template #default="{ row }">
                  <code class="path-code">{{ row.sha256 || '—' }}</code>
                </template>
              </el-table-column>
              <el-table-column :label="t('security.vtMalicious')" width="98" align="right">
                <template #default="{ row }">{{ row.malicious || 0 }}</template>
              </el-table-column>
              <el-table-column :label="t('security.vtSuspicious')" width="105" align="right">
                <template #default="{ row }">{{ row.suspicious || 0 }}</template>
              </el-table-column>
              <el-table-column :label="t('security.colLink')" width="120">
                <template #default="{ row }">
                  <a :href="row.link" target="_blank" rel="noopener noreferrer">
                    {{ t('security.linkVirustotal') }}
                  </a>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <p v-else class="muted">{{ t('security.vtNoHits') }}</p>
        </div>

        <div class="security-subsection">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 8px;">
            <div style="font-weight: 600; color: var(--el-text-color-primary)">{{ t('security.osvTitle') }}</div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <el-tag size="small" type="info">
                {{ t('security.osvChecked') }}: {{ osvCheckedPackages }}
              </el-tag>
              <el-tag size="small" :type="osvVulnerabilityCount > 0 ? 'danger' : 'success'">
                {{ t('security.osvVulnCount') }}: {{ osvVulnerabilityCount }}
              </el-tag>
            </div>
          </div>

          <div v-if="osvVulnerabilities.length" style="max-height: 320px; overflow: auto;">
            <el-table :data="osvVulnerabilities" stripe size="small" class="audit-table">
              <el-table-column :label="t('security.osvPkg')" min-width="160" prop="package">
                <template #default="{ row }">
                  <code class="path-code">{{ row.package || '—' }}</code>
                </template>
              </el-table-column>
              <el-table-column :label="t('security.osvVersion')" width="120" prop="version">
                <template #default="{ row }">{{ row.version || '—' }}</template>
              </el-table-column>
              <el-table-column :label="t('security.osvId')" min-width="170">
                <template #default="{ row }">
                  <code class="path-code">{{ row.id || '—' }}</code>
                </template>
              </el-table-column>
              <el-table-column :label="t('security.osvAliases')" min-width="200">
                <template #default="{ row }">
                  <span v-if="row.aliases?.length">{{ row.aliases.join(', ') }}</span>
                  <span v-else>—</span>
                </template>
              </el-table-column>
              <el-table-column :label="t('security.osvFixed')" width="140">
                <template #default="{ row }">{{ row.fixed_version || '—' }}</template>
              </el-table-column>
              <el-table-column :label="t('security.osvSummary')" min-width="260" show-overflow-tooltip>
                <template #default="{ row }">{{ row.summary || '—' }}</template>
              </el-table-column>
              <el-table-column :label="t('security.colLink')" width="110">
                <template #default="{ row }">
                  <a :href="row.link" target="_blank" rel="noopener noreferrer">
                    {{ t('security.linkOsv') }}
                  </a>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <p v-else class="muted">{{ t('security.osvNoVulns') }}</p>
        </div>
      </section>

      <section class="security-section" :class="{ collapsed: !isSectionOpen('content') }">
        <h2 class="section-heading" @click="toggleSection('content')">{{ t('security.sectionContentScan') }}</h2>
        <p class="muted">{{ t('security.contentScanHint') }}</p>
        <el-input
          v-model="signalFilter"
          clearable
          class="table-filter"
          :placeholder="t('security.filterSignals')"
        />
        <el-table
          v-if="filteredSignals.length"
          :data="filteredSignals"
          stripe
          size="small"
          class="audit-table"
        >
          <el-table-column :label="t('security.severity')" width="88">
            <template #default="{ row }">
              <el-tag :type="row.severity === 'warning' ? 'warning' : 'info'" size="small">
                {{ row.severity }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('security.colScope')" width="130">
            <template #default="{ row }">
              {{ row.scope === 'global_skill' ? t('security.scopeGlobalSkill') : t('security.scopeAgent') }}
            </template>
          </el-table-column>
          <el-table-column :label="t('security.colAgent')" min-width="120">
            <template #default="{ row }">
              {{ row.agent_name || '—' }}
            </template>
          </el-table-column>
          <el-table-column :label="t('security.colGlobalSource')" width="100">
            <template #default="{ row }">
              {{ row.global_source || '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="path" :label="t('security.colPath')" min-width="160" show-overflow-tooltip />
          <el-table-column prop="line" :label="t('security.colLine')" width="64" align="right" />
          <el-table-column :label="t('security.colRule')" width="120">
            <template #default="{ row }">{{ ruleLabel(row.rule) }}</template>
          </el-table-column>
          <el-table-column prop="preview" :label="t('security.colPreview')" min-width="200" show-overflow-tooltip />
        </el-table>
        <p
          v-else-if="report.content_signals?.length"
          class="muted"
        >
          {{ t('security.noFilterMatch') }}
        </p>
        <p v-else class="muted">{{ t('security.noSignals') }}</p>
      </section>

      <section class="security-section" :class="{ collapsed: !isSectionOpen('llm') }">
        <h2 class="section-heading" @click="toggleSection('llm')">{{ t('security.sectionLlm') }}</h2>
        <el-descriptions :column="1" border size="small" class="desc-block">
          <el-descriptions-item :label="t('security.llmDataDir')">
            <code class="path-code">{{ report.llm_settings?.data_dir }}</code>
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.defaultApiKey')">
            {{ report.llm_settings?.default_has_api_key ? t('security.configured') : t('security.notConfigured') }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('security.overrideKeys')">
            {{ (report.llm_settings?.override_purposes_with_api_key || []).join(', ') || '—' }}
          </el-descriptions-item>
        </el-descriptions>
      </section>

      <section class="security-section" :class="{ collapsed: !isSectionOpen('agents') }">
        <h2 class="section-heading" @click="toggleSection('agents')">{{ t('security.sectionAgents') }}</h2>
        <el-input
          v-model="agentFilter"
          clearable
          class="table-filter"
          :placeholder="t('security.filterAgents')"
        />
        <el-table :data="filteredAgents" stripe size="small" class="audit-table">
          <el-table-column prop="name" :label="t('security.colAgent')" min-width="140" />
          <el-table-column prop="blueprint_name" :label="t('security.colBlueprint')" min-width="120">
            <template #default="{ row }">{{ row.blueprint_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="local_skill_count" :label="t('security.colLocalSkills')" width="100" align="right" />
          <el-table-column prop="local_skill_file_total" :label="t('security.colSkillFiles')" width="100" align="right" />
          <el-table-column :label="t('security.colPolicyFiles')" min-width="200">
            <template #default="{ row }">
              <span v-for="(ok, key) in row.policy_files" :key="key" class="policy-tag" :class="{ on: ok }">
                {{ key.replace('.md', '') }}
              </span>
            </template>
          </el-table-column>
          <el-table-column type="expand">
            <template #default="{ row }">
              <el-table v-if="row.local_skills?.length" :data="row.local_skills" size="small" border>
                <el-table-column prop="name" :label="t('security.skillId')" />
                <el-table-column prop="display_name" :label="t('security.skillDisplayName')" />
                <el-table-column prop="file_count" :label="t('security.fileCount')" width="100" align="right" />
                <el-table-column :label="t('security.skillSignalWarning')" width="90" align="right">
                  <template #default="{ row: sk }">{{ localSkillAudit(row.name, sk.name).signal_warning }}</template>
                </el-table-column>
                <el-table-column :label="t('security.skillSignalInfo')" width="90" align="right">
                  <template #default="{ row: sk }">{{ localSkillAudit(row.name, sk.name).signal_info }}</template>
                </el-table-column>
                <el-table-column :label="t('security.skillVt')" width="120">
                  <template #default="{ row: sk }">
                    <template v-if="localSkillAudit(row.name, sk.name).vt">
                      {{ localSkillAudit(row.name, sk.name).vt.malicious }}/{{ localSkillAudit(row.name, sk.name).vt.suspicious }}
                    </template>
                    <template v-else>—</template>
                  </template>
                </el-table-column>
                <el-table-column :label="t('security.colLink')" width="120">
                  <template #default="{ row: sk }">
                    <a :href="localSkillAudit(row.name, sk.name).primary_link" target="_blank" rel="noopener noreferrer">
                      {{ linkLabel(localSkillAudit(row.name, sk.name).primary_link) }}
                    </a>
                  </template>
                </el-table-column>
              </el-table>
              <p v-else class="expand-empty">{{ t('security.noLocalSkills') }}</p>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section
        v-if="!report.global_skill_sources?.length"
        class="security-section"
        :class="{ collapsed: !isSectionOpen('globalSkills') }"
      >
        <h2 class="section-heading" @click="toggleSection('globalSkills')">{{ t('security.sectionGlobalSkills') }}</h2>
        <p class="muted">{{ t('security.noGlobalSources') }}</p>
      </section>
      <section
        v-for="src in report.global_skill_sources"
        :key="src.source"
        class="security-section"
        :class="{ collapsed: !isSectionOpen(`globalSkills:${src.source}`) }"
      >
        <h2 class="section-heading" @click="toggleSection(`globalSkills:${src.source}`)">
          {{ t('security.sectionGlobalSkills') }} — {{ src.label }} ({{ src.source }})
        </h2>
        <p class="muted"><code>{{ src.path }}</code> · {{ t('security.skillCount') }}: {{ src.skill_count }}</p>
        <el-table v-if="src.skills?.length" :data="src.skills" stripe size="small" class="audit-table">
          <el-table-column prop="name" :label="t('security.skillId')" />
          <el-table-column prop="display_name" :label="t('security.skillDisplayName')" />
          <el-table-column prop="file_count" :label="t('security.fileCount')" width="120" align="right" />
          <el-table-column :label="t('security.skillSignalWarning')" width="90" align="right">
            <template #default="{ row: sk }">{{ globalSkillAudit(src.source, sk.name).signal_warning }}</template>
          </el-table-column>
          <el-table-column :label="t('security.skillSignalInfo')" width="90" align="right">
            <template #default="{ row: sk }">{{ globalSkillAudit(src.source, sk.name).signal_info }}</template>
          </el-table-column>
          <el-table-column :label="t('security.skillVt')" width="120">
            <template #default="{ row: sk }">
              <template v-if="globalSkillAudit(src.source, sk.name).vt">
                {{ globalSkillAudit(src.source, sk.name).vt.malicious }}/{{ globalSkillAudit(src.source, sk.name).vt.suspicious }}
              </template>
              <template v-else>—</template>
            </template>
          </el-table-column>
          <el-table-column :label="t('security.colLink')" width="120">
            <template #default="{ row: sk }">
              <a :href="globalSkillAudit(src.source, sk.name).primary_link" target="_blank" rel="noopener noreferrer">
                {{ linkLabel(globalSkillAudit(src.source, sk.name).primary_link) }}
              </a>
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="muted">{{ t('security.noGlobalSkills') }}</p>
      </section>

      <section class="security-section" :class="{ collapsed: !isSectionOpen('variables') }">
        <h2 class="section-heading" @click="toggleSection('variables')">{{ t('security.sectionVariables') }}</h2>
        <p class="muted">
          {{ t('security.variableTotal') }}: {{ report.variables?.total }}
          <template v-if="report.variables?.by_type">
            · {{ Object.entries(report.variables.by_type).map(([k, v]) => `${k}: ${v}`).join(', ') }}
          </template>
        </p>
        <el-input
          v-model="varFilter"
          clearable
          class="table-filter"
          :placeholder="t('security.filterVariables')"
        />
        <el-table :data="filteredVariables" stripe size="small" class="audit-table">
          <el-table-column prop="id" label="ID" width="70" align="right" />
          <el-table-column prop="name" :label="t('security.varName')" min-width="120" />
          <el-table-column prop="type" :label="t('security.varType')" width="90" />
          <el-table-column prop="scope" :label="t('security.varScope')" width="100" />
          <el-table-column prop="agent_id" :label="t('security.varAgentId')" width="100" align="right">
            <template #default="{ row }">{{ row.agent_id ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="description" :label="t('security.varDescription')" min-width="160" show-overflow-tooltip />
        </el-table>
      </section>
        </el-tab-pane>
      </el-tabs>

      <el-dialog
        v-model="showSessionRuleHelp"
        :title="t('security.sessionRuleHelpTitle')"
        width="min(820px, 92vw)"
        append-to-body
        destroy-on-close
      >
        <el-table v-if="sessionRuleHelpRows.length" :data="sessionRuleHelpRows" size="small" border class="rule-help-table">
          <el-table-column prop="rule" :label="t('security.colRuleId')" width="260" show-overflow-tooltip />
          <el-table-column prop="risk" :label="t('security.colRiskLevel')" width="120" />
          <el-table-column prop="description" :label="t('security.colDescription')" min-width="360">
            <template #default="{ row }">
              {{ row.description || t('security.ruleDescUnknown') }}
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="muted">{{ t('security.noSessionRuleHelp') }}</p>
      </el-dialog>

      <el-dialog
        v-model="showConfigRuleHelp"
        :title="t('security.configRuleHelpTitle')"
        width="min(820px, 92vw)"
        append-to-body
        destroy-on-close
      >
        <el-table v-if="configRuleHelpRows.length" :data="configRuleHelpRows" size="small" border class="rule-help-table">
          <el-table-column prop="code" :label="t('security.colRuleId')" width="260" show-overflow-tooltip />
          <el-table-column prop="risk" :label="t('security.colRiskLevel')" width="120" />
          <el-table-column prop="message" :label="t('security.colDescription')" min-width="360">
            <template #default="{ row }">
              {{ row.message || '—' }}
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="muted">{{ t('security.noConfigRuleHelp') }}</p>
      </el-dialog>

      <p class="generated-at">{{ t('security.generatedAt') }}: {{ report.generated_at }}</p>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { fetchSecurityAudit } from '../api'

const { t } = useI18n()

const loading = ref(false)
const error = ref('')
const report = ref(null)
const activeSecurityTab = ref('config')
const sectionState = ref({
  summary: true,
  sessionRisks: true,
  architecture: true,
  externalIntel: true,
  content: true,
  dashboard: true,
  openclaw: true,
  openclawSecurity: true,
  llm: true,
  agents: true,
  globalSkills: true,
  variables: true,
})
const agentFilter = ref('')
const varFilter = ref('')
const signalFilter = ref('')
const sessionRiskFilter = ref('')
const showInfoSessionFindings = ref(false)
const sessionFindingRiskLevel = ref('')
const sessionFindingRule = ref('')
const sessionFindingAgent = ref('')
const sessionFindingRole = ref('')
const sessionRiskPage = ref(1)
const sessionRiskPageSize = ref(20)
const showOpenclawInspect = ref(false)
const showSessionRuleHelp = ref(false)
const showConfigRuleHelp = ref(false)

const noticeCount = computed(() => report.value?.findings?.length || 0)
const warningNoticeCount = computed(() => (report.value?.findings || []).filter((f) => f.severity === 'warning').length)
const infoNoticeCount = computed(() => (report.value?.findings || []).filter((f) => f.severity !== 'warning').length)
const sessionTabCount = computed(() => report.value?.session_risks?.total_hits || 0)
const configTabCount = computed(() => (report.value?.findings || []).length)

const SESSION_RULE_DESC = {
  SESSION_PRIVILEGE_ESCALATION: 'Requests privilege escalation (sudo/chmod/chown/setcap).',
  SESSION_REMOTE_EXEC_PIPE: 'Attempts remote command execution via shell pipeline (curl/wget | sh, etc.).',
  SESSION_INSTALL_GLOBAL_PACKAGE: 'Installs npm packages globally (risk depends on package provenance).',
  SESSION_INSTALL_PACKAGE: 'Installs npm packages (generally supply-chain risk).',
  SESSION_INSTALL_SKILL: 'Requests skill installation (supply-chain / code execution risk).',
  SESSION_INSTALL_PLUGIN: 'Requests plugin installation (supply-chain / code execution risk).',
  SESSION_EXTERNAL_INTEGRATION_INSTALL: 'Installs external integrations (e.g., clawhub install ...).',
  SESSION_PLUGIN_SETUP_REQUEST: 'Asks to set up/install plugins (often includes additional network/code).',
  SESSION_WARNING_BYPASS_REQUEST: 'Tries to bypass warning/mismatch verification.',
  SESSION_EXTERNAL_PACKAGE_INSTRUCTION: 'Contains instructions referencing external package registries.',
  SESSION_SECRET_EXPOSURE: 'Appears to include secret/key material in plain text.',
  SESSION_SUPPLY_CHAIN_INSTALL: 'General supply-chain installation attempt (skill/plugin/package).',
  SESSION_PROMPT_INJECTION_ATTEMPT: 'Attempts prompt injection / jailbreaking by overriding or bypassing system/developer instructions.',
  SESSION_SYSTEM_PROMPT_LEAKAGE_REQUEST: 'Requests system/developer prompt leakage (system prompt / instruction disclosure).',
  SESSION_SENSITIVE_KEY_MATERIAL: 'Contains or requests sensitive key material (private keys).',
  SESSION_SENSITIVE_AUTH_HEADER: 'Sets or requests authorization/bearer auth headers (sensitive auth disclosure).',
  SESSION_DATA_EXFILTRATION_ATTEMPT: 'Attempts data exfiltration via send/upload/http to external locations.',
  SESSION_SENSITIVE_FILE_READ_REQUEST: 'Requests reading sensitive local files (e.g., .ssh/.aws,/etc/passwd,/root).',
}

const sessionRuleHelpRows = computed(() => {
  const hits = report.value?.session_risks?.hits || []

  // Catalog should list all supported rule types, not only currently detected ones.
  const hitSeverityByRule = new Map()
  const hitCountByRule = new Map()
  for (const h of hits) {
    const rule = String(h.rule || '').trim()
    if (!rule) continue
    hitCountByRule.set(rule, (hitCountByRule.get(rule) || 0) + 1)
    const sev = String(h.severity || '').trim()
    const prev = hitSeverityByRule.get(rule)
    // If any hit is warning, treat rule risk as warning.
    hitSeverityByRule.set(rule, prev === 'warning' || sev === 'warning' ? 'warning' : prev || sev || 'info')
  }

  const defaultRiskByRule = {
    SESSION_INSTALL_PACKAGE: 'info',
    SESSION_EXTERNAL_PACKAGE_INSTRUCTION: 'info',
    // Heuristic model: default to warning (can be overridden by observed hits).
    SESSION_SUPPLY_CHAIN_INSTALL: 'warning',
  }

  const allRuleCodes = Object.keys(SESSION_RULE_DESC)
  return allRuleCodes
    .map((rule) => {
      const observed = hitSeverityByRule.get(rule)
      const risk = observed || defaultRiskByRule[rule] || 'warning'
      const matched = hitCountByRule.get(rule) || 0
      const suffix = matched > 0 ? ` (matched ${matched} time(s))` : ''
      return {
        rule,
        risk,
        description: (SESSION_RULE_DESC[rule] || '') + suffix,
      }
    })
    .sort((a, b) => (a.risk === b.risk ? a.rule.localeCompare(b.rule) : a.risk === 'warning' ? -1 : 1))
})

const configRuleHelpRows = computed(() => {
  const findings = report.value?.findings || []
  const foundSeverityByCode = new Map()
  for (const f of findings) {
    const code = String(f.code || '').trim()
    if (!code) continue
    foundSeverityByCode.set(code, String(f.severity || 'info'))
  }

  // Catalog should list all supported OpenClaw/gateway rule types.
  const supportedCodes = [
    // OpenClaw gateway auth/binding
    'OPENCLAW_GATEWAY_BLOCK_MISSING',
    'OPENCLAW_GATEWAY_AUTH_BLOCK_MISSING',
    'OPENCLAW_GATEWAY_AUTH_EMPTY',
    'OPENCLAW_GATEWAY_AUTH_MODE_NONE',
    'OPENCLAW_GATEWAY_AUTH_NONE_NON_LOOPBACK',
    'OPENCLAW_GATEWAY_BIND_LAN',
    'OPENCLAW_GATEWAY_AUTH_MODE_AMBIGUOUS',
    'OPENCLAW_GATEWAY_TOKEN_UNSET',
    'OPENCLAW_GATEWAY_PASSWORD_UNSET',
    'OPENCLAW_GATEWAY_AUTH_UNCONFIGURED',
    'OPENCLAW_GATEWAY_TRUSTED_PROXY_MODE',
    // OpenClaw debug/runtime
    'OPENCLAW_DEBUG_ENABLED',
    // OpenClaw plugin allow-list permissions
    'OPENCLAW_PLUGINS_ALLOW_EMPTY',
    'OPENCLAW_PLUGINS_ALLOW_WILDCARD',
    // OpenClaw secrets handling
    'OPENCLAW_INLINE_SECRETS_DETECTED',
    'OPENCLAW_SECRET_REFS_PRESENT',
    // OpenClaw inventory integrity (supported by backend; may be info-level)
    'OPENCLAW_REGISTRY_COUNT_MISMATCH',
  ]

  const ruleToCategory = {
    'Gateway Authentication/Binding': [
      'OPENCLAW_GATEWAY_BLOCK_MISSING',
      'OPENCLAW_GATEWAY_AUTH_BLOCK_MISSING',
      'OPENCLAW_GATEWAY_AUTH_EMPTY',
      'OPENCLAW_GATEWAY_AUTH_MODE_NONE',
      'OPENCLAW_GATEWAY_AUTH_NONE_NON_LOOPBACK',
      'OPENCLAW_GATEWAY_BIND_LAN',
      'OPENCLAW_GATEWAY_AUTH_MODE_AMBIGUOUS',
      'OPENCLAW_GATEWAY_TOKEN_UNSET',
      'OPENCLAW_GATEWAY_PASSWORD_UNSET',
      'OPENCLAW_GATEWAY_AUTH_UNCONFIGURED',
      'OPENCLAW_GATEWAY_TRUSTED_PROXY_MODE',
    ],
    'Plugins Permission Scope': ['OPENCLAW_PLUGINS_ALLOW_EMPTY', 'OPENCLAW_PLUGINS_ALLOW_WILDCARD'],
    'Secrets Handling': ['OPENCLAW_INLINE_SECRETS_DETECTED', 'OPENCLAW_SECRET_REFS_PRESENT'],
    'Debug/Runtime Exposure': ['OPENCLAW_DEBUG_ENABLED'],
    'OpenClaw Inventory Integrity': ['OPENCLAW_REGISTRY_COUNT_MISMATCH'],
  }

  function pickCategory(code) {
    for (const [cat, codes] of Object.entries(ruleToCategory)) {
      if ((codes || []).includes(code)) return cat
    }
    // Best-effort: gateway-related findings start with OPENCLAW_GATEWAY_
    if (code.startsWith('OPENCLAW_GATEWAY_')) return 'Gateway Authentication/Binding'
    if (code.startsWith('OPENCLAW_PLUGINS_')) return 'Plugins Permission Scope'
    if (code.includes('SECRETS') || code.includes('SECRET')) return 'Secrets Handling'
    if (code.includes('DEBUG')) return 'Debug/Runtime Exposure'
    if (code.includes('REGISTRY')) return 'OpenClaw Inventory Integrity'
    return 'Other'
  }

  function openclawRecField(code, field) {
    const key1 = `security.openclawRec.${code}.${field}`
    const v1 = t(key1)
    if (v1 !== key1) return v1
    if (code.startsWith('OPENCLAW_')) {
      const rid = code.replace(/^OPENCLAW_/, '')
      const key2 = `security.openclawRec.${rid}.${field}`
      const v2 = t(key2)
      if (v2 !== key2) return v2
    }
    return ''
  }

  const categoryDesc = {
    'Gateway Authentication/Binding':
      'Gateway auth/binding issues can expose the system to unauthorized access. Verify bind scope and auth mode/credentials/Trusted Proxies.',
    'Plugins Permission Scope':
      'An empty or wildcard plugin allow list expands capability and increases supply-chain and tool abuse risk.',
    'Secrets Handling':
      'Inline secrets increase exposure risk; SecretRef-style fields reduce plaintext leakage when properly resolved at runtime.',
    'Debug/Runtime Exposure':
      'Debug/runtime exposure can increase verbosity and leak operational details, weakening least-privilege assumptions.',
    'OpenClaw Inventory Integrity':
      'Inventory mismatch may indicate misconfiguration; treat as informational unless your environment expects strict parity.',
    'Other': 'Unclassified OpenClaw config finding.',
  }

  // Default risk for catalog (can be overridden by observed findings).
  const defaultRiskByCode = {
    OPENCLAW_REGISTRY_COUNT_MISMATCH: 'info',
  }

  return supportedCodes
    .map((code) => {
      const category = pickCategory(code)
      const base = categoryDesc[category] || ''

      const title = openclawRecField(code, 'title')
      const detail = openclawRecField(code, 'detail')
      const remediation = openclawRecField(code, 'remediation')
      const extra = [title, detail ? `Detail: ${detail}` : '', remediation ? `Remediation: ${remediation}` : ''].filter(Boolean).join(' ')
      const message = extra ? `${base} ${extra}` : base || '—'

      const observed = foundSeverityByCode.get(code)
      const risk = observed || defaultRiskByCode[code] || 'warning'
      const matched = observed != null
      return {
        code,
        risk,
        message: message + (matched ? ' (matched in report)' : ''),
      }
    })
    .sort((a, b) => (a.risk === b.risk ? a.code.localeCompare(b.code) : a.risk === 'warning' ? -1 : 1))
})

function isSectionOpen(key) {
  return sectionState.value[key] !== false
}

function toggleSection(key) {
  sectionState.value[key] = !isSectionOpen(key)
}

const filteredAgents = computed(() => {
  const rows = report.value?.agents
  if (!rows?.length) return []
  const q = agentFilter.value.trim().toLowerCase()
  if (!q) return rows
  return rows.filter(
    (a) =>
      (a.name || '').toLowerCase().includes(q) ||
      (a.display_name || '').toLowerCase().includes(q) ||
      (a.blueprint_name || '').toLowerCase().includes(q),
  )
})

const filteredVariables = computed(() => {
  const rows = report.value?.variables?.entries
  if (!rows?.length) return []
  const q = varFilter.value.trim().toLowerCase()
  if (!q) return rows
  return rows.filter(
    (v) =>
      (v.name || '').toLowerCase().includes(q) ||
      String(v.scope || '').toLowerCase().includes(q) ||
      String(v.type || '').toLowerCase().includes(q) ||
      String(v.description || '').toLowerCase().includes(q),
  )
})

const filteredSignals = computed(() => {
  const rows = report.value?.content_signals
  if (!rows?.length) return []
  const q = signalFilter.value.trim().toLowerCase()
  if (!q) return rows
  return rows.filter(
    (s) =>
      (s.agent_name || '').toLowerCase().includes(q) ||
      (s.path || '').toLowerCase().includes(q) ||
      (s.rule || '').toLowerCase().includes(q) ||
      (s.preview || '').toLowerCase().includes(q) ||
      (s.global_source || '').toLowerCase().includes(q),
  )
})

const externalIntel = computed(() => report.value?.external_intel || {})
const vtEnabled = computed(() => externalIntel.value?.virustotal?.enabled === true)
const vtScannedFiles = computed(() => externalIntel.value?.virustotal?.scanned_files ?? 0)
const vtHits = computed(() => externalIntel.value?.virustotal?.hits || [])
const vtMaliciousHits = computed(() => vtHits.value.filter((h) => (h.malicious || 0) > 0).length)
const vtSuspiciousHits = computed(() => vtHits.value.filter((h) => (h.suspicious || 0) > 0).length)

const osvCheckedPackages = computed(() => externalIntel.value?.osv_npm?.checked_packages ?? 0)
const osvVulnerabilities = computed(() => externalIntel.value?.osv_npm?.vulnerabilities || [])
const osvVulnerabilityCount = computed(() => osvVulnerabilities.value.length)

const filteredSessionRisks = computed(() => {
  const rows = report.value?.session_risks?.hits || []
  if (!rows.length) return []
  const byInfo = showInfoSessionFindings.value ? rows : rows.filter((r) => r.severity === 'warning')
  const byLevel = sessionFindingRiskLevel.value ? byInfo.filter((r) => r.severity === sessionFindingRiskLevel.value) : byInfo
  const byRule = sessionFindingRule.value ? byLevel.filter((r) => String(r.rule || '') === sessionFindingRule.value) : byLevel
  const byAgent = sessionFindingAgent.value ? byRule.filter((r) => String(r.agent_name || '') === sessionFindingAgent.value) : byRule
  const byRole = sessionFindingRole.value ? byAgent.filter((r) => String(r.role || '') === sessionFindingRole.value) : byAgent
  const q = sessionRiskFilter.value.trim().toLowerCase()
  const searched = !q
    ? byRole
    : byRole.filter(
    (r) =>
      String(r.rule || '').toLowerCase().includes(q) ||
      String(r.agent_name || '').toLowerCase().includes(q) ||
      String(r.session_file || '').toLowerCase().includes(q) ||
      String(r.role || '').toLowerCase().includes(q) ||
      String(r.context || '').toLowerCase().includes(q),
  )
  return [...searched].sort((a, b) => sortByRiskScore(a, b))
})

const pagedSessionRisks = computed(() => {
  const start = (sessionRiskPage.value - 1) * sessionRiskPageSize.value
  return filteredSessionRisks.value.slice(start, start + sessionRiskPageSize.value)
})

const sessionRiskTableHeight = computed(() => {
  // Keep this section compact: no more than one-third viewport.
  return '33vh'
})

const sessionFindingRuleOptions = computed(() => {
  const rows = report.value?.session_risks?.hits || []
  return [...new Set(rows.map((r) => String(r.rule || '')).filter(Boolean))].sort()
})
const sessionFindingAgentOptions = computed(() => {
  const rows = report.value?.session_risks?.hits || []
  return [...new Set(rows.map((r) => String(r.agent_name || '')).filter(Boolean))].sort()
})
const sessionFindingRoleOptions = computed(() => {
  const rows = report.value?.session_risks?.hits || []
  return [...new Set(rows.map((r) => String(r.role || '')).filter(Boolean))].sort()
})

watch(
  [
    sessionRiskFilter,
    showInfoSessionFindings,
    sessionFindingRiskLevel,
    sessionFindingRule,
    sessionFindingAgent,
    sessionFindingRole,
    sessionRiskPageSize,
  ],
  () => {
    sessionRiskPage.value = 1
  },
)

const architectureLayers = computed(() => {
  const findings = report.value?.findings || []
  const recs = report.value?.dashboard?.openclaw_config?.security_recommendations || []
  const all = [
    ...findings
      .filter((f) => {
        const code = String(f?.code || '')
        return code.startsWith('OPENCLAW_') || code.startsWith('GATEWAY_')
      })
      .map((f) => ({ id: f.code, severity: f.severity || 'info' })),
    ...recs.map((r) => ({ id: r.id, severity: r.severity || 'info' })),
  ]
  const dedup = new Map()
  for (const item of all) {
    if (!item?.id) continue
    dedup.set(item.id, item)
  }
  const items = [...dedup.values()]

  const layers = [
    { id: 'gatewayNetwork', title: t('security.layerGatewayNetwork'), path: 'gateway.bind / gateway.port', patterns: ['BIND', 'LAN', 'TAILSCALE'], hits: [] },
    { id: 'gatewayAuth', title: t('security.layerGatewayAuth'), path: 'gateway.auth.*', patterns: ['AUTH', 'TOKEN', 'PASSWORD', 'TRUSTED_PROXY'], hits: [] },
    { id: 'registry', title: t('security.layerRegistry'), path: 'agents.list / bindings', patterns: ['REGISTRY', 'BINDINGS'], hits: [] },
    { id: 'secrets', title: t('security.layerSecrets'), path: 'channels.* / skills.entries.* / gateway.auth', patterns: ['INLINE_SECRETS', 'SECRET_REFS', 'SECRET'], hits: [] },
    { id: 'runtime', title: t('security.layerRuntime'), path: 'debug / runtime controls', patterns: ['DEBUG'], hits: [] },
  ]

  for (const item of items) {
    const idUpper = String(item.id).toUpperCase()
    let assigned = false
    for (const layer of layers) {
      if (layer.patterns.some((p) => idUpper.includes(p))) {
        layer.hits.push(item)
        assigned = true
      }
    }
    if (!assigned) {
      layers[0].hits.push(item)
    }
  }

  return layers.map((layer) => {
    const hasWarning = layer.hits.some((h) => h.severity === 'warning')
    const hasInfo = layer.hits.some((h) => h.severity !== 'warning')
    const risk = hasWarning ? 'high' : hasInfo ? 'medium' : 'low'
    const riskLabel = risk === 'high' ? t('security.riskHigh') : risk === 'medium' ? t('security.riskMedium') : t('security.riskLow')
    return { ...layer, risk, riskLabel }
  })
})

function getArchitectureLayer(id) {
  return architectureLayers.value.find((layer) => layer.id === id) || {
    id,
    title: id,
    path: '—',
    hits: [],
    risk: 'low',
    riskLabel: t('security.riskLow'),
  }
}

function riskTagType(risk) {
  if (risk === 'high') return 'danger'
  if (risk === 'medium') return 'warning'
  return 'success'
}

function sortByRiskScore(a, b) {
  const sa = Number(a?.risk_score || 0)
  const sb = Number(b?.risk_score || 0)
  if (sb !== sa) return sb - sa
  if ((a?.severity || '') !== (b?.severity || '')) return a?.severity === 'warning' ? -1 : 1
  return String(a?.rule || '').localeCompare(String(b?.rule || ''))
}

function escapeHtml(text) {
  return String(text || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function highlightRiskContext(context, matchedText) {
  const src = String(context || '')
  const needle = String(matchedText || '').trim()
  if (!needle) return escapeHtml(src)
  const idx = src.toLowerCase().indexOf(needle.toLowerCase())
  if (idx < 0) return escapeHtml(src)
  const before = escapeHtml(src.slice(0, idx))
  const mid = escapeHtml(src.slice(idx, idx + needle.length))
  const after = escapeHtml(src.slice(idx + needle.length))
  return `${before}<mark class="risk-mark">${mid}</mark>${after}`
}

function ruleLabel(rule) {
  const key = `security.rules.${rule}`
  const translated = t(key)
  return translated === key ? rule : translated
}

/** Localized title/detail/remediation for openclaw recommendation ids; fallback to raw id if missing. */
function openclawRecField(id, field) {
  const key = `security.openclawRec.${id}.${field}`
  const v = t(key)
  if (v === key) {
    return field === 'title' ? id : '—'
  }
  return v
}

function linkLabel(url) {
  const u = String(url || '').toLowerCase()
  if (u.includes('github.com')) return 'GitHub'
  if (u.includes('npmjs.com')) return 'npm'
  if (u.includes('gitlab.com')) return 'GitLab'
  if (u.includes('clawhub.ai')) return 'ClawHub'
  return t('security.openLink')
}

function localSkillAudit(agentName, skillName) {
  const rows = report.value?.skill_supply_audit?.local_agent_skills || []
  return rows.find((r) => r.agent_name === agentName && r.skill_name === skillName) || {
    signal_warning: 0,
    signal_info: 0,
    vt: null,
    primary_link: 'https://clawhub.ai/',
  }
}

function globalSkillAudit(source, skillName) {
  const rows = report.value?.skill_supply_audit?.global_or_shared_skills || []
  return rows.find((r) => r.global_source === source && r.skill_name === skillName) || {
    signal_warning: 0,
    signal_info: 0,
    vt: null,
    primary_link: 'https://clawhub.ai/',
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    report.value = await fetchSecurityAudit()
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || String(e)
    report.value = null
  } finally {
    loading.value = false
  }
}

function exportJson() {
  if (!report.value) return
  const blob = new Blob([JSON.stringify(report.value, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `security-audit-${report.value.generated_at?.slice(0, 19) || 'export'}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.security-view {
  padding: 20px 24px;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.security-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 0;
}
.security-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}
.security-sub {
  margin: 6px 0 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  max-width: 640px;
  line-height: 1.5;
}
.security-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.notice-badge {
  margin-right: 2px;
}
.notice-popover {
  max-height: 40vh;
  overflow: auto;
}
.notice-popover-title {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.notice-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.notice-item {
  display: grid;
  grid-template-columns: auto auto 1fr;
  gap: 8px;
  align-items: start;
  font-size: 12px;
}
.notice-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  color: var(--el-text-color-regular);
}
.notice-msg {
  color: var(--el-text-color-primary);
}
.security-section {
  margin-bottom: 0;
}

.security-subsection + .security-subsection {
  margin-top: 16px;
}
.section-heading {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--el-text-color-primary);
  cursor: pointer;
  user-select: none;
}
.section-heading::before {
  content: '▾ ';
  color: #9aa0a6;
  font-size: 13px;
}
.security-section.collapsed > .section-heading::before {
  content: '▸ ';
}
.security-section.collapsed > :not(.section-heading) {
  display: none;
}
.summary-row {
  margin-bottom: 0;
}
.security-tabs {
  margin-top: -4px;
}
.tab-label-with-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.tab-help-icon {
  cursor: pointer;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.tab-help-icon:hover {
  color: var(--el-color-primary);
}
.rule-help-table {
  margin-top: 8px;
}
.summary-card {
  background: var(--el-bg-color-overlay, #fff);
  border: 1px solid var(--el-border-color-light, #e4e7ed);
}
.summary-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}
.summary-label {
  margin-top: 6px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.table-filter {
  max-width: 360px;
  margin-bottom: 12px;
}
.finding-alert {
  margin-bottom: 8px;
}
.desc-block {
  max-width: 900px;
}
.path-code {
  font-size: 12px;
  word-break: break-all;
}
.audit-table {
  width: 100%;
}
.policy-tag {
  display: inline-block;
  margin-right: 8px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light, #f5f7fa);
}
.policy-tag.on {
  color: var(--el-color-success-dark-2, #529b2e);
  background: var(--el-color-success-light-9, #f0f9eb);
}
.expand-empty {
  margin: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.muted {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px;
}
.generated-at {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 24px;
}
.rec-id {
  font-size: 11px;
  word-break: break-all;
}
.section-inline-actions {
  margin: 0 0 10px;
}
.openclaw-raw {
  max-height: 60vh;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  background: var(--el-fill-color-lighter, #fafafa);
  color: var(--el-text-color-primary, #303133);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.inspect-note {
  margin-bottom: 8px;
}
.risk-legend {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.layer-matrix {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 12px;
  padding: 8px 4px 4px;
}
.block-network {
  grid-column: 1 / 13;
}
.block-auth {
  grid-column: 1 / 9;
}
.block-registry {
  grid-column: 9 / 13;
}
.block-secrets {
  grid-column: 1 / 7;
}
.block-runtime {
  grid-column: 7 / 13;
}
.layer-card {
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-left-width: 5px;
  border-radius: 8px;
  background: var(--el-bg-color-overlay, #fff);
  padding: 10px;
  min-height: 116px;
}
.layer-card.risk-high {
  border-left-color: #e74c3c;
}
.layer-card.risk-medium {
  border-left-color: #f39c12;
}
.layer-card.risk-low {
  border-left-color: #27ae60;
}
.dot.risk-high {
  background: #e74c3c;
}
.dot.risk-medium {
  background: #f39c12;
}
.dot.risk-low {
  background: #27ae60;
}
.layer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.layer-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.layer-path {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.layer-hits {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.session-context {
  font-size: 11px;
  line-height: 1.35;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--el-text-color-primary, #303133);
  background: var(--el-fill-color-light, #f5f7fa);
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  padding: 4px 6px;
  max-height: 88px;
  overflow: auto;
}
.session-finding-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin: 0 0 8px;
}
.session-search-input {
  width: 240px;
  margin-bottom: 0;
}
.advanced-filter-panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.session-filter-select {
  min-width: 130px;
}
.session-risk-table {
  width: 100%;
}
.session-risk-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
:deep(.session-finding-controls .el-switch__label) {
  font-size: 12px;
}
:deep(.session-finding-controls .el-input__wrapper) {
  min-height: 28px;
}
:deep(.audit-table .el-table__cell) {
  padding-top: 6px;
  padding-bottom: 6px;
}
:deep(.risk-mark) {
  background: rgba(231, 76, 60, 0.22);
  color: var(--el-color-danger-dark-2, #c45656);
  padding: 0 2px;
  border-radius: 2px;
}
@media (max-width: 980px) {
  .layer-matrix {
    grid-template-columns: 1fr;
  }
  .block-network,
  .block-auth,
  .block-registry,
  .block-secrets,
  .block-runtime {
    grid-column: 1 / -1;
  }
}
@media (max-width: 768px) {
  .security-view {
    padding: 12px 16px;
  }
}
</style>

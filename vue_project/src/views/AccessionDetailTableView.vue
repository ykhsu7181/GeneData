<template>
  <div :class="['accession-page', embedded ? 'is-embedded' : '']">
    <div class="accession-breadcrumb">{{ $t('page.accessionDetail.breadcrumb', { accession: routeAccession || '-' }) }}</div>

    <div class="page-heading">
      <div>
        <div class="page-kicker">ACCESSION</div>
        <h1>{{ $t('page.accessionDetail.title', { accession: accession?.accession || routeAccession || '-' }) }}</h1>
        <div v-if="accession" class="heading-tags">
          <span class="heading-tag species-tag">{{ $t('page.accessionDetail.species', { value: speciesLabel }) }}</span>
          <span class="heading-tag population-tag">{{ $t('page.accessionDetail.subPopulation', { value: accession.sub_population || '-' }) }}</span>
        </div>
      </div>
      <div class="heading-actions">
        <button v-if="!embedded" type="button" class="back-search-button" @click="goBackToSearch">{{ $t('page.accessionDetail.backToSearch') }}</button>
        <el-tooltip :content="$t('common.refresh')" placement="top"><el-button circle class="refresh-button" @click="refreshPage"><el-icon><Refresh /></el-icon></el-button></el-tooltip>
      </div>
    </div>

    <div v-if="loading" class="state-card"><el-skeleton :rows="12" animated /></div>
    <div v-else-if="!routeAccession" class="state-card"><el-empty :description="$t('page.accessionDetail.selectPrompt')" /></div>
    <div v-else-if="errorMessage" class="state-card"><el-empty :description="errorMessage" /></div>

    <template v-else-if="accession">
      <div class="summary-grid">
        <article v-for="card in summaryCards" :key="card.key" class="summary-card">
          <span class="summary-icon">{{ card.icon }}</span>
          <div><div class="summary-label">{{ card.label }}</div><div class="summary-value">{{ card.value }}</div></div>
        </article>
      </div>

      <div class="accession-layout">
        <main class="detail-column">
          <nav class="section-tabs" :aria-label="$t('page.accessionDetail.sectionsLabel')">
            <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="selectTab(tab.key)">{{ $t(tab.labelKey) }}</button>
          </nav>

          <section v-if="activeTab === 'basic'" class="detail-section">
            <h2>{{ $t('common.basicInformation') }}</h2>
            <div class="basic-info-grid">
              <div v-for="row in basicInfoRows" :key="row.label" class="basic-info-row">
                <span class="field-label">{{ row.label }}</span>
                <a v-if="row.link && row.value !== '-'" :href="row.value" target="_blank" rel="noopener noreferrer" class="field-link">{{ row.value }}</a>
                <span v-else class="field-value">{{ row.value }}</span>
              </div>
            </div>
            <h3>{{ $t('page.accessionDetail.externalIdentifiers') }}</h3>
            <div class="identifier-grid">
              <article class="identifier-card"><span>ENA Study</span><strong>{{ external.ena_studies?.join('、') || '-' }}</strong></article>
              <article class="identifier-card"><span>BioSample</span><strong>{{ external.biosample_count || 0 }}</strong></article>
              <article class="identifier-card"><span>Experiment</span><strong>{{ external.experiment_count || 0 }}</strong></article>
              <article class="identifier-card"><span>Run</span><strong>{{ external.run_count || 0 }}</strong></article>
            </div>
          </section>

          <section v-else class="detail-section">
            <div class="section-title-row"><h2>{{ activeTabLabel }}</h2><span v-if="tabLoading" class="table-loading">{{ $t('page.accessionDetail.loading') }}</span></div>

            <div v-if="activeTab === 'datasets'" class="table-shell"><table class="detail-table"><thead><tr><th>{{ $t('page.accessionDetail.columns.datasetCode') }}</th><th>{{ $t('page.accessionDetail.columns.datasetName') }}</th><th>{{ $t('page.accessionDetail.columns.type') }}</th><th>BioProject</th><th>{{ $t('page.accessionDetail.columns.externalDatabase') }}</th><th>{{ $t('page.accessionDetail.columns.runCount') }}</th></tr></thead><tbody><tr v-for="item in tabRows" :key="item.id"><td>{{ item.dataset_code }}</td><td>{{ item.dataset_name || '-' }}</td><td>{{ item.dataset_type || '-' }}</td><td>{{ item.bioproject_accession || '-' }}</td><td>{{ item.external_database || '-' }}</td><td>{{ item.run_count }}</td></tr><tr v-if="!tabRows.length && !tabLoading"><td colspan="6" class="empty-table-cell">{{ $t('page.accessionDetail.empty.datasets') }}</td></tr></tbody></table></div>

            <div v-else-if="activeTab === 'samples'" class="table-shell"><table class="detail-table"><thead><tr><th>{{ $t('page.accessionDetail.columns.sampleName') }}</th><th>{{ $t('page.accessionDetail.columns.sampleCode') }}</th><th>{{ $t('page.accessionDetail.columns.tissue') }}</th><th>{{ $t('common.dataType') }}</th><th>Experiment</th></tr></thead><tbody><tr v-for="item in tabRows" :key="item.id"><td>{{ item.sample_name }}</td><td>{{ item.biosample_accession }}</td><td>{{ item.tissue }}</td><td>{{ item.data_type }}</td><td>{{ item.experiment_accession }}</td></tr><tr v-if="!tabRows.length && !tabLoading"><td colspan="5" class="empty-table-cell">{{ $t('page.accessionDetail.empty.samples') }}</td></tr></tbody></table></div>

            <div v-else-if="activeTab === 'assemblies'" class="table-shell"><table class="detail-table"><thead><tr><th>{{ $t('page.accessionDetail.columns.assemblyVersion') }}</th><th>{{ $t('page.accessionDetail.columns.assemblyCode') }}</th><th>{{ $t('page.accessionDetail.columns.referenceGenome') }}</th><th>BioProject</th><th>Reference</th><th>{{ $t('common.actions') }}</th></tr></thead><tbody><tr v-for="item in tabRows" :key="item.id"><td>{{ item.display_name || item.name }}</td><td>{{ item.standard_id || '-' }}</td><td>{{ item.reference || '-' }}</td><td>{{ item.bio_project || '-' }}</td><td>{{ item.reference || '-' }}</td><td><button class="table-action" type="button" @click="openFiles('assembly', item.id)">{{ $t('page.accessionDetail.viewFiles') }}</button></td></tr><tr v-if="!tabRows.length && !tabLoading"><td colspan="6" class="empty-table-cell">{{ $t('page.accessionDetail.empty.assemblies') }}</td></tr></tbody></table></div>

            <div v-else-if="activeTab === 'annotations'" class="table-shell"><table class="detail-table"><thead><tr><th>{{ $t('page.accessionDetail.columns.annotationVersion') }}</th><th>{{ $t('page.accessionDetail.columns.annotationCode') }}</th><th>{{ $t('page.accessionDetail.columns.sourceMethod') }}</th><th>{{ $t('page.accessionDetail.columns.relatedAssembly') }}</th><th>{{ $t('common.actions') }}</th></tr></thead><tbody><tr v-for="item in tabRows" :key="item.id"><td>{{ item.display_name || item.name }}</td><td>{{ item.standard_id || '-' }}</td><td>{{ item.source_name || '-' }}</td><td>{{ item.assembly_name || '-' }}</td><td><button class="table-action" type="button" @click="openFiles('annotation', item.id)">{{ $t('page.accessionDetail.viewFiles') }}</button></td></tr><tr v-if="!tabRows.length && !tabLoading"><td colspan="5" class="empty-table-cell">{{ $t('page.accessionDetail.empty.annotations') }}</td></tr></tbody></table></div>

            <div v-else-if="activeTab === 'files'" class="table-shell"><table class="detail-table"><thead><tr><th>{{ $t('common.fileName') }}</th><th>{{ $t('common.fileRole') }}</th><th>{{ $t('page.accessionDetail.columns.relatedType') }}</th><th>{{ $t('common.fileType') }}</th><th>{{ $t('page.accessionDetail.columns.size') }}</th><th>{{ $t('common.download') }}</th></tr></thead><tbody><tr v-for="item in filteredFiles" :key="item.id"><td>{{ item.file_name }}</td><td><span class="role-chip">{{ item.file_role }}</span></td><td>{{ item.related_type }}</td><td>{{ item.file_type }}</td><td>{{ item.size_display }}</td><td><button class="download-action" type="button" @click="downloadFile(item)">{{ $t('page.accessionDetail.datafileDownload') }}</button></td></tr><tr v-if="!filteredFiles.length && !tabLoading"><td colspan="6" class="empty-table-cell">{{ $t('page.accessionDetail.empty.files') }}</td></tr></tbody></table></div>

            <div v-if="tabPagination.total > tabPagination.page_size" class="pagination-note">{{ $t('page.accessionDetail.pagination', { total: tabPagination.total, page: tabPagination.page }) }}</div>
          </section>
        </main>

        <aside class="side-column">
          <section class="side-card map-card"><div class="side-card-heading"><h2>{{ $t('page.accessionDetail.geography') }}</h2></div><div v-if="geography.has_point" class="map-placeholder"><span class="map-pin">●</span><strong>{{ accession.accession }}</strong><small>{{ $t('page.accessionDetail.coordinatesRecorded') }}</small></div><el-empty v-else :description="$t('page.accessionDetail.noCoordinates')" :image-size="72" /></section>
          <section class="side-card relation-card"><div class="side-card-heading"><h2>{{ $t('page.accessionDetail.relationship') }}</h2><span>{{ $t('page.accessionDetail.relationshipStructure') }}</span></div><div class="structure-root">{{ accession.accession }}</div><div v-if="relationship.assemblies?.length" class="structure-list"><div v-for="assembly in relationship.assemblies" :key="assembly.id" class="structure-assembly"><strong>{{ assembly.display_name || assembly.name }}</strong><span v-for="annotation in annotationsForAssembly(assembly.id)" :key="annotation.id">{{ annotation.display_name || annotation.name }}</span></div></div><p v-else class="empty-structure">{{ $t('page.accessionDetail.noRelationship') }}</p></section>
        </aside>
      </div>
    </template>
  </div>
</template>

<script>
import { computed, ref, watch } from 'vue';
import { Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import axios from 'axios';

const tabs = [
  { key: 'basic', labelKey: 'page.accessionDetail.tabs.basic' }, { key: 'datasets', labelKey: 'page.accessionDetail.tabs.datasets' },
  { key: 'samples', labelKey: 'page.accessionDetail.tabs.samples' }, { key: 'assemblies', labelKey: 'page.accessionDetail.tabs.assemblies' },
  { key: 'annotations', labelKey: 'page.accessionDetail.tabs.annotations' }, { key: 'files', labelKey: 'page.accessionDetail.tabs.files' }
];

export default {
  name: 'AccessionDetailTableView',
  components: { Refresh },
  props: { embedded: { type: Boolean, default: false } },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { locale, t } = useI18n();
    const loading = ref(false);
    const tabLoading = ref(false);
    const errorMessageKey = ref('');
    const summaryData = ref({});
    const activeTab = ref('basic');
    const tabRows = ref([]);
    const tabPagination = ref({ page: 1, page_size: 20, total: 0 });
    const fileScope = ref(null);
    const loadedTabs = ref(new Set());
    const routeAccession = computed(() => String(route.query.accession || route.query.organism || '').trim());
    const accession = computed(() => summaryData.value.accession || null);
    const summary = computed(() => summaryData.value.summary || {});
    const external = computed(() => summaryData.value.external_identifiers || {});
    const geography = computed(() => summaryData.value.geography || {});
    const relationship = computed(() => summaryData.value.relationship_overview || {});
    const errorMessage = computed(() => errorMessageKey.value ? t(errorMessageKey.value) : '');
    const activeTabLabel = computed(() => {
      const labelKey = tabs.find((item) => item.key === activeTab.value)?.labelKey;
      return labelKey ? t(labelKey) : '';
    });
    const speciesLabel = computed(() => {
      const species = accession.value?.species;
      if (!species) return '-';
      const name = locale.value === 'zh'
        ? species.chinese_name || species.common_name || species.species_code
        : species.common_name || species.species_code || species.chinese_name;
      return species.scientific_name ? `${name} (${species.scientific_name})` : name;
    });
    const summaryCards = computed(() => [
      { key: 'sample', label: t('page.accessionDetail.summary.samples'), value: summary.value.sample_count ?? 0, icon: '⚗' },
      { key: 'dataset', label: t('page.accessionDetail.summary.datasets'), value: summary.value.dataset_count ?? 0, icon: '▰' },
      { key: 'assembly', label: t('page.accessionDetail.summary.assemblies'), value: summary.value.assembly_count ?? 0, icon: '⌛' },
      { key: 'annotation', label: t('page.accessionDetail.summary.annotations'), value: summary.value.annotation_count ?? 0, icon: '✎' },
      { key: 'file', label: t('page.accessionDetail.summary.files'), value: summary.value.file_count ?? 0, icon: '▤' },
      { key: 'size', label: t('page.accessionDetail.summary.totalSize'), value: summary.value.total_size_display || '0 B', icon: '▣' }
    ]);
    const basicInfoRows = computed(() => {
      const data = accession.value || {};
      return [
        { label: t('page.accessionDetail.fields.accession'), value: data.accession || '-' }, { label: t('page.accessionDetail.fields.species'), value: speciesLabel.value },
        { label: t('page.accessionDetail.fields.subPopulation'), value: data.sub_population || '-' }, { label: t('page.accessionDetail.fields.longitude'), value: data.longitude ?? '-' },
        { label: t('page.accessionDetail.fields.region'), value: data.region || '-' }, { label: t('page.accessionDetail.fields.latitude'), value: data.latitude ?? '-' },
        { label: t('page.accessionDetail.fields.country'), value: data.country || '-' }, { label: t('page.accessionDetail.fields.description'), value: data.description || '-' },
        { label: t('page.accessionDetail.fields.externalLink'), value: data.external_link || '-', link: Boolean(data.external_link) }
      ];
    });
    const filteredFiles = computed(() => !fileScope.value ? tabRows.value : tabRows.value.filter((item) => item.relations?.some((relation) => relation.related_type === fileScope.value.type && String(relation.related_id) === String(fileScope.value.id))));
    const annotationsForAssembly = (assemblyId) => (relationship.value.annotations || []).filter((item) => String(item.assembly_id) === String(assemblyId));

    const reset = () => { summaryData.value = {}; tabRows.value = []; tabPagination.value = { page: 1, page_size: 20, total: 0 }; loadedTabs.value = new Set(); fileScope.value = null; activeTab.value = 'basic'; };
    const fetchSummary = async () => {
      if (!routeAccession.value) { reset(); return; }
      loading.value = true; errorMessageKey.value = '';
      try {
        const response = await axios.get(`/files/accessions/${encodeURIComponent(routeAccession.value)}/summary/`);
        if (!response.data?.success) throw new Error('Request failed');
        summaryData.value = response.data.data || {};
        loadedTabs.value = new Set(['basic']);
      } catch { reset(); errorMessageKey.value = 'messages.accessionLoadFailed'; }
      finally { loading.value = false; }
    };
    const fetchTab = async (tab) => {
      if (tab === 'basic' || !routeAccession.value) return;
      tabLoading.value = true;
      try {
        const response = await axios.get(`/files/accessions/${encodeURIComponent(routeAccession.value)}/${tab}/`, { params: { page: 1, page_size: 20 } });
        if (!response.data?.success) throw new Error('Request failed');
        tabRows.value = response.data.data?.results || [];
        tabPagination.value = response.data.data?.pagination || { page: 1, page_size: 20, total: 0 };
        loadedTabs.value.add(tab);
      } catch { tabRows.value = []; tabPagination.value = { page: 1, page_size: 20, total: 0 }; ElMessage.error(t('messages.accessionTabLoadFailed')); }
      finally { tabLoading.value = false; }
    };
    const selectTab = async (tab) => { activeTab.value = tab; fileScope.value = null; if (tab !== 'basic') await fetchTab(tab); };
    const openFiles = async (type, id) => { fileScope.value = { type, id }; activeTab.value = 'files'; await fetchTab('files'); };
    const downloadFile = (file) => { if (!file?.datafile_download_url) { ElMessage.error(t('messages.missingDatafileUrl')); return; } window.open(new URL(file.datafile_download_url, window.location.origin).toString(), '_blank'); };
    const refreshPage = async () => { await fetchSummary(); if (activeTab.value !== 'basic') await fetchTab(activeTab.value); };
    const goBackToSearch = async () => router.push({ name: 'accession-card' });
    watch(routeAccession, fetchSummary, { immediate: true });
    return { accession, activeTab, activeTabLabel, annotationsForAssembly, basicInfoRows, downloadFile, errorMessage, external, filteredFiles, geography, goBackToSearch, loading, openFiles, refreshPage, relationship, routeAccession, selectTab, speciesLabel, summaryCards, tabLoading, tabPagination, tabRows, tabs };
  }
};
</script>

<style scoped>
.accession-page { padding: 8px 0 36px; color: #15233d; }
.accession-breadcrumb { margin-bottom: 12px; color: #76849a; font-size: 13px; }.page-heading { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }.page-kicker { color:#1760e8; font-size:11px; font-weight:800; letter-spacing:.16em; }.page-heading h1 { margin:4px 0 10px; font-size:30px; }.heading-tags { display:flex; gap:8px; }.heading-tag { padding:5px 12px; border-radius:999px; font-size:12px; font-weight:700; }.species-tag { color:#1c5bc5; background:#eaf2ff; border:1px solid #cfe0ff; }.population-tag { color:#327b46; background:#eaf8ed; border:1px solid #ccebd3; }.heading-actions { display:flex; gap:10px; }.back-search-button,.table-action,.download-action { height:34px; padding:0 12px; border:1px solid #c9dcfb; border-radius:8px; background:#fff; color:#1760e8; font-size:12px; font-weight:700; cursor:pointer; }.refresh-button { border-color:#d8e3f4; color:#1760e8; }
.state-card { padding:40px; background:#fff; border:1px solid #e2e9f4; border-radius:14px; }.summary-grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:12px; margin-bottom:14px; }.summary-card { display:flex; align-items:center; gap:12px; min-height:70px; padding:10px 13px; background:#fff; border:1px solid #e1e8f3; border-radius:12px; box-shadow:0 6px 18px rgba(35,68,116,.06); }.summary-icon { display:grid; place-items:center; width:36px; height:36px; border-radius:11px; background:#edf4ff; color:#1760e8; font-size:18px; }.summary-label { color:#718096; font-size:12px; }.summary-value { margin-top:3px; color:#153a7a; font-size:20px; font-weight:800; }
.accession-layout { display:grid; grid-template-columns:minmax(0,1fr) 270px; gap:14px; align-items:start; }.detail-column,.side-card { background:#fff; border:1px solid #e1e8f3; border-radius:13px; }.detail-column { overflow:hidden; }.section-tabs { display:flex; gap:26px; height:48px; padding:0 18px; align-items:center; border-bottom:1px solid #e8edf5; }.section-tabs button { height:48px; padding:0; border:0; border-bottom:3px solid transparent; background:transparent; color:#526079; font-size:13px; cursor:pointer; }.section-tabs button.active { color:#1760e8; border-bottom-color:#1760e8; font-weight:800; }.detail-section { padding:16px 18px 20px; }.detail-section h2,.side-card h2 { margin:0 0 14px; color:#1455c8; font-size:17px; }.detail-section h3 { margin:22px 0 12px; color:#1455c8; font-size:15px; }.section-title-row,.side-card-heading { display:flex; align-items:center; justify-content:space-between; }.table-loading { color:#718096; font-size:12px; }.basic-info-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); border:1px solid #e2e9f4; border-radius:10px; overflow:hidden; }.basic-info-row { display:grid; grid-template-columns:108px 1fr; min-height:42px; align-items:center; padding:0 12px; border-bottom:1px solid #e8edf5; }.basic-info-row:nth-child(odd) { border-right:1px solid #e8edf5; }.basic-info-row:nth-last-child(-n+1) { border-bottom:0; }.field-label { color:#718096; font-size:12px; }.field-value,.field-link { color:#18335f; font-size:13px; word-break:break-all; }.field-link { color:#1760e8; }.identifier-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }.identifier-card { min-height:72px; padding:12px; border:1px solid #dce7f5; border-radius:10px; background:#f9fbff; }.identifier-card span { display:block; color:#718096; font-size:12px; }.identifier-card strong { display:block; margin-top:8px; color:#1752ae; font-size:13px; overflow-wrap:anywhere; }
.table-shell { overflow-x:auto; border:1px solid #e2e9f4; border-radius:10px; }.detail-table { width:100%; border-collapse:collapse; min-width:720px; }.detail-table th,.detail-table td { padding:12px; border-bottom:1px solid #e8edf5; text-align:left; font-size:12px; }.detail-table th { background:#f1f6fd; color:#4b607e; white-space:nowrap; }.detail-table td { color:#1c3359; }.empty-table-cell { text-align:center !important; color:#8795ab !important; }.role-chip { padding:4px 8px; border-radius:999px; background:#f0ecff; color:#6a49c6; font-size:11px; }.download-action { background:#f7faff; }.pagination-note { margin-top:12px; color:#718096; font-size:12px; }
.side-column { display:grid; gap:14px; }.side-card { padding:15px; }.side-card-heading span { color:#7a89a0; font-size:10px; }.map-placeholder { display:grid; place-items:center; gap:7px; min-height:160px; border-radius:10px; background:linear-gradient(135deg,#eaf4ff,#f7fbff); color:#2a5b9e; }.map-pin { font-size:34px; color:#2777ef; }.map-placeholder small { color:#718096; }.structure-root { display:inline-block; padding:8px 12px; border:2px solid #2b73eb; border-radius:999px; color:#1752ae; font-size:12px; font-weight:800; }.structure-list { margin-top:14px; border-left:2px solid #d4e2f7; padding-left:12px; }.structure-assembly { display:grid; gap:7px; margin:12px 0; color:#294a78; font-size:12px; }.structure-assembly span { padding-left:10px; color:#718096; }.empty-structure { color:#8795ab; font-size:12px; }
@media (max-width:1100px) { .summary-grid { grid-template-columns:repeat(3,1fr); }.accession-layout { grid-template-columns:1fr; }.side-column { grid-template-columns:repeat(2,1fr); }.identifier-grid { grid-template-columns:repeat(2,1fr); } } @media (max-width:700px) { .summary-grid,.side-column,.basic-info-grid { grid-template-columns:1fr; }.basic-info-row:nth-child(odd) { border-right:0; }.section-tabs { overflow-x:auto; gap:18px; }.identifier-grid { grid-template-columns:1fr; } }
</style>

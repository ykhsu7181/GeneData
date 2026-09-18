<template>
  <div class="assembly-page">
    <div v-if="!assemblyId" class="page-state">
      <el-empty :description="$t('page.assemblyDetail.noAssemblySelected')" />
    </div>

    <div v-else-if="loading" class="page-state page-loading">
      <el-skeleton :rows="12" animated />
    </div>

    <div v-else-if="errorMessage" class="page-state">
      <el-result icon="warning" :title="errorMessage">
        <template #extra>
          <button class="secondary-button" type="button" @click="fetchDetail">
            <el-icon><Refresh /></el-icon>
            {{ $t('page.assemblyDetail.retry') }}
          </button>
        </template>
      </el-result>
    </div>

    <template v-else-if="detail">
      <header class="detail-header">
        <nav class="breadcrumb" :aria-label="$t('page.assembly.breadcrumbLabel')">
          <router-link :to="{ name: 'dashboard-home' }">{{ $t('nav.home') }}</router-link>
          <span aria-hidden="true">/</span>
          <router-link v-if="fromAccession" :to="{ name: 'accession-card' }">{{ $t('nav.accession') }}</router-link>
          <router-link v-else :to="{ name: 'assembly', query: assemblyPortalQuery }">{{ $t('page.assembly.title') }}</router-link>
          <span aria-hidden="true">/</span>
          <router-link :to="{ name: 'accession-card', query: accessionDetailQuery }">
            {{ assembly.accession || '-' }}
          </router-link>
          <span aria-hidden="true">/</span>
          <span>{{ assemblyDisplayName }}</span>
        </nav>

        <div class="heading-row">
          <div class="heading-main">
          <h1>{{ $t('page.assemblyDetail.title', { accession: assembly.accession || '-', assembly: assemblyDisplayName }) }}</h1>
            <div class="heading-tags">
              <span class="heading-tag species-tag">{{ $t('page.assemblyDetail.species', { value: speciesLabel }) }}</span>
              <span class="heading-tag population-tag">{{ $t('page.assemblyDetail.subPopulation', { value: detail.sub_population || '-' }) }}</span>
            </div>
          </div>
          <div class="heading-actions">
            <form class="detail-search" role="search" @submit.prevent="submitSearch">
              <label class="detail-search-field">
                <el-icon aria-hidden="true"><Search /></el-icon>
                <input
                  v-model="searchQuery"
                  type="search"
                  :aria-label="$t('page.assembly.searchTitle')"
                  :placeholder="$t('page.assembly.searchPlaceholder')"
                >
              </label>
              <button class="search-button" type="submit" :disabled="!searchQuery.trim() || searchLoading">
                {{ $t('common.search') }}
              </button>
            </form>
            <el-tooltip :content="$t('common.refresh')" placement="top">
              <el-button circle class="refresh-button" :aria-label="$t('common.refresh')" :loading="loading" @click="fetchDetail">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </header>

      <section class="content-card" aria-labelledby="basic-information-heading">
        <div class="card-heading card-heading-with-actions">
          <h2 id="basic-information-heading">{{ $t('page.assemblyDetail.basicInformation') }}</h2>
          <div class="header-actions">
            <button
              class="primary-button"
              type="button"
              :disabled="!detail.genome_download_url"
              @click="downloadGenome"
            >
              <el-icon><Download /></el-icon>
              {{ $t('page.assemblyDetail.download') }}
            </button>
            <button class="secondary-button" type="button" @click="openRelatedFiles">
              <el-icon><FolderOpened /></el-icon>
              {{ $t('page.assemblyDetail.relatedFiles') }}
            </button>
          </div>
        </div>
        <dl class="detail-grid">
          <template v-for="row in basicRows" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd>{{ displayValue(row.value) }}</dd>
          </template>
        </dl>
      </section>

      <section class="content-card" aria-labelledby="statistics-heading">
        <div class="card-heading">
          <h2 id="statistics-heading">{{ $t('page.assemblyDetail.statistics') }}</h2>
        </div>
        <dl class="detail-grid">
          <template v-for="row in statisticRows" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd>{{ displayValue(row.value) }}</dd>
          </template>
        </dl>
      </section>

      <section class="content-card" aria-labelledby="annotation-heading">
        <div class="card-heading">
          <h2 id="annotation-heading">{{ $t('page.assemblyDetail.annotation') }}</h2>
        </div>
        <AnnotationVersionTable
          :rows="annotations"
          :show-assembly="false"
          :show-default="true"
          :action-label="$t('page.assemblyDetail.viewFiles')"
          :default-column-label="$t('page.assemblyDetail.defaultColumn')"
          :default-yes-label="$t('page.assemblyDetail.yes')"
          :default-no-label="$t('page.assemblyDetail.no')"
          :empty-text="$t('page.assemblyDetail.emptyAnnotations')"
          @view-files="openAnnotationFiles"
        />
      </section>

      <section class="content-card" aria-labelledby="related-assemblies-heading">
        <div class="card-heading">
          <h2 id="related-assemblies-heading">{{ $t('page.assemblyDetail.relatedAssemblies') }}</h2>
        </div>
        <AssemblyVersionTable
          :rows="relatedAssemblies"
          :current-assembly-id="assembly.id"
          mode="revision"
          :action-label="$t('page.assemblyDetail.viewAssembly')"
          :current-label="$t('page.assemblyDetail.current')"
          :empty-text="$t('page.assemblyDetail.emptyAssemblies')"
          @select="selectAssembly"
        />
      </section>
    </template>

    <RelatedFilesDrawer
      v-model="drawerVisible"
      :title="drawerTitle"
      :loading="drawerLoading"
      :error-message="drawerErrorMessage"
      :files="displayedDrawerFiles"
      @download="downloadRelatedFile"
      @retry="loadRelatedFiles"
    />
  </div>
</template>

<script>
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Download, FolderOpened, Refresh, Search } from '@element-plus/icons-vue';
import AnnotationVersionTable from '@/components/accession/AnnotationVersionTable.vue';
import AssemblyVersionTable from '@/components/accession/AssemblyVersionTable.vue';
import RelatedFilesDrawer from '@/components/assembly/RelatedFilesDrawer.vue';

const firstQueryValue = (value) => (Array.isArray(value) ? value[0] : value);

const normalizeQueryText = (value) => {
  const normalized = value === null || value === undefined ? '' : String(value).trim();
  return normalized;
};

export default {
  name: 'AssemblyView',
  components: {
    AnnotationVersionTable,
    AssemblyVersionTable,
    RelatedFilesDrawer,
    Download,
    FolderOpened,
    Refresh,
    Search
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { t, locale } = useI18n();
    const loading = ref(false);
    const errorKey = ref('');
    const detail = ref(null);
    const drawerVisible = ref(false);
    const drawerLoading = ref(false);
    const drawerErrorKey = ref('');
    const drawerFiles = ref([]);
    const drawerScope = ref(null);
    const searchQuery = ref('');
    const searchLoading = ref(false);

    const assemblyId = computed(() => String(route.params.assemblyId || '').trim());
    const fromAccession = computed(() => (
      normalizeQueryText(firstQueryValue(route.query.from)).toLocaleLowerCase() === 'accession'
    ));
    const assemblyPortalQuery = computed(() => {
      const query = {};
      const search = normalizeQueryText(firstQueryValue(route.query.search || route.query.q));
      const page = Number(firstQueryValue(route.query.page) || 1);
      if (search) query.search = search;
      if (Number.isInteger(page) && page > 1) query.page = String(page);
      return query;
    });
    const assembly = computed(() => detail.value?.assembly || {});
    const accessionDetailQuery = computed(() => {
      const query = { accession: assembly.value.accession || '' };
      const returnTo = normalizeQueryText(firstQueryValue(route.query.return_to));
      if (fromAccession.value && returnTo) query.return_to = returnTo;
      return query;
    });
    const annotations = computed(() => detail.value?.annotations || []);
    const relatedAssemblies = computed(() => detail.value?.related_assemblies || []);
    const assemblyDisplayName = computed(() => (
      assembly.value.display_name || assembly.value.assembly_name || assembly.value.name || '-'
    ));
    const speciesLabel = computed(() => {
      const species = detail.value?.species;
      if (!species) return '-';
      const name = String(locale.value).startsWith('zh')
        ? species.chinese_name || species.common_name || species.species_code
        : species.common_name || species.species_code || species.chinese_name;
      if (!name) return species.scientific_name || '-';
      return species.scientific_name && species.scientific_name !== name
        ? `${name} (${species.scientific_name})`
        : name;
    });
    const errorMessage = computed(() => (errorKey.value ? t(errorKey.value) : ''));
    const drawerErrorMessage = computed(() => (drawerErrorKey.value ? t(drawerErrorKey.value) : ''));
    const drawerTitle = computed(() => (
      drawerScope.value
        ? t('page.assemblyDetail.annotationFilesTitle', { annotation: drawerScope.value.label || '-' })
        : t('page.assemblyDetail.drawerTitle', { accession: assembly.value.accession || '-' })
    ));
    const displayedDrawerFiles = computed(() => {
      if (!drawerScope.value) return drawerFiles.value;
      return drawerFiles.value.filter((item) => item.relations?.some((relation) => (
        relation.related_type === drawerScope.value.type
        && String(relation.related_id) === String(drawerScope.value.id)
      )));
    });

    const displayValue = (value) => (
      value === null || value === undefined || value === '' ? '-' : value
    );
    const formatBasePairs = (value) => {
      if (value === null || value === undefined || value === '') return '-';
      const number = Number(value);
      if (!Number.isFinite(number)) return value;
      if (number >= 1e9) return `${(number / 1e9).toFixed(2).replace(/\.00$/, '')} Gb`;
      if (number >= 1e6) return `${(number / 1e6).toFixed(2).replace(/\.00$/, '')} Mb`;
      if (number >= 1e3) return `${(number / 1e3).toFixed(2).replace(/\.00$/, '')} Kb`;
      return `${number.toLocaleString()} bp`;
    };
    const formatPercent = (value) => {
      if (value === null || value === undefined || value === '') return '-';
      return `${Number(value).toLocaleString()}%`;
    };

    const basicRows = computed(() => [
      { label: t('page.assemblyDetail.fields.assemblyAccession'), value: assembly.value.assembly_accession || assembly.value.standard_id },
      { label: t('page.assemblyDetail.fields.biosampleAccession'), value: assembly.value.biosample_accession },
      { label: t('page.assemblyDetail.fields.assemblyType'), value: assembly.value.assembly_type },
      { label: t('page.assemblyDetail.fields.assemblyMethod'), value: assembly.value.assembly_method },
      { label: t('page.assemblyDetail.fields.sequencingTechnology'), value: assembly.value.sequencing_technology },
      { label: t('page.assemblyDetail.fields.description'), value: assembly.value.description }
    ]);
    const statisticRows = computed(() => {
      const statistics = detail.value?.statistics || {};
      return [
        { label: t('page.assemblyDetail.statisticFields.genomeSize'), value: formatBasePairs(statistics.genome_size) },
        { label: t('page.assemblyDetail.statisticFields.assemblyLevel'), value: statistics.assembly_level },
        { label: t('page.assemblyDetail.statisticFields.chromosomeCount'), value: statistics.chromosome_count },
        { label: t('page.assemblyDetail.statisticFields.contigCount'), value: statistics.contig_count },
        { label: t('page.assemblyDetail.statisticFields.n50'), value: formatBasePairs(statistics.n50) },
        { label: t('page.assemblyDetail.statisticFields.gcContent'), value: formatPercent(statistics.gc_content) }
      ];
    });

    const fetchDetail = async () => {
      if (!assemblyId.value) {
        detail.value = null;
        errorKey.value = '';
        return;
      }
      loading.value = true;
      errorKey.value = '';
      detail.value = null;
      drawerVisible.value = false;
      try {
        const response = await axios.get(`/files/assemblies/${encodeURIComponent(assemblyId.value)}/summary/`);
        if (!response.data?.success) throw new Error('Assembly request failed');
        detail.value = response.data.data;
        searchQuery.value = detail.value?.assembly?.accession || '';
      } catch (error) {
        const status = error.response?.status;
        if (status === 403) errorKey.value = 'page.assemblyDetail.forbidden';
        else if (status === 404) errorKey.value = 'page.assemblyDetail.notFound';
        else if (status === 409) errorKey.value = 'page.assemblyDetail.conflict';
        else errorKey.value = 'page.assemblyDetail.loadFailed';
      } finally {
        loading.value = false;
      }
    };

    const normalizeApiUrl = (url) => {
      const value = String(url || '');
      return value.startsWith('/gd/api/') ? value.slice('/gd/api'.length) : value;
    };
    const loadRelatedFiles = async () => {
      const endpoint = normalizeApiUrl(detail.value?.related_files_url);
      if (!endpoint) {
        drawerFiles.value = [];
        drawerErrorKey.value = 'page.assemblyDetail.drawerLoadFailed';
        return;
      }
      drawerLoading.value = true;
      drawerErrorKey.value = '';
      try {
        const files = [];
        let page = 1;
        let total = 0;
        do {
          const response = await axios.get(endpoint, { params: { page, page_size: 100 } });
          if (!response.data?.success) throw new Error('Related files request failed');
          const pageData = response.data.data || {};
          const results = pageData.results || [];
          files.push(...results);
          total = Number(pageData.pagination?.total || files.length);
          page += 1;
          if (!results.length) break;
        } while (files.length < total);
        drawerFiles.value = files;
      } catch {
        drawerFiles.value = [];
        drawerErrorKey.value = 'page.assemblyDetail.drawerLoadFailed';
      } finally {
        drawerLoading.value = false;
      }
    };
    const openRelatedFiles = async () => {
      drawerScope.value = null;
      drawerVisible.value = true;
      await loadRelatedFiles();
    };
    const openAnnotationFiles = async (annotation) => {
      drawerScope.value = {
        type: 'annotation',
        id: annotation.id,
        label: annotation.display_name || annotation.annotation_name || annotation.name
      };
      drawerVisible.value = true;
      await loadRelatedFiles();
    };
    const openDownload = (url, missingKey) => {
      if (!url) {
        ElMessage.error(t(missingKey));
        return;
      }
      window.open(new URL(url, window.location.origin).toString(), '_blank');
    };
    const downloadGenome = () => openDownload(
      detail.value?.genome_download_url,
      'page.assemblyDetail.noGenomeFile'
    );
    const downloadRelatedFile = (file) => openDownload(
      file?.datafile_download_url,
      'messages.missingDatafileUrl'
    );
    const selectAssembly = (item) => router.push({
      name: 'assembly-detail',
      params: { assemblyId: item.id },
      query: route.query
    });

    const submitSearch = async () => {
      const keyword = searchQuery.value.trim();
      if (!keyword || searchLoading.value) return;
      searchLoading.value = true;
      try {
        const response = await axios.get('/files/assemblies/', {
          params: { search: keyword, page: 1, page_size: 20 }
        });
        const results = Array.isArray(response.data?.results) ? response.data.results : [];
        const normalizedKeyword = keyword.toLocaleLowerCase();
        const exactMatch = results.find((item) => [
          item.accession,
          item.assembly,
          item.assembly_accession
        ].some((value) => String(value || '').trim().toLocaleLowerCase() === normalizedKeyword));
        const target = exactMatch || results[0];
        if (!target?.id) {
          ElMessage.warning(t('page.assembly.noResults'));
          return;
        }
        await router.push({
          name: 'assembly-detail',
          params: { assemblyId: target.id },
          query: route.query
        });
      } catch {
        ElMessage.error(t('page.assembly.loadFailed'));
      } finally {
        searchLoading.value = false;
      }
    };

    watch(assemblyId, fetchDetail, { immediate: true });

    return {
      assemblyId,
      accessionDetailQuery,
      assemblyPortalQuery,
      loading,
      errorMessage,
      detail,
      assembly,
      annotations,
      relatedAssemblies,
      assemblyDisplayName,
      speciesLabel,
      basicRows,
      statisticRows,
      drawerVisible,
      drawerLoading,
      drawerErrorMessage,
      drawerTitle,
      displayedDrawerFiles,
      displayValue,
      fetchDetail,
      fromAccession,
      openRelatedFiles,
      openAnnotationFiles,
      loadRelatedFiles,
      downloadGenome,
      downloadRelatedFile,
      selectAssembly,
      searchQuery,
      searchLoading,
      submitSearch
    };
  }
};
</script>

<style scoped>
.assembly-page { width:100%; margin:0; padding:8px 0 36px; box-sizing:border-box; color:#15233d; }
.detail-header { margin-bottom:16px; padding:16px 20px 18px; background:#fff; border:1px solid #e1e8f3; border-radius:13px; box-shadow:0 6px 18px rgba(35,68,116,.05); }
.breadcrumb { display:flex; gap:8px; align-items:center; margin-bottom:14px; color:#76849a; font-size:13px; }
.breadcrumb a { color:#3974c7; text-decoration:none; }
.breadcrumb a:hover,.breadcrumb a:focus-visible { color:#086cde; text-decoration:underline; }
.heading-row { display:flex; align-items:center; justify-content:space-between; gap:18px; }
.heading-main { display:flex; align-items:center; flex-wrap:wrap; gap:12px; min-width:0; }
.detail-header h1 { margin:0 6px 0 0; color:#102c5d; font-size:30px; line-height:1.2; }
.heading-tags { display:flex; flex-wrap:wrap; gap:8px; }
.heading-tag { padding:5px 12px; border-radius:999px; font-size:12px; font-weight:700; white-space:nowrap; }
.species-tag { color:#1c5bc5; background:#eaf2ff; border:1px solid #cfe0ff; }
.population-tag { color:#327b46; background:#eaf8ed; border:1px solid #ccebd3; }
.heading-actions { display:flex; align-items:center; gap:10px; margin-left:auto; flex:0 1 520px; justify-content:flex-end; }
.detail-search { display:grid; grid-template-columns:minmax(180px, 1fr) 72px; flex:1; max-width:430px; }
.detail-search-field { display:flex; align-items:center; gap:9px; min-width:0; height:38px; padding:0 12px; border:1px solid #cfdef0; border-right:0; border-radius:8px 0 0 8px; background:#fff; color:#71829d; box-sizing:border-box; }
.detail-search-field:focus-within { border-color:#4c9df3; box-shadow:0 0 0 2px rgba(47,136,255,.1); }
.detail-search-field input { width:100%; min-width:0; border:0; outline:0; color:#18345f; background:transparent; font:inherit; font-size:13px; }
.search-button { min-height:38px; border:0; border-radius:0 8px 8px 0; color:#fff; background:linear-gradient(180deg,#2e91f5,#0b71df); font:inherit; font-size:13px; font-weight:700; cursor:pointer; }
.search-button:disabled { cursor:not-allowed; opacity:1; }
.refresh-button { flex:0 0 auto; }
.content-card { margin-top:16px; padding:18px 20px 20px; border:1px solid #dce7f5; border-radius:12px; background:#fff; box-shadow:0 7px 22px rgba(37, 75, 122, 0.05); }
.card-heading { display:flex; align-items:center; min-height:34px; padding-bottom:12px; }
.card-heading-with-actions { justify-content:space-between; gap:16px; }
.card-heading h2 { margin:0; color:#1671dc; font-size:19px; }
.header-actions { display:flex; gap:10px; flex-wrap:wrap; }
.primary-button,.secondary-button { display:inline-flex; min-height:36px; padding:0 15px; border-radius:8px; align-items:center; justify-content:center; gap:7px; font-size:13px; font-weight:700; cursor:pointer; }
.primary-button { border:1px solid #1677ed; color:#fff; background:#1677ed; }
.secondary-button { border:1px solid #bcd5fb; color:#1768cf; background:#fff; }
.primary-button:disabled { border-color:#cbd6e4; color:#8391a5; background:#eef2f6; cursor:not-allowed; }
.detail-grid { display:grid; grid-template-columns:minmax(190px, 34%) 1fr; margin:0; border-top:1px solid #e3eaf4; }
.detail-grid dt,.detail-grid dd { min-height:38px; margin:0; padding:10px 12px; border-bottom:1px solid #e3eaf4; box-sizing:border-box; font-size:13px; line-height:1.45; }
.detail-grid dt { color:#506789; }
.detail-grid dd { color:#183a70; overflow-wrap:anywhere; }
.page-state { min-height:520px; display:grid; place-items:center; }
.page-loading { display:block; padding:80px 0; }
@media (max-width: 700px) {
  .assembly-page { padding:8px 0 34px; }
  .detail-header { padding:14px; }
  .heading-row { align-items:flex-start; flex-direction:column; }
  .detail-header h1 { font-size:26px; }
  .heading-actions { width:100%; flex-basis:auto; margin-left:0; }
  .detail-search { max-width:none; }
  .card-heading-with-actions { align-items:flex-start; flex-direction:column; }
  .header-actions { width:100%; }
  .primary-button,.secondary-button { flex:1; }
  .detail-grid { grid-template-columns:1fr; }
  .detail-grid dt { min-height:auto; padding-bottom:3px; border-bottom:0; font-weight:700; }
  .detail-grid dd { padding-top:3px; }
}
</style>

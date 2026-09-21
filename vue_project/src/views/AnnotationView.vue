<template>
  <div class="annotation-view">
    <section class="annotation-hero">
      <nav class="breadcrumb" :aria-label="$t('page.annotation.breadcrumbLabel')">
        <RouterLink to="/dashboard">{{ $t('nav.home') }}</RouterLink>
        <span aria-hidden="true">/</span>
        <button v-if="annotationReturnPath" type="button" @click="returnToAssembly">
          {{ $t('page.annotation.assembly') }}
        </button>
        <span v-if="annotationReturnPath" aria-hidden="true">/</span>
        <span>{{ $t('page.annotation.title') }}</span>
      </nav>
      <h1 id="annotation-page-title">{{ $t('page.annotation.title') }}</h1>
    </section>

    <AnnotationSearchPanel
      :accession="selectedOrganism"
      :assembly-id="selectedAssemblyId"
      :annotation-id="selectedAnnotationId"
      :chromosome="selectedChromosome"
      :feature-type="selectedFeatureType"
      :view-mode="viewMode"
      :assembly-options="assemblyOptions"
      :annotation-options="annotationOptions"
      :chromosome-options="chromosomeOptions"
      :feature-type-options="featureTypeOptions"
      :loading="loading"
      :loading-organisms="loadingOrganisms"
      :loading-hierarchy="loadingHierarchy"
      :loading-options="loadingOptions"
      :fetch-suggestions="queryAccessionSuggestions"
      :assembly-label="getAssemblyLabel"
      :annotation-label="getAnnotationLabel"
      @update:accession="selectedOrganism = $event"
      @accession-input="handleAccessionInput"
      @accession-select="handleAccessionSelect"
      @clear-accession="handleOrganismChange('')"
      @assembly-change="handleAssemblyChange"
      @annotation-change="handleAnnotationChange"
      @chromosome-change="handleChromosomeChange"
      @feature-change="handleFeatureTypeChange"
      @search="handleAccessionSearch"
      @reset="resetAnnotationFilters"
      @view-change="handleViewModeChange"
    />

    <AnnotationSummaryBar :summary="annotationStatistics" :loading="loadingOptions" />

    <div
      class="data-card"
      role="region"
      :aria-label="$t('page.annotation.resultsRegionLabel')"
      :aria-busy="String(loading || loadingAnnotation || loadingVisualization)"
    >
      <div class="data-card-header">
        <h2 id="annotation-results-title">
          <el-icon aria-hidden="true"><Collection /></el-icon>
          {{ $t(viewMode === 'chart' ? 'page.annotation.chartTitle' : 'page.annotation.tableTitle') }}
        </h2>
        <div class="data-card-actions">
          <span aria-live="polite">
            {{ $t('page.annotation.resultCount', { count: displayedResultCount }) }}
          </span>
          <el-tooltip :content="$t('page.annotation.refreshData')" placement="top">
            <el-button circle :aria-label="$t('page.annotation.refreshData')" @click="fetchFiles" :loading="loading">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </div>
      <div v-if="loading" class="loading" role="status" aria-live="polite">
        <span class="sr-only">{{ $t('page.annotation.loadingData') }}</span>
        <el-skeleton :rows="6" animated aria-hidden="true" />
      </div>

      <div v-else-if="contextErrorKey" class="context-error" role="alert">
        <el-result icon="warning" :title="$t(contextErrorKey)">
          <template #extra>
            <el-button v-if="annotationReturnPath" @click="returnToAssembly">
              {{ $t('page.annotation.backToAssembly') }}
            </el-button>
            <el-button type="primary" @click="useDefaultAnnotation">
              {{ $t('page.annotation.viewDefaultAnnotation') }}
            </el-button>
          </template>
        </el-result>
      </div>

      <div v-else-if="!selectedOrganism" class="empty-state" role="status">
        <el-empty :description="$t('page.annotation.selectOrganismPrompt')" />
      </div>

      <div v-else class="content-container">
        <div v-if="viewMode === 'table' && dataErrorKey" class="data-error" role="alert">
          <span>{{ $t(dataErrorKey) }}</span>
          <el-button type="primary" plain @click="fetchAnnotationData">
            {{ $t('page.annotation.retryData') }}
          </el-button>
        </div>

        <!-- 表格模式 -->
        <div v-if="viewMode === 'table'" class="annotation-table">
          <el-table
            :data="annotationData"
            v-loading="loadingAnnotation"
            stripe
            border
            height="600"
            style="width: 100%"
            :aria-label="$t('page.annotation.tableTitle')"
            :empty-text="$t('page.annotation.empty')"
          >
            <el-table-column prop="seqid" :label="$t('page.annotation.chromosome')" width="120" />
            <el-table-column prop="feature" :label="$t('page.annotation.feature')" width="100" />
            <el-table-column prop="start" :label="$t('page.annotation.start')" width="100" sortable />
            <el-table-column prop="end" :label="$t('page.annotation.end')" width="100" sortable />
            <el-table-column prop="length" :label="$t('page.annotation.length')" width="100" sortable />
            <el-table-column prop="strand" :label="$t('page.annotation.strand')" width="80" />
            <el-table-column prop="source" :label="$t('page.annotation.source')" width="100" />
            <el-table-column prop="score" :label="$t('page.annotation.score')" width="80" />
            <el-table-column :label="$t('page.annotation.attributes')" min-width="300">
              <template #default="scope">
                <div class="attributes-container">
                  <div v-for="(value, key) in scope.row.attributes" :key="key" class="attribute-item">
                    <span class="attr-key">{{ key }}:</span>
                    <span class="attr-value">{{ value }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div class="pagination-container">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[20, 50, 100, 200]"
              :total="totalCount"
              :aria-label="$t('page.annotation.paginationLabel')"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
            />
          </div>
        </div>

        <!-- 图形模式 -->
        <div v-else-if="viewMode === 'chart'" class="annotation-visualization">
          <div v-if="loadingVisualization" class="loading-visualization" role="status" aria-live="polite">
            <div class="loading-content">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>{{ $t('page.annotation.loadingVisualization') }}</span>
            </div>
          </div>
          <div v-else-if="visualizationErrorKey" class="data-error" role="alert">
            <span>{{ $t(visualizationErrorKey) }}</span>
            <el-button type="primary" plain @click="fetchVisualizationData">
              {{ $t('page.annotation.retryData') }}
            </el-button>
          </div>
          <div v-else-if="!selectedOrganism || !selectedChromosome" class="empty-state" role="status">
            <el-empty :description="$t('page.annotation.selectVisualization')" />
          </div>
          <div v-else class="chart-content">
            <!-- 可视化控制面板 -->
            <div class="visualization-controls">
              <div class="control-group">
                <span class="control-label">{{ $t('page.annotation.displayFeatureTypes') }}</span>
                <el-checkbox-group
                  v-model="displayFeatures"
                  class="feature-checkboxes"
                  :aria-label="$t('page.annotation.featureControlsLabel')"
                  @change="updateVisualization"
                >
                  <el-checkbox label="gene" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('gene') }"></span>
                    {{ $t('page.annotation.gene') }}
                  </el-checkbox>
                  <el-checkbox label="mRNA" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('mRNA') }"></span>
                    mRNA
                  </el-checkbox>
                  <el-checkbox label="CDS" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('CDS') }"></span>
                    {{ $t('page.annotation.codingSequence') }}
                  </el-checkbox>
                  <el-checkbox label="exon" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('exon') }"></span>
                    {{ $t('page.annotation.exon') }}
                  </el-checkbox>
                  <el-checkbox label="five_prime_UTR" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('five_prime_UTR') }"></span>
                    5'UTR
                  </el-checkbox>
                  <el-checkbox label="three_prime_UTR" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('three_prime_UTR') }"></span>
                    3'UTR
                  </el-checkbox>
                </el-checkbox-group>
              </div>
              <div class="control-group">
                <span class="control-label">
                  {{ $t('page.annotation.rowLength', { unit: segmentLengthUnit }) }}
                </span>
                <div class="segment-length-controls">
                  <el-button
                    size="small"
                    @mousedown="startDecrease"
                    @mouseup="stopChange"
                    @mouseleave="stopChange"
                    @touchstart="startDecrease"
                    @touchend="stopChange"
                    class="fast-control-btn"
                    :aria-label="$t('page.annotation.decreaseRowLength')"
                  >
                    -
                  </el-button>
                  <el-input
                    v-model.number="segmentLengthDisplay"
                    type="number"
                    :min="segmentLengthMin"
                    :max="segmentLengthMax"
                    :step="segmentLengthStep"
                    size="small"
                    @change="handleSegmentLengthChange"
                    @blur="validateInput"
                    class="segment-input"
                    :aria-label="$t('page.annotation.rowLengthInputLabel', { unit: segmentLengthUnit })"
                  />
                  <el-button
                    size="small"
                    @mousedown="startIncrease"
                    @mouseup="stopChange"
                    @mouseleave="stopChange"
                    @touchstart="startIncrease"
                    @touchend="stopChange"
                    class="fast-control-btn"
                    :aria-label="$t('page.annotation.increaseRowLength')"
                  >
                    +
                  </el-button>
                  <el-button
                    size="small"
                    type="default"
                    @click="resetSegmentLength"
                    class="reset-button"
                  >
                    {{ segmentLengthResetLabel }}
                  </el-button>
                </div>
              </div>
            </div>

            <!-- 可视化容器 -->
            <div
              ref="annotationContainer"
              class="annotation-container"
              role="img"
              :aria-label="$t('page.annotation.visualizationLabel')"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onBeforeUnmount, watch, nextTick, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { Collection, Refresh, Loading } from '@element-plus/icons-vue';
import axios from 'axios';
import * as d3 from 'd3';
import { useI18n } from 'vue-i18n';
import AnnotationSearchPanel from '@/components/annotation/AnnotationSearchPanel.vue';
import AnnotationSummaryBar from '@/components/annotation/AnnotationSummaryBar.vue';

const normalizeQueryValue = (value) => {
  if (Array.isArray(value)) {
    return value[0] || '';
  }
  return value ? String(value).trim() : '';
};

const matchesId = (item, value) => {
  if (!item || value === null || value === undefined || value === '') {
    return false;
  }
  return String(item.id) === String(value);
};

const ANNOTATION_PAGE_SIZES = [20, 50, 100, 200];

const normalizePositiveInteger = (value, fallback) => {
  const parsed = Number.parseInt(normalizeQueryValue(value), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
};

const normalizePageSize = value => {
  const parsed = normalizePositiveInteger(value, 50);
  return ANNOTATION_PAGE_SIZES.includes(parsed) ? parsed : 50;
};

const normalizeViewMode = value => (normalizeQueryValue(value) === 'chart' ? 'chart' : 'table');

const getSegmentLengthStepBp = (chromosomeLength) => {
  const length = Number(chromosomeLength);
  if (!Number.isFinite(length) || length <= 0 || length >= 1000000) return 10000;
  return 10 ** Math.max(0, Math.floor(Math.log10(length)) - 1);
};

const getDefaultSegmentLengthBp = (chromosomeLength) => {
  const length = Number(chromosomeLength);
  if (!Number.isFinite(length) || length <= 0 || length >= 1000000) return 1000000;
  const step = getSegmentLengthStepBp(length);
  return Math.ceil(length / step) * step;
};

const isCanceledRequest = error => (
  error?.code === 'ERR_CANCELED'
  || error?.name === 'CanceledError'
  || axios.isCancel?.(error)
);

const normalizeAssemblyReturnPath = (value) => {
  const normalized = normalizeQueryValue(value);
  if (!normalized || normalized.startsWith('//')) return '';
  return /^\/assembly\/[^/?#]+(?:[/?#]|$)/.test(normalized) ? normalized : '';
};

export default {
  name: 'AnnotationView',
  components: {
    AnnotationSearchPanel,
    AnnotationSummaryBar,
    Collection,
    Refresh,
    Loading
  },
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();
    const loading = ref(true);
    const loadingOrganisms = ref(false);
    const loadingAnnotation = ref(false);
    const loadingHierarchy = ref(false);
    const loadingOptions = ref(false);
    const draftQuery = reactive({
      accession: '',
      assemblyId: '',
      annotationId: '',
      chromosome: '',
      featureType: 'all'
    });
    const appliedQuery = reactive({
      accession: '',
      assemblyId: '',
      annotationId: '',
      chromosome: '',
      featureType: 'all'
    });
    const selectedOrganism = computed({
      get: () => draftQuery.accession,
      set: (value) => { draftQuery.accession = value || ''; }
    });
    const selectedAssemblyId = computed({
      get: () => draftQuery.assemblyId,
      set: (value) => { draftQuery.assemblyId = value ? String(value) : ''; }
    });
    const selectedAnnotationId = computed({
      get: () => draftQuery.annotationId,
      set: (value) => { draftQuery.annotationId = value ? String(value) : ''; }
    });
    const selectedChromosome = computed({
      get: () => draftQuery.chromosome,
      set: (value) => { draftQuery.chromosome = value || ''; }
    });
    const selectedFeatureType = computed({
      get: () => draftQuery.featureType,
      set: (value) => { draftQuery.featureType = value || 'all'; }
    });
    const allOrganisms = ref([]);
    const organismOptions = ref([]);
    const assemblyOptions = ref([]);
    const annotationOptions = ref([]);
    const chromosomeOptions = ref([]);
    const featureTypeOptions = ref(['all']);
    const annotationData = ref([]);
    const annotationStatistics = ref(null);
    const dataErrorKey = ref('');
    const visualizationErrorKey = ref('');
    const loadedOptionsAnnotationId = ref('');
    const optionsRequestToken = ref(0);
    const currentPage = ref(1);
    const pageSize = ref(50);
    const totalCount = ref(0);
    let componentDisposed = false;
    let routeRequestToken = 0;
    let organismsController = null;
    let hierarchyController = null;
    let optionsController = null;
    let annotationDataController = null;
    let visualizationController = null;
    let segmentLengthContextKey = '';

    const replaceRequestController = (currentController) => {
      currentController?.abort();
      return new AbortController();
    };

    // 可视化相关数据
    const viewMode = ref('table'); // 'table' 或 'chart'
    const loadingVisualization = ref(false);
    const annotationContainer = ref(null);
    const displayFeatures = ref([
      'gene',
      'mRNA',
      'CDS',
      'exon',
      'five_prime_UTR',
      'three_prime_UTR'
    ]);
    const segmentLength = ref(1000000); // 默认1.0Mb
    const chromosomeLength = ref(0);
    const visualizationData = ref([]);
    const displayedResultCount = computed(() => (
      viewMode.value === 'chart' ? visualizationData.value.length : totalCount.value
    ));
    const contextAccession = computed({
      get: () => appliedQuery.accession,
      set: (value) => { appliedQuery.accession = value || ''; }
    });
    const contextAssemblyId = computed({
      get: () => appliedQuery.assemblyId,
      set: (value) => { appliedQuery.assemblyId = value ? String(value) : ''; }
    });
    const contextAnnotationId = computed({
      get: () => appliedQuery.annotationId,
      set: (value) => { appliedQuery.annotationId = value ? String(value) : ''; }
    });
    const hierarchyAssemblies = ref([]);
    const loadedHierarchyAccession = ref('');
    const routeSyncInProgress = ref(false);
    const hierarchyLoadFailed = ref(false);
    const contextErrorKey = ref('');
    const annotationReturnPath = computed(() => (
      normalizeQueryValue(route.query.from) === 'assembly'
        ? normalizeAssemblyReturnPath(route.query.return_to)
        : ''
    ));

    const segmentLengthUnit = computed(() => {
      if (chromosomeLength.value > 0 && chromosomeLength.value < 1000) return 'bp';
      if (chromosomeLength.value > 0 && chromosomeLength.value < 1000000) return 'kb';
      return 'Mb';
    });
    const segmentLengthDivisor = computed(() => (
      segmentLengthUnit.value === 'bp' ? 1 : segmentLengthUnit.value === 'kb' ? 1000 : 1000000
    ));
    const segmentLengthStep = computed(() => (
      getSegmentLengthStepBp(chromosomeLength.value) / segmentLengthDivisor.value
    ));
    const segmentLengthMin = computed(() => segmentLengthStep.value);
    const segmentLengthMax = computed(() => {
      if (segmentLengthUnit.value === 'Mb') return 50;
      return Math.max(segmentLengthDisplay.value * 2, segmentLengthStep.value);
    });
    const segmentLengthDisplay = computed({
      get: () => {
        const value = segmentLength.value / segmentLengthDivisor.value;
        return segmentLengthUnit.value === 'bp'
          ? Math.round(value)
          : Math.round(value * 100) / 100;
      },
      set: (value) => {
        segmentLength.value = Math.max(1, Math.round(value * segmentLengthDivisor.value));
      }
    });
    const segmentLengthResetLabel = computed(() => (
      chromosomeLength.value > 0 && chromosomeLength.value < 1000000
        ? t('page.annotation.fitSequence')
        : t('page.annotation.resetOneMb')
    ));

    const initializeSegmentLength = (length) => {
      const contextKey = `${contextAnnotationId.value}:${selectedChromosome.value}`;
      if (segmentLengthContextKey === contextKey) return;
      segmentLength.value = getDefaultSegmentLengthBp(length);
      segmentLengthContextKey = contextKey;
    };

    const buildNormalizedQuery = ({
      accession,
      assembly,
      annotation,
      chromosome,
      featureType,
      view,
      page,
      pageSize: queryPageSize,
      from,
      returnTo
    }) => {
      const query = {};
      if (accession) {
        query.accession = accession;
      }
      if (assembly) {
        query.assembly = String(assembly);
      }
      if (annotation) {
        query.annotation = String(annotation);
      }
      if (chromosome) {
        query.chromosome = chromosome;
      }
      if (featureType && featureType !== 'all') {
        query.feature = featureType;
      }
      if (view === 'chart') {
        query.view = 'chart';
      }
      if (Number(page) > 1) {
        query.page = String(page);
      }
      if (Number(queryPageSize) !== 50 && ANNOTATION_PAGE_SIZES.includes(Number(queryPageSize))) {
        query.page_size = String(queryPageSize);
      }
      if (from === 'assembly') {
        query.from = 'assembly';
      }
      const safeReturnPath = normalizeAssemblyReturnPath(returnTo);
      if (safeReturnPath) {
        query.return_to = safeReturnPath;
      }
      return query;
    };

    const queryKeys = [
      'accession', 'assembly', 'annotation', 'chromosome', 'feature',
      'view', 'page', 'page_size', 'from', 'return_to'
    ];

    const routeQueryMatches = query => (
      !normalizeQueryValue(route.query.organism)
      && queryKeys.every(key => normalizeQueryValue(route.query[key]) === normalizeQueryValue(query[key]))
      && Object.keys(route.query).every(key => queryKeys.includes(key) || !normalizeQueryValue(route.query[key]))
    );

    const writeRouteQuery = async (query, { replace = true } = {}) => {
      if (routeQueryMatches(query)) return false;

      routeSyncInProgress.value = true;
      try {
        await router[replace ? 'replace' : 'push']({
          path: route.path,
          query
        });
      } finally {
        routeSyncInProgress.value = false;
      }
      return true;
    };

    const replaceRouteQuery = query => writeRouteQuery(query, { replace: true });
    const pushRouteQuery = query => writeRouteQuery(query, { replace: false });

    const buildCurrentRouteQuery = (overrides = {}) => buildNormalizedQuery({
      accession: selectedOrganism.value,
      assembly: selectedAssemblyId.value,
      annotation: selectedAnnotationId.value,
      chromosome: selectedChromosome.value,
      featureType: selectedFeatureType.value,
      view: viewMode.value,
      page: currentPage.value,
      pageSize: pageSize.value,
      from: normalizeQueryValue(route.query.from),
      returnTo: route.query.return_to,
      ...overrides
    });

    const buildAnnotationContextParams = ({ featureType = null, chromosome = null, page = null, pageSizeValue = null, includeOrganismFallback = false } = {}) => {
      const params = {};

      if (contextAnnotationId.value) {
        params.annotation_id = contextAnnotationId.value;
      }
      if (contextAssemblyId.value) {
        params.assembly_id = contextAssemblyId.value;
      }
      if (contextAccession.value) {
        params.accession = contextAccession.value;
      }
      if (!contextAnnotationId.value && !contextAssemblyId.value && selectedOrganism.value) {
        params.organism = selectedOrganism.value;
      } else if (includeOrganismFallback && selectedOrganism.value) {
        params.organism = selectedOrganism.value;
      }
      if (chromosome) {
        params.chromosome = chromosome;
      }
      if (featureType) {
        params.feature_type = featureType;
      }
      if (page !== null) {
        params.page = page;
      }
      if (pageSizeValue !== null) {
        params.page_size = pageSizeValue;
      }

      return params;
    };

    const fetchAccessionHierarchy = async (accession) => {
      hierarchyController?.abort();
      if (!accession) {
        hierarchyAssemblies.value = [];
        assemblyOptions.value = [];
        annotationOptions.value = [];
        loadedHierarchyAccession.value = '';
        hierarchyLoadFailed.value = false;
        return true;
      }

      if (loadedHierarchyAccession.value === accession && hierarchyAssemblies.value.length) {
        assemblyOptions.value = hierarchyAssemblies.value;
        hierarchyLoadFailed.value = false;
        return true;
      }

      const controller = new AbortController();
      hierarchyController = controller;
      hierarchyLoadFailed.value = false;
      loadingHierarchy.value = true;
      try {
        const response = await axios.get(`/files/accessions/${accession}/`, {
          signal: controller.signal
        });
        if (componentDisposed || controller.signal.aborted) return false;
        hierarchyAssemblies.value = response.data?.data?.assemblies || [];
        assemblyOptions.value = hierarchyAssemblies.value;
        loadedHierarchyAccession.value = accession;
        return true;
      } catch (error) {
        if (isCanceledRequest(error) || controller.signal.aborted) return false;
        console.error('获取 accession hierarchy 失败:', error);
        hierarchyAssemblies.value = [];
        assemblyOptions.value = [];
        annotationOptions.value = [];
        loadedHierarchyAccession.value = accession;
        hierarchyLoadFailed.value = true;
        return false;
      } finally {
        if (hierarchyController === controller) {
          loadingHierarchy.value = false;
          hierarchyController = null;
        }
      }
    };

    const pickAssembly = (requestedAssemblyId) => {
      if (!hierarchyAssemblies.value.length) {
        return null;
      }

      if (requestedAssemblyId) {
        return hierarchyAssemblies.value.find((item) => matchesId(item, requestedAssemblyId)) || null;
      }
      return hierarchyAssemblies.value.find((item) => item.is_default) || hierarchyAssemblies.value[0];
    };

    const pickAnnotation = (assembly, requestedAnnotationId) => {
      if (!assembly?.annotations?.length) {
        return null;
      }

      if (requestedAnnotationId) {
        return assembly.annotations.find((item) => matchesId(item, requestedAnnotationId)) || null;
      }
      return assembly.annotations.find((item) => item.is_default) || assembly.annotations[0];
    };

    const getAssemblyLabel = (assembly) => (
      assembly?.display_name || assembly?.assembly_name || assembly?.name || '-'
    );

    const getAnnotationLabel = (annotation) => (
      annotation?.display_name || annotation?.annotation_name || annotation?.name || '-'
    );

    const updateAnnotationOptions = (assembly) => {
      annotationOptions.value = Array.isArray(assembly?.annotations) ? assembly.annotations : [];
    };

    // 获取有注释文件的生物体列表
    const fetchOrganisms = async () => {
      organismsController = replaceRequestController(organismsController);
      const controller = organismsController;
      try {
        loadingOrganisms.value = true;
        const response = await axios.get('/files/query/annotation-organisms/', {
          signal: controller.signal
        });
        if (componentDisposed || controller.signal.aborted) return;
        allOrganisms.value = response.data || [];
        organismOptions.value = allOrganisms.value;
      } catch (error) {
        if (isCanceledRequest(error) || controller.signal.aborted) return;
        console.error('获取有注释文件的生物体列表失败:', error);
        ElMessage.error(t('page.annotation.organismLoadFailed'));
      } finally {
        if (organismsController === controller) {
          loadingOrganisms.value = false;
          organismsController = null;
        }
      }
    };

    const fetchAnnotationOptions = async ({ force = false } = {}) => {
      const annotationId = contextAnnotationId.value;
      if (!annotationId) {
        optionsController?.abort();
        optionsController = null;
        loadingOptions.value = false;
        optionsRequestToken.value += 1;
        loadedOptionsAnnotationId.value = '';
        chromosomeOptions.value = [];
        featureTypeOptions.value = ['all'];
        annotationStatistics.value = null;
        return false;
      }
      if (
        !force
        && loadedOptionsAnnotationId.value === annotationId
        && annotationStatistics.value
      ) {
        return true;
      }

      const requestToken = optionsRequestToken.value + 1;
      optionsRequestToken.value = requestToken;
      optionsController = replaceRequestController(optionsController);
      const controller = optionsController;
      loadingOptions.value = true;
      try {
        const response = await axios.get('/files/query/annotation-options/', {
          params: buildAnnotationContextParams(),
          signal: controller.signal
        });
        if (
          componentDisposed
          || controller.signal.aborted
          || requestToken !== optionsRequestToken.value
          || contextAnnotationId.value !== annotationId
        ) {
          return false;
        }
        const data = response.data || {};
        chromosomeOptions.value = Array.isArray(data.chromosomes) ? data.chromosomes : [];
        featureTypeOptions.value = [
          'all',
          ...(Array.isArray(data.feature_types) ? data.feature_types : [])
        ];
        annotationStatistics.value = data.summary || null;
        loadedOptionsAnnotationId.value = annotationId;
        if (
          selectedChromosome.value
          && !chromosomeOptions.value.includes(selectedChromosome.value)
        ) {
          selectedChromosome.value = '';
        }
        if (
          selectedFeatureType.value !== 'all'
          && !featureTypeOptions.value.includes(selectedFeatureType.value)
        ) {
          selectedFeatureType.value = 'all';
        }
        return true;
      } catch (error) {
        if (isCanceledRequest(error) || controller.signal.aborted) return false;
        if (requestToken !== optionsRequestToken.value) return false;
        console.error('获取 Annotation 筛选元数据失败:', error);
        loadedOptionsAnnotationId.value = '';
        chromosomeOptions.value = [];
        featureTypeOptions.value = ['all'];
        annotationStatistics.value = null;
        ElMessage.error(t('page.annotation.optionsLoadFailed'));
        return false;
      } finally {
        if (requestToken === optionsRequestToken.value && optionsController === controller) {
          loadingOptions.value = false;
          optionsController = null;
        }
      }
    };

    // 获取注释数据
    const fetchAnnotationData = async () => {
      if (!selectedOrganism.value) {
        annotationDataController?.abort();
        annotationDataController = null;
        loadingAnnotation.value = false;
        return;
      }

      annotationDataController = replaceRequestController(annotationDataController);
      const controller = annotationDataController;
      try {
        loadingAnnotation.value = true;
        dataErrorKey.value = '';
        appliedQuery.chromosome = selectedChromosome.value;
        appliedQuery.featureType = selectedFeatureType.value;

        const params = buildAnnotationContextParams({
          featureType: appliedQuery.featureType,
          chromosome: appliedQuery.chromosome || null,
          page: currentPage.value,
          pageSizeValue: pageSize.value
        });

        const response = await axios.get('/files/query/annotation-data/', {
          params,
          signal: controller.signal
        });
        if (componentDisposed || controller.signal.aborted) return;
        const data = response.data;

        annotationData.value = data.results || [];
        totalCount.value = data.count || 0;

      } catch (error) {
        if (isCanceledRequest(error) || controller.signal.aborted) return;
        console.error('获取注释数据失败:', error);
        annotationData.value = [];
        totalCount.value = 0;
        dataErrorKey.value = 'page.annotation.dataLoadFailed';
        ElMessage.error(t('page.annotation.dataLoadFailed'));
      } finally {
        if (annotationDataController === controller) {
          loadingAnnotation.value = false;
          annotationDataController = null;
        }
      }
    };

    // 获取可视化数据（获取更多数据用于绘图）
    const fetchVisualizationData = async () => {
      if (!selectedOrganism.value || !selectedChromosome.value) {
        visualizationController?.abort();
        visualizationController = null;
        loadingVisualization.value = false;
        return;
      }

      visualizationController = replaceRequestController(visualizationController);
      const controller = visualizationController;
      let visualizationReady = false;
      try {
        loadingVisualization.value = true;
        visualizationErrorKey.value = '';
        appliedQuery.chromosome = selectedChromosome.value;
        appliedQuery.featureType = selectedFeatureType.value;

        const params = buildAnnotationContextParams({
          featureType: 'all',
          chromosome: selectedChromosome.value,
          page: 1,
          pageSizeValue: 10000
        });

        const response = await axios.get('/files/query/annotation-data/', {
          params,
          signal: controller.signal
        });
        if (componentDisposed || controller.signal.aborted) return;
        const data = response.data;

        visualizationData.value = data.results || [];

        // 获取染色体的实际长度
        await getChromosomeLength(controller.signal);
        if (componentDisposed || controller.signal.aborted) return;
        visualizationReady = true;

      } catch (error) {
        if (isCanceledRequest(error) || controller.signal.aborted) return;
        console.error('获取可视化数据失败:', error);
        visualizationData.value = [];
        visualizationErrorKey.value = 'page.annotation.visualizationLoadFailed';
        ElMessage.error(t('page.annotation.visualizationLoadFailed'));
      } finally {
        if (visualizationController === controller) {
          loadingVisualization.value = false;
          if (visualizationReady) {
            await nextTick();
          }
          if (
            visualizationController === controller
            && !componentDisposed
            && !controller.signal.aborted
            && visualizationReady
          ) {
            drawAnnotationVisualization();
          }
          if (visualizationController === controller) {
            visualizationController = null;
          }
        }
      }
    };

    // 获取染色体长度
    const getChromosomeLength = async (signal) => {
      if (!selectedOrganism.value || !selectedChromosome.value) {
        return;
      }

      try {
        const params = buildAnnotationContextParams({
          chromosome: selectedChromosome.value
        });

        const response = await axios.get('/files/query/chromosome-length/', { params, signal });
        if (componentDisposed || signal?.aborted) return;
        chromosomeLength.value = response.data.length;
        initializeSegmentLength(chromosomeLength.value);
      } catch (error) {
        if (isCanceledRequest(error) || signal?.aborted) throw error;
        console.error('获取染色体长度失败:', error);
        // 如果获取失败，使用注释数据中的最大位置作为备选
        if (visualizationData.value.length > 0) {
          chromosomeLength.value = Math.max(...visualizationData.value.map(d => d.end));
          initializeSegmentLength(chromosomeLength.value);
        }
      }
    };

    // 绘制注释可视化
    const drawAnnotationVisualization = () => {
      if (!annotationContainer.value || !selectedOrganism.value || !selectedChromosome.value) {
        return;
      }

      // 清除之前的内容
      d3.select(annotationContainer.value).selectAll("*").remove();
      d3.selectAll('.annotation-tooltip').remove();

      const container = d3.select(annotationContainer.value);
      const width = Math.max(720, annotationContainer.value.clientWidth);

      const formatGenomicPosition = (position) => {
        const value = Number(position) || 0;
        if (Math.abs(value) >= 1000000) {
          return `${Number((value / 1000000).toFixed(2))} Mb`;
        }
        if (Math.abs(value) >= 1000) {
          return `${Number((value / 1000).toFixed(2))} kb`;
        }
        return `${Math.round(value)} bp`;
      };

      // 过滤要显示的特征类型
      const filteredData = visualizationData.value.filter(d =>
        displayFeatures.value.includes(d.feature)
      );

      if (filteredData.length === 0) {
        container.append("div")
          .style("text-align", "center")
          .style("padding", "50px")
          .style("color", "#999")
          .text(t('page.annotation.noFeatures'));
        return;
      }

      // 计算分段参数
      const segmentLen = segmentLength.value;
      const numSegments = Math.ceil(chromosomeLength.value / segmentLen);
      const margin = { top: 50, right: 50, bottom: 50, left: 50 };
      const segmentWidth = width - margin.left - margin.right;

      // 预计算每个分段的特征密度和所需高度
      const segmentInfos = [];
      let totalHeight = margin.top + margin.bottom;

      for (let i = 0; i < numSegments; i++) {
        const segmentStart = i * segmentLen;
        const segmentEnd = Math.min((i + 1) * segmentLen, chromosomeLength.value);

        // 过滤该分段的数据
        const segmentData = filteredData.filter(d =>
          d.start <= segmentEnd && d.end >= segmentStart
        );

        // 计算每种特征类型在该分段的密度
        const featureDensities = {};
        let maxDensityInSegment = 0;

        displayFeatures.value.forEach(featureType => {
          const typeData = segmentData.filter(d => d.feature === featureType);

          // 计算重叠密度：将分段分成小区间，计算每个区间的重叠数量
          const binSize = segmentLen / 100; // 将分段分成100个小区间
          const densityArray = new Array(100).fill(0);

          typeData.forEach(feature => {
            const startBin = Math.floor((feature.start - segmentStart) / binSize);
            const endBin = Math.ceil((feature.end - segmentStart) / binSize);

            for (let bin = Math.max(0, startBin); bin < Math.min(100, endBin); bin++) {
              densityArray[bin]++;
            }
          });

          const maxDensity = Math.max(...densityArray);
          featureDensities[featureType] = maxDensity;
          maxDensityInSegment = Math.max(maxDensityInSegment, maxDensity);
        });

        // 根据密度计算所需高度 - 使用更紧凑的计算
        const baseHeight = 25; // 减少基础高度
        const maxTracksPerType = Math.min(maxDensityInSegment, 4); // 限制最大轨道数为4
        const densityHeight = Math.max(0, (maxTracksPerType - 1) * 4); // 每层重叠增加4px（减少）
        const featureTypeHeight = displayFeatures.value.length * 18;
        const segmentHeight = Math.max(40, baseHeight + densityHeight + featureTypeHeight); // 最小高度40px

        segmentInfos.push({
          start: segmentStart,
          end: segmentEnd,
          height: segmentHeight,
          y: totalHeight,
          densities: featureDensities,
          maxDensity: maxDensityInSegment
        });

        totalHeight += segmentHeight + 20; // 减少分段间距为20px
      }

      const height = totalHeight;

      const svg = container.append("svg")
        .attr("width", width)
        .attr("height", height)
        .style("display", "block")
        .style("background", "#fafafa");

      // 使用统一的特征类型颜色映射
      const featureColors = {
        'gene': '#2E86AB',
        'mRNA': '#A23B72',
        'exon': '#F18F01',
        'CDS': '#C73E1D',
        'five_prime_UTR': '#7209B7',
        'three_prime_UTR': '#560BAD'
      };

      // 为每个分段绘制
      segmentInfos.forEach((segmentInfo) => {
        const { start: segmentStart, end: segmentEnd, height: segmentHeight, y: segmentY } = segmentInfo;

        // 单段短序列采用自适应比例铺满；多段染色体的末段继续保持统一比例。
        const actualSegmentLength = segmentEnd - segmentStart;
        const actualSegmentWidth = numSegments === 1
          ? segmentWidth
          : (actualSegmentLength / segmentLen) * segmentWidth;

        // 创建该分段的比例尺
        const xScale = d3.scaleLinear()
          .domain([segmentStart, segmentEnd])
          .range([margin.left, margin.left + actualSegmentWidth]);

        // 绘制染色体分段主体
        svg.append("rect")
          .attr("x", margin.left)
          .attr("y", segmentY)
          .attr("width", actualSegmentWidth)
          .attr("height", segmentHeight)
          .attr("fill", "#e8e8e8")
          .attr("stroke", "#ccc")
          .attr("stroke-width", 1);

        // 添加分段标签 - 左侧显示起始位置
        svg.append("text")
          .attr("x", margin.left - 10)
          .attr("y", segmentY + segmentHeight / 2)
          .attr("text-anchor", "end")
          .attr("dominant-baseline", "middle")
          .style("font-size", "12px")
          .style("fill", "#666")
          .text(formatGenomicPosition(segmentStart));

        // 添加分段标签 - 右侧显示终止位置
        svg.append("text")
          .attr("x", margin.left + actualSegmentWidth + 10)
          .attr("y", segmentY + segmentHeight / 2)
          .attr("text-anchor", "start")
          .attr("dominant-baseline", "middle")
          .style("font-size", "12px")
          .style("fill", "#666")
          .text(formatGenomicPosition(segmentEnd));

        // 过滤该分段的数据
        const segmentData = filteredData.filter(d =>
          d.start <= segmentEnd && d.end >= segmentStart
        );

        // 按特征类型分组绘制，使用智能布局避免重叠
        displayFeatures.value.forEach((featureType, typeIndex) => {
          const typeData = segmentData.filter(d => d.feature === featureType);

          if (typeData.length === 0) return;

          // 为该特征类型的数据分配轨道，避免重叠
          const tracks = [];
          const trackHeight = 10;
          const trackSpacing = 2;
          const maxTracks = 3; // 限制最大轨道数

          typeData.forEach(feature => {
            const startX = Math.max(xScale(feature.start), margin.left);
            const endX = Math.min(xScale(feature.end), margin.left + segmentWidth);

            // 找到第一个不重叠的轨道
            let trackIndex = 0;
            while (trackIndex < tracks.length) {
              const track = tracks[trackIndex];
              let hasOverlap = false;

              for (let existingFeature of track) {
                const existingStartX = Math.max(xScale(existingFeature.start), margin.left);
                const existingEndX = Math.min(xScale(existingFeature.end), margin.left + segmentWidth);

                if (!(endX <= existingStartX || startX >= existingEndX)) {
                  hasOverlap = true;
                  break;
                }
              }

              if (!hasOverlap) {
                track.push(feature);
                break;
              }
              trackIndex++;
            }

            // 如果没有找到合适的轨道，创建新轨道（但不超过最大轨道数）
            if (trackIndex === tracks.length && tracks.length < maxTracks) {
              tracks.push([feature]);
            } else if (trackIndex === tracks.length) {
              // 如果已达到最大轨道数，放入最后一个轨道（允许重叠）
              tracks[tracks.length - 1].push(feature);
            }
          });

          // 绘制每个轨道的特征
          tracks.forEach((track, trackIndex) => {
            const baseTrackY = segmentY + 10 + typeIndex * 18;
            const trackY = baseTrackY + trackIndex * (trackHeight + trackSpacing);

            track.forEach(feature => {
              const startX = Math.max(xScale(feature.start), margin.left);
              const endX = Math.min(xScale(feature.end), margin.left + actualSegmentWidth);
              const featureWidth = Math.max(endX - startX, 1);

              svg.append("rect")
                .attr("x", startX)
                .attr("y", trackY)
                .attr("width", featureWidth)
                .attr("height", trackHeight)
                .attr("fill", featureColors[featureType] || '#999')
                .attr("opacity", 0.8)
                .on("mouseover", function(event) {
                  // 创建tooltip
                  d3.selectAll('.annotation-tooltip').remove();
                  const tooltip = d3.select("body").append("div")
                    .attr("class", "annotation-tooltip")
                    .style("opacity", 0)
                    .style("position", "absolute")
                    .style("background", "rgba(0,0,0,0.8)")
                    .style("color", "white")
                    .style("padding", "8px")
                    .style("border-radius", "4px")
                    .style("font-size", "12px")
                    .style("pointer-events", "none")
                    .style("z-index", "1000");

                  tooltip.transition()
                    .duration(200)
                    .style("opacity", .9);

                  tooltip.html(`
                    <strong>${feature.feature}</strong><br/>
                    ${t('page.annotation.position')}: ${feature.start.toLocaleString()} - ${feature.end.toLocaleString()}<br/>
                    ${t('page.annotation.length')}: ${feature.length.toLocaleString()} bp<br/>
                    ${t('page.annotation.strand')}: ${feature.strand}<br/>
                    ${feature.attributes.ID ? 'ID: ' + feature.attributes.ID : ''}
                  `)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
                })
                .on("mouseout", function() {
                  d3.selectAll(".annotation-tooltip").remove();
                });
            });
          });
        });
      });
    };

    // 获取特征颜色
    const getFeatureColor = (featureType) => {
      const featureColors = {
        'gene': '#2E86AB',
        'mRNA': '#A23B72',
        'exon': '#F18F01',
        'CDS': '#C73E1D',
        'five_prime_UTR': '#7209B7',
        'three_prime_UTR': '#560BAD'
      };
      return featureColors[featureType] || '#999';
    };

    // 处理分段长度变化
    const handleSegmentLengthChange = () => {
      if (viewMode.value === 'chart' && selectedOrganism.value && selectedChromosome.value) {
        drawAnnotationVisualization();
      }
    };

    const resetSegmentLength = () => {
      segmentLength.value = getDefaultSegmentLengthBp(chromosomeLength.value);
      if (viewMode.value === 'chart' && selectedOrganism.value && selectedChromosome.value) {
        drawAnnotationVisualization();
      }
    };

    // 快速调整控制
    let changeInterval = null;
    let changeTimeout = null;

    const startIncrease = () => {
      // 立即执行一次
      increaseValue();
      // 设置初始延迟后开始快速重复
      changeTimeout = setTimeout(() => {
        changeInterval = setInterval(increaseValue, 50); // 每50ms执行一次，比默认快2倍
      }, 300); // 300ms后开始快速重复
    };

    const startDecrease = () => {
      // 立即执行一次
      decreaseValue();
      // 设置初始延迟后开始快速重复
      changeTimeout = setTimeout(() => {
        changeInterval = setInterval(decreaseValue, 50); // 每50ms执行一次，比默认快2倍
      }, 300); // 300ms后开始快速重复
    };

    const stopChange = () => {
      if (changeInterval) {
        clearInterval(changeInterval);
        changeInterval = null;
      }
      if (changeTimeout) {
        clearTimeout(changeTimeout);
        changeTimeout = null;
      }
    };

    const increaseValue = () => {
      const newValue = Math.min(
        segmentLengthMax.value,
        segmentLengthDisplay.value + segmentLengthStep.value
      );
      segmentLengthDisplay.value = newValue;
      handleSegmentLengthChange();
    };

    const decreaseValue = () => {
      const newValue = Math.max(
        segmentLengthMin.value,
        segmentLengthDisplay.value - segmentLengthStep.value
      );
      segmentLengthDisplay.value = newValue;
      handleSegmentLengthChange();
    };

    const validateInput = () => {
      const value = Number(segmentLengthDisplay.value);
      segmentLengthDisplay.value = Math.min(
        segmentLengthMax.value,
        Math.max(segmentLengthMin.value, Number.isFinite(value) ? value : segmentLengthMin.value)
      );
      handleSegmentLengthChange();
    };

    // 更新可视化
    const updateVisualization = () => {
      if (viewMode.value === 'chart' && selectedOrganism.value && selectedChromosome.value) {
        drawAnnotationVisualization();
      }
    };

    const clearContextData = () => {
      hierarchyController?.abort();
      optionsController?.abort();
      annotationDataController?.abort();
      visualizationController?.abort();
      hierarchyController = null;
      optionsController = null;
      annotationDataController = null;
      visualizationController = null;
      loadingHierarchy.value = false;
      loadingOptions.value = false;
      loadingAnnotation.value = false;
      loadingVisualization.value = false;
      Object.assign(draftQuery, {
        accession: '',
        assemblyId: '',
        annotationId: '',
        chromosome: '',
        featureType: 'all'
      });
      Object.assign(appliedQuery, {
        accession: '',
        assemblyId: '',
        annotationId: '',
        chromosome: '',
        featureType: 'all'
      });
      hierarchyAssemblies.value = [];
      assemblyOptions.value = [];
      annotationOptions.value = [];
      loadedHierarchyAccession.value = '';
      currentPage.value = 1;
      annotationData.value = [];
      totalCount.value = 0;
      annotationStatistics.value = null;
      dataErrorKey.value = '';
      visualizationErrorKey.value = '';
      loadedOptionsAnnotationId.value = '';
      optionsRequestToken.value += 1;
      chromosomeOptions.value = [];
      featureTypeOptions.value = ['all'];
      visualizationData.value = [];
      chromosomeLength.value = 0;
      contextErrorKey.value = '';
      hierarchyLoadFailed.value = false;
      loadingHierarchy.value = false;
    };

    const syncRouteContext = async (requestToken) => {
      const accession = normalizeQueryValue(route.query.accession) || normalizeQueryValue(route.query.organism);
      const requestedAssemblyId = normalizeQueryValue(route.query.assembly);
      const requestedAnnotationId = normalizeQueryValue(route.query.annotation);
      const requestedChromosome = normalizeQueryValue(route.query.chromosome);
      const requestedFeatureType = normalizeQueryValue(route.query.feature) || 'all';
      const requestedViewMode = normalizeViewMode(route.query.view);
      const requestedPage = normalizePositiveInteger(route.query.page, 1);
      const requestedPageSize = normalizePageSize(route.query.page_size);

      if (!accession) {
        clearContextData();
        return true;
      }

      contextErrorKey.value = '';
      selectedOrganism.value = accession;
      draftQuery.assemblyId = requestedAssemblyId;
      draftQuery.annotationId = requestedAnnotationId;
      draftQuery.chromosome = requestedChromosome;
      draftQuery.featureType = requestedFeatureType;
      appliedQuery.chromosome = requestedChromosome;
      appliedQuery.featureType = requestedFeatureType;
      viewMode.value = requestedViewMode;
      currentPage.value = requestedPage;
      pageSize.value = requestedPageSize;

      const hierarchyLoaded = await fetchAccessionHierarchy(accession);
      if (
        componentDisposed
        || requestToken !== routeRequestToken
        || !hierarchyLoaded
      ) {
        return false;
      }

      if (hierarchyLoadFailed.value) {
        contextErrorKey.value = 'page.annotation.contextLoadFailed';
        return false;
      }

      const assembly = pickAssembly(requestedAssemblyId);
      if (requestedAssemblyId && !assembly) {
        updateAnnotationOptions(null);
        contextAccession.value = accession;
        contextAssemblyId.value = '';
        contextAnnotationId.value = '';
        contextErrorKey.value = 'page.annotation.assemblyNotFound';
        return false;
      }
      updateAnnotationOptions(assembly);
      const annotation = pickAnnotation(assembly, requestedAnnotationId);

      const resolvedAssemblyId = assembly?.id ? String(assembly.id) : '';
      const resolvedAnnotationId = annotation?.id ? String(annotation.id) : '';
      const contextChanged = (
        appliedQuery.accession !== accession
        || appliedQuery.assemblyId !== resolvedAssemblyId
        || appliedQuery.annotationId !== resolvedAnnotationId
      );
      draftQuery.assemblyId = resolvedAssemblyId;
      draftQuery.annotationId = resolvedAnnotationId;
      contextAccession.value = accession;
      contextAssemblyId.value = assembly?.id ? String(assembly.id) : '';
      if (requestedAnnotationId && !annotation) {
        contextAnnotationId.value = '';
        contextErrorKey.value = 'page.annotation.annotationNotFound';
        return false;
      }
      contextAnnotationId.value = annotation?.id ? String(annotation.id) : '';
      if (contextChanged) {
        annotationStatistics.value = null;
        loadedOptionsAnnotationId.value = '';
        dataErrorKey.value = '';
        visualizationErrorKey.value = '';
      }

      if (allOrganisms.value.length && !allOrganisms.value.includes(accession)) {
        organismOptions.value = Array.from(new Set([accession, ...allOrganisms.value]));
      }

      await replaceRouteQuery(buildNormalizedQuery({
        accession,
        assembly: assembly?.id || '',
        annotation: annotation?.id || '',
        chromosome: requestedChromosome,
        featureType: requestedFeatureType,
        view: requestedViewMode,
        page: requestedPage,
        pageSize: requestedPageSize,
        from: normalizeQueryValue(route.query.from),
        returnTo: route.query.return_to
      }));
      return true;
    };

    const reconcileRouteFilters = async () => {
      const chromosomeIsValid = !selectedChromosome.value
        || chromosomeOptions.value.includes(selectedChromosome.value);
      const featureIsValid = selectedFeatureType.value === 'all'
        || featureTypeOptions.value.includes(selectedFeatureType.value);

      if (!chromosomeIsValid) selectedChromosome.value = '';
      if (!featureIsValid) selectedFeatureType.value = 'all';
      appliedQuery.chromosome = selectedChromosome.value;
      appliedQuery.featureType = selectedFeatureType.value;
      if (!chromosomeIsValid || !featureIsValid) currentPage.value = 1;

      await replaceRouteQuery(buildCurrentRouteQuery());
    };

    const returnToAssembly = () => {
      if (annotationReturnPath.value) {
        router.push(annotationReturnPath.value);
        return;
      }
      const targetAssemblyId = contextAssemblyId.value || normalizeQueryValue(route.query.assembly);
      if (targetAssemblyId) {
        router.push({ name: 'assembly-detail', params: { assemblyId: targetAssemblyId } });
      } else {
        router.push({ name: 'assembly' });
      }
    };

    const useDefaultAnnotation = async () => {
      const requestedAssemblyId = contextErrorKey.value === 'page.annotation.assemblyNotFound'
        ? ''
        : contextAssemblyId.value || normalizeQueryValue(route.query.assembly);
      await router.replace({
        path: route.path,
        query: buildNormalizedQuery({
          accession: contextAccession.value || normalizeQueryValue(route.query.accession),
          assembly: requestedAssemblyId,
          from: normalizeQueryValue(route.query.from),
          returnTo: route.query.return_to
        })
      });
    };

    // 获取文件列表（保持兼容性）
    const fetchFiles = async () => {
      try {
        loading.value = true;
        if (selectedOrganism.value) {
          if (viewMode.value === 'table') {
            await fetchAnnotationData();
          } else if (viewMode.value === 'chart' && selectedChromosome.value) {
            await fetchVisualizationData();
          }
        }
      } catch (error) {
        console.error('获取数据失败:', error);
        ElMessage.error(t('messages.getDataFailed'));
      } finally {
        loading.value = false;
      }
    };

    const normalizeAccession = (value) => String(value || '').trim().toLowerCase();

    const queryAccessionSuggestions = (query, callback) => {
      const normalizedQuery = normalizeAccession(query);
      const matches = normalizedQuery
        ? allOrganisms.value.filter(item => normalizeAccession(item).includes(normalizedQuery))
        : allOrganisms.value;

      organismOptions.value = matches;
      callback(matches.slice(0, 50).map(value => ({ value })));
    };

    const handleAccessionSearch = async () => {
      const keyword = String(selectedOrganism.value || '').trim();
      if (!keyword) {
        ElMessage.warning(t('page.annotation.enterAccession'));
        return;
      }

      const accession = allOrganisms.value.find(
        item => normalizeAccession(item) === normalizeAccession(keyword)
      );
      if (!accession) {
        ElMessage.warning(t('page.annotation.noExactMatch', { accession: keyword }));
        return;
      }

      if (
        normalizeAccession(accession) === normalizeAccession(loadedHierarchyAccession.value)
        && selectedAssemblyId.value
        && selectedAnnotationId.value
      ) {
        await pushRouteQuery(buildCurrentRouteQuery({ accession }));
        await handleRouteParams();
        return;
      }

      await handleOrganismChange(accession);
    };

    const handleAccessionSelect = async (item) => {
      await handleOrganismChange(item?.value || '');
    };

    const handleAccessionInput = (value) => {
      if (normalizeAccession(value) === normalizeAccession(loadedHierarchyAccession.value)) return;
      draftQuery.assemblyId = '';
      draftQuery.annotationId = '';
      draftQuery.chromosome = '';
      draftQuery.featureType = 'all';
      hierarchyAssemblies.value = [];
      assemblyOptions.value = [];
      annotationOptions.value = [];
      loadedHierarchyAccession.value = '';
    };

    // 生物体选择变化
    const handleOrganismChange = async (value) => {
      selectedOrganism.value = value;
      draftQuery.assemblyId = '';
      draftQuery.annotationId = '';
      draftQuery.chromosome = '';
      draftQuery.featureType = 'all';
      currentPage.value = 1;

      if (value) {
        contextAccession.value = value;
        contextAssemblyId.value = '';
        contextAnnotationId.value = '';
        appliedQuery.chromosome = '';
        appliedQuery.featureType = 'all';
        hierarchyAssemblies.value = [];
        assemblyOptions.value = [];
        annotationOptions.value = [];
        loadedHierarchyAccession.value = '';
        visualizationData.value = [];
        chromosomeLength.value = 0;
        await pushRouteQuery(buildNormalizedQuery({ accession: value }));
        await handleRouteParams();
      } else {
        clearContextData();
        await pushRouteQuery({});
      }
    };

    const handleAssemblyChange = async (value) => {
      const assembly = assemblyOptions.value.find((item) => matchesId(item, value));
      selectedAssemblyId.value = assembly?.id || '';
      updateAnnotationOptions(assembly);
      const annotation = pickAnnotation(assembly, '');
      selectedAnnotationId.value = annotation?.id || '';
      selectedChromosome.value = '';
      selectedFeatureType.value = 'all';
      currentPage.value = 1;
      visualizationData.value = [];
      chromosomeLength.value = 0;
      segmentLengthContextKey = '';
      dataErrorKey.value = '';
      visualizationErrorKey.value = '';
      if (!assembly) return;

      await pushRouteQuery(buildCurrentRouteQuery({
        assembly: assembly.id,
        annotation: annotation?.id || '',
        chromosome: '',
        featureType: 'all',
        page: 1
      }));
      await handleRouteParams();
    };

    const handleAnnotationChange = async (value) => {
      const annotation = annotationOptions.value.find((item) => matchesId(item, value));
      selectedAnnotationId.value = annotation?.id || '';
      selectedChromosome.value = '';
      selectedFeatureType.value = 'all';
      currentPage.value = 1;
      visualizationData.value = [];
      chromosomeLength.value = 0;
      dataErrorKey.value = '';
      visualizationErrorKey.value = '';
      if (!annotation) return;

      await pushRouteQuery(buildCurrentRouteQuery({
        annotation: annotation.id,
        chromosome: '',
        featureType: 'all',
        page: 1
      }));
      await handleRouteParams();
    };

    // 染色体选择变化
    const handleChromosomeChange = async (value) => {
      selectedChromosome.value = value;
      visualizationErrorKey.value = '';
      appliedQuery.chromosome = selectedChromosome.value;
      currentPage.value = 1;
      await pushRouteQuery(buildCurrentRouteQuery());
      if (viewMode.value === 'table') {
        await fetchAnnotationData();
      } else if (viewMode.value === 'chart' && value) {
        await fetchVisualizationData();
      } else if (!value) {
        visualizationData.value = [];
        chromosomeLength.value = 0;
      }
    };

    // 特征类型选择变化
    const handleFeatureTypeChange = async (value) => {
      selectedFeatureType.value = value;
      appliedQuery.featureType = selectedFeatureType.value;
      currentPage.value = 1;
      await pushRouteQuery(buildCurrentRouteQuery());
      await fetchAnnotationData();
    };

    const resetAnnotationFilters = async () => {
      selectedChromosome.value = '';
      selectedFeatureType.value = 'all';
      appliedQuery.chromosome = '';
      appliedQuery.featureType = 'all';
      currentPage.value = 1;
      visualizationData.value = [];
      chromosomeLength.value = 0;
      dataErrorKey.value = '';
      visualizationErrorKey.value = '';
      await pushRouteQuery(buildCurrentRouteQuery());
      if (viewMode.value === 'table' && selectedAnnotationId.value) {
        await fetchAnnotationData();
      }
    };

    const handleViewModeChange = async (mode) => {
      viewMode.value = mode === 'chart' ? 'chart' : 'table';
      if (viewMode.value === 'chart') {
        annotationDataController?.abort();
        annotationDataController = null;
        loadingAnnotation.value = false;
      } else {
        visualizationController?.abort();
        visualizationController = null;
        loadingVisualization.value = false;
        d3.selectAll('.annotation-tooltip').remove();
      }
      await pushRouteQuery(buildCurrentRouteQuery());
      if (viewMode.value === 'chart') {
        if (selectedChromosome.value) await fetchVisualizationData();
      } else if (selectedAnnotationId.value) {
        await fetchAnnotationData();
      }
    };

    // 分页大小变化
    const handleSizeChange = async (size) => {
      pageSize.value = size;
      currentPage.value = 1;
      await pushRouteQuery(buildCurrentRouteQuery());
      await fetchAnnotationData();
    };

    // 当前页变化
    const handleCurrentChange = async (page) => {
      currentPage.value = page;
      await pushRouteQuery(buildCurrentRouteQuery());
      await fetchAnnotationData();
    };

    // 处理URL参数
    const handleRouteParams = async () => {
      const requestToken = routeRequestToken + 1;
      routeRequestToken = requestToken;
      loading.value = true;
      const isValidContext = await syncRouteContext(requestToken);
      if (componentDisposed || requestToken !== routeRequestToken) return;
      if (isValidContext) {
        await fetchAnnotationOptions();
        if (componentDisposed || requestToken !== routeRequestToken) return;
        await reconcileRouteFilters();
        if (componentDisposed || requestToken !== routeRequestToken) return;
        await fetchFiles();
      } else {
        loading.value = false;
      }
    };

    watch(
      () => [
        route.query.accession,
        route.query.organism,
        route.query.assembly,
        route.query.annotation,
        route.query.chromosome,
        route.query.feature,
        route.query.view,
        route.query.page,
        route.query.page_size,
        route.query.from,
        route.query.return_to
      ],
      async () => {
        if (routeSyncInProgress.value) {
          return;
        }
        await handleRouteParams();
      }
    );

    watch(allOrganisms, async (newOrganisms) => {
      if (newOrganisms.length > 0 && selectedOrganism.value && !newOrganisms.includes(selectedOrganism.value)) {
        organismOptions.value = Array.from(new Set([selectedOrganism.value, ...newOrganisms]));
      }
    });

    onMounted(async () => {
      await fetchOrganisms();
      if (componentDisposed) return;
      await handleRouteParams();
    });

    onBeforeUnmount(() => {
      componentDisposed = true;
      routeRequestToken += 1;
      organismsController?.abort();
      hierarchyController?.abort();
      optionsController?.abort();
      annotationDataController?.abort();
      visualizationController?.abort();
      stopChange();
      d3.selectAll('.annotation-tooltip').remove();
      if (annotationContainer.value) {
        d3.select(annotationContainer.value).selectAll('*').remove();
      }
    });

    return {
      loading,
      loadingOrganisms,
      loadingAnnotation,
      loadingHierarchy,
      loadingOptions,
      loadingVisualization,
      draftQuery,
      appliedQuery,
      selectedOrganism,
      selectedAssemblyId,
      selectedAnnotationId,
      selectedChromosome,
      selectedFeatureType,
      organismOptions,
      assemblyOptions,
      annotationOptions,
      chromosomeOptions,
      featureTypeOptions,
      annotationData,
      annotationStatistics,
      dataErrorKey,
      visualizationErrorKey,
      currentPage,
      pageSize,
      totalCount,
      displayedResultCount,
      contextErrorKey,
      annotationReturnPath,
      viewMode,
      annotationContainer,
      displayFeatures,
      segmentLength,
      segmentLengthDisplay,
      segmentLengthUnit,
      segmentLengthStep,
      segmentLengthMin,
      segmentLengthMax,
      segmentLengthResetLabel,
      fetchFiles,
      fetchOrganisms,
      fetchAnnotationData,
      fetchAnnotationOptions,
      fetchVisualizationData,
      drawAnnotationVisualization,
      updateVisualization,
      handleSegmentLengthChange,
      resetSegmentLength,
      startIncrease,
      startDecrease,
      stopChange,
      validateInput,
      getFeatureColor,
      queryAccessionSuggestions,
      getAssemblyLabel,
      getAnnotationLabel,
      handleAccessionSearch,
      handleAccessionSelect,
      handleAccessionInput,
      handleOrganismChange,
      handleAssemblyChange,
      handleAnnotationChange,
      handleChromosomeChange,
      handleFeatureTypeChange,
      resetAnnotationFilters,
      handleViewModeChange,
      handleSizeChange,
      handleCurrentChange,
      handleRouteParams,
      returnToAssembly,
      useDefaultAnnotation
    };
  }
};
</script>

<style scoped>
.annotation-view {
  padding: 0;
  min-height: calc(100vh - 160px);
  color: #132449;
}

.annotation-hero {
  margin-bottom: 12px;
  padding-top: 4px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: #7183a0;
  font-size: 13px;
}

.breadcrumb a,
.breadcrumb button {
  padding: 0;
  border: 0;
  background: transparent;
  color: #2b6fc7;
  font: inherit;
  text-decoration: none;
  cursor: pointer;
}

.breadcrumb a:hover,
.breadcrumb a:focus-visible,
.breadcrumb button:hover,
.breadcrumb button:focus-visible {
  color: #0068e8;
  text-decoration: underline;
  outline: none;
}

.annotation-hero h1 {
  margin: 0;
  color: #102f61;
  font-size: 30px;
  line-height: 1.12;
  letter-spacing: -0.03em;
}

.data-card {
  padding: 14px 15px 16px;
  border: 1px solid #d9e7f7;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 14px 36px rgba(36, 103, 178, 0.08);
}

.data-card-header,
.data-card-actions,
.data-card-header h2 {
  display: flex;
  align-items: center;
}

.data-card-header {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.data-card-header h2 {
  gap: 8px;
  margin: 0;
  color: #0060df;
  font-size: 18px;
  line-height: 1.2;
}

.data-card-actions {
  gap: 10px;
  color: #60799e;
  font-size: 13px;
}

.loading {
  padding: 20px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.data-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid #f3c2c2;
  border-radius: 8px;
  background: #fef0f0;
  color: #b42318;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
}

.content-container {
  padding: 0;
}

.annotation-table {
  margin-top: 0;
}

.attributes-container {
  max-height: 100px;
  overflow-y: auto;
}

.attribute-item {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
}

.attr-key {
  font-weight: 500;
  color: #909399;
  margin-right: 4px;
}

.attr-value {
  color: #606266;
  word-break: break-all;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  overflow-x: auto;
}

.view-toggle {
  display: flex;
  align-items: center;
}

.annotation-visualization {
  margin-top: 0; /* 移除上边距，让内容向上对齐 */
}

.chart-content {
  /* 确保图形内容紧贴上方 */
  margin-top: 0;
}

.loading-visualization {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #606266;
}

.visualization-controls {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  margin-top: 0; /* 移除上边距 */
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.segment-length-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.fast-control-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  font-size: 14px;
  font-weight: bold;
  border-radius: 4px;
  user-select: none;
  cursor: pointer;
}

.fast-control-btn:active {
  transform: scale(0.95);
}

.segment-input {
  width: 80px;
  text-align: center;
}

.segment-input .el-input__inner {
  text-align: center;
  font-size: 12px;
  padding: 0 8px;
}

.reset-button {
  white-space: nowrap;
  font-size: 12px;
  padding: 4px 8px;
  margin-left: 4px;
}

.control-label {
  font-weight: 500;
  color: #606266;
  min-width: 100px;
}

.feature-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  min-height: 40px;
}

.feature-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
}

.feature-legend {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
  margin-right: 4px;
}

.annotation-container {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: white;
  min-height: 220px;
  overflow-x: auto;
}

/* Tooltip样式 */
.annotation-tooltip {
  position: absolute;
  background: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  pointer-events: none;
  z-index: 1000;
}

/* 加快input-number按钮响应速度 */
.el-input-number {
  /* 减少按钮按下时的延迟 */
  --el-input-number-controls-height: 14px;
}

.el-input-number .el-input-number__increase,
.el-input-number .el-input-number__decrease {
  /* 加快按钮重复触发的速度 */
  transition: none !important;
}

/* 自定义按钮行为，加快连续点击速度 */
.control-group .el-input-number {
  --el-input-number-controls-height: 14px;
}

.control-group .el-input-number .el-input-number__increase:active,
.control-group .el-input-number .el-input-number__decrease:active {
  /* 按下时立即响应 */
  transform: scale(0.95);
}

@media (max-width: 760px) {
  .annotation-hero h1 { font-size: 26px; }
  .data-card-header { align-items: flex-start; }
  .data-card-actions { flex-shrink: 0; }
  .pagination-container { justify-content: flex-start; }
  .visualization-controls, .control-group { align-items: flex-start; }
  .control-group { flex-direction: column; }
}
</style>

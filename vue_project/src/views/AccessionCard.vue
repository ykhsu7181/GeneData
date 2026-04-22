<template>
  <div class="accession-card-view">
    <div class="page-header">
      <h2 class="title">{{ $t('page.accessionCard.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('common.refresh')" placement="top">
          <el-button circle size="small" @click="refreshPage">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <div class="search-container">
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-select
          v-model="selectedAccession"
          filterable
          remote
          clearable
          class="search-select"
          :placeholder="$t('page.accessionCard.searchPlaceholder')"
          :remote-method="searchOrganisms"
          :loading="loadingOrganisms"
          @change="handleAccessionChange"
          @visible-change="handleSearchVisibleChange"
        >
          <el-option
            v-for="item in organismOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </div>
    </div>

    <div class="data-card">
      <div v-if="loading" class="loading">
        <el-skeleton :rows="12" animated />
      </div>

      <div v-else-if="!selectedAccession" class="empty-state">
        <el-empty description="请选择一个 accession 查看详情" />
      </div>

      <div v-else-if="errorMessage" class="empty-state">
        <el-empty :description="errorMessage" />
      </div>

      <div v-else-if="accessionDetail" class="content-container">
        <div class="top-grid">
          <section class="panel info-panel">
            <div class="panel-header">
              <div>
                <h3 class="panel-title">{{ accessionDetail.accession }}</h3>
                <div class="panel-subtitle">Accession overview</div>
              </div>
              <div class="panel-header-actions">
                <span class="panel-badge">{{ summary.file_count || 0 }} files</span>
                <el-button
                  size="small"
                  class="detail-table-button"
                  @click="goToDetailTable"
                >
                  Details
                </el-button>
              </div>
            </div>

            <div class="info-grid">
              <div class="info-row info-row-2">
                <div class="info-item info-item-tall">
                  <div class="info-label">SeqData</div>
                  <div class="info-value">
                    <a
                      v-if="accessionDetail.seq_data"
                      :href="accessionDetail.seq_data"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="seq-link"
                    >
                      {{ accessionDetail.seq_data }}
                    </a>
                    <span v-else>-</span>
                  </div>
                </div>

                <div class="info-item info-item-tall">
                  <div class="info-label">SubPopulation</div>
                  <div class="info-value">
                    <template v-if="accessionDetail.sub_population">
                      <span :class="['sub-population-badge', subPopulationTagClass]">
                        {{ accessionDetail.sub_population }}
                      </span>
                    </template>
                    <span v-else>-</span>
                  </div>
                </div>
              </div>

              <div class="info-row info-row-4">
                <div class="info-item info-item-compact-tight">
                  <div class="info-label">Country/Region</div>
                  <div class="info-value">
                    <div>{{ locationLabel }}</div>
                  </div>
                </div>

                <div class="info-item info-item-compact-tight">
                  <div class="info-label">Longitude</div>
                  <div class="info-value">{{ accessionDetail.longitude ?? '-' }}</div>
                </div>

                <div class="info-item info-item-compact-tight">
                  <div class="info-label">Latitude</div>
                  <div class="info-value">{{ accessionDetail.latitude ?? '-' }}</div>
                </div>

                <div class="info-item info-item-compact-tight">
                  <div class="info-label">Location</div>
                  <div class="info-value">
                    <button
                      type="button"
                      class="inline-link location-link"
                      @click="goToAccessionMap"
                    >
                      location.{{ accessionDetail.accession || selectedAccession || '-' }}
                    </button>
                  </div>
                </div>
              </div>

              <div class="info-row info-row-3">
                <div class="info-item info-item-list info-item-list-narrow">
                  <div class="info-label">Accession</div>
                  <div class="info-value">
                    <button type="button" class="inline-link accession-link" @click="goToDataOverview">
                      {{ accessionDetail.accession || '-' }}
                    </button>
                  </div>
                </div>

                <div class="info-item info-item-list info-item-list-medium info-item-summary">
                  <el-tooltip
                    effect="light"
                    placement="top-start"
                    :show-after="120"
                    :disabled="!assemblyTooltipEntries.length"
                    popper-class="accession-summary-tooltip"
                  >
                    <template #default>
                      <div
                        class="summary-card-trigger"
                        role="button"
                        tabindex="0"
                        @click="goToDetailTable('assembly')"
                        @keydown.enter.prevent="goToDetailTable('assembly')"
                        @keydown.space.prevent="goToDetailTable('assembly')"
                      >
                        <div class="info-label">Assembly</div>
                        <div class="summary-interactive-block">
                          <div class="summary-quantity">{{ assemblyCount }}</div>
                        </div>
                      </div>
                    </template>
                    <template #content>
                      <div class="summary-tooltip">
                        <div
                          v-for="entry in assemblyTooltipEntries"
                          :key="`assembly-tooltip-${entry.id}`"
                          class="summary-tooltip-row summary-tooltip-row-2"
                        >
                          <div class="summary-tooltip-cell summary-tooltip-cell-primary">{{ entry.name }}</div>
                          <div class="summary-tooltip-cell summary-tooltip-cell-mono">{{ entry.bioProject }}</div>
                        </div>
                        <div class="summary-tooltip-footer">
                          <span class="summary-tooltip-footer-icon">&#8599;</span>
                          <span>Click to view detailed information</span>
                        </div>
                      </div>
                    </template>
                  </el-tooltip>
                </div>

                <div class="info-item info-item-list info-item-list-wide info-item-summary">
                  <el-tooltip
                    effect="light"
                    placement="top-start"
                    :show-after="120"
                    :disabled="!annotationTooltipEntries.length"
                    popper-class="accession-summary-tooltip"
                  >
                    <template #default>
                      <div
                        class="summary-card-trigger"
                        role="button"
                        tabindex="0"
                        @click="goToDetailTable('annotation')"
                        @keydown.enter.prevent="goToDetailTable('annotation')"
                        @keydown.space.prevent="goToDetailTable('annotation')"
                      >
                        <div class="info-label">Annotation</div>
                        <div class="summary-interactive-block">
                          <div class="summary-quantity">{{ annotationCount }}</div>
                        </div>
                      </div>
                    </template>
                    <template #content>
                      <div class="summary-tooltip">
                        <div
                          v-for="entry in annotationTooltipEntries"
                          :key="`annotation-tooltip-${entry.id}`"
                          class="summary-tooltip-row summary-tooltip-row-3"
                        >
                          <div class="summary-tooltip-cell summary-tooltip-cell-primary">{{ entry.name }}</div>
                          <div class="summary-tooltip-cell">{{ entry.featureTypes }}</div>
                          <div class="summary-tooltip-cell">{{ entry.source }}</div>
                        </div>
                        <div class="summary-tooltip-footer">
                          <span class="summary-tooltip-footer-icon">&#8599;</span>
                          <span>Click to view detailed information</span>
                        </div>
                      </div>
                    </template>
                  </el-tooltip>
                </div>
              </div>

              <div class="info-row info-row-1">
                <div class="info-item info-item-wide">
                  <div class="info-label">Description</div>
                  <div class="info-value">{{ accessionDetail.description || '-' }}</div>
                </div>
              </div>
            </div>
          </section>

          <section class="panel resources-panel resources-panel-top">
            <div class="panel-header">
              <div>
                <h3 class="panel-title">Current Modules</h3>
                <div class="panel-subtitle">Module entry points are derived from current context</div>
              </div>
            </div>

            <div class="resource-grid">
              <article
                v-for="resource in resourceCards"
                :key="resource.key"
                :class="['resource-card', resource.enabled ? 'resource-card-active' : 'resource-card-disabled']"
              >
                <div class="resource-top">
                  <div class="resource-title">{{ resource.title }}</div>
                  <span :class="['resource-pill', resource.enabled ? 'pill-available' : 'pill-unavailable']">
                    {{ resource.enabled ? 'Available' : 'Unavailable' }}
                  </span>
                </div>

                <div class="resource-scope">{{ resource.scopeLabel }}</div>
                <div class="resource-file">{{ resource.fileLabel }}</div>
                <div class="resource-desc">{{ resource.description }}</div>

                <div class="resource-actions">
                  <el-button
                    v-if="false"
                    link
                    type="primary"
                    @click="openResource(resource)"
                  >
                    下载文件
                  </el-button>
                  <el-button
                    v-if="resource.enabled"
                    link
                    type="primary"
                    @click="openResource(resource)"
                  >
                    View
                  </el-button>
                  <el-button
                    v-if="resource.file?.id"
                    link
                    type="primary"
                    @click="downloadFile(resource.file)"
                  >
                    {{ resource.downloadLabel || 'Download' }}
                  </el-button>
                </div>
              </article>
            </div>
          </section>
        </div>

        <div class="main-grid">
          <section class="panel hierarchy-panel">
            <div class="panel-header hierarchy-header">
              <div>
                <h3 class="panel-title">Assemblies</h3>
                <div class="panel-subtitle">Accession -> Assembly -> Annotation hierarchy</div>
                <div v-if="currentContextSummary" class="hierarchy-current-summary">
                  Current: {{ currentContextSummary }}
                </div>
              </div>
              <div class="hierarchy-legend">
                <span class="legend-chip legend-accession">Accession</span>
                <span class="legend-chip legend-assembly">Assembly</span>
                <span class="legend-chip legend-annotation">Annotation</span>
              </div>
            </div>

            <div v-if="assemblies.length" ref="hierarchyGraphRef" class="hierarchy-graph">
              <svg
                v-if="hierarchySvgSize.width && hierarchySvgSize.height"
                class="hierarchy-lines"
                :width="hierarchySvgSize.width"
                :height="hierarchySvgSize.height"
                :viewBox="`0 0 ${hierarchySvgSize.width} ${hierarchySvgSize.height}`"
                aria-hidden="true"
              >
                <path
                  v-for="line in hierarchyLinePaths"
                  :key="line.key"
                  :d="line.path"
                  :class="['hierarchy-line', line.active ? 'hierarchy-line-active' : 'hierarchy-line-muted']"
                />
              </svg>

              <div class="accession-lane">
                <article ref="accessionNodeRef" class="hierarchy-node accession-node">
                  <div class="node-title">{{ accessionDetail.accession }}</div>
                  <div class="node-meta">
                    <span>{{ summary.assembly_count || assemblies.length }} assemblies</span>
                    <span>{{ summary.annotation_count || 0 }} annotations</span>
                  </div>
                </article>
              </div>

              <div class="branch-lane">
                <article
                  v-for="assembly in assemblies"
                  :key="assembly.id"
                  :class="[
                    'assembly-branch',
                    isCurrentAssembly(assembly) ? 'assembly-branch-active' : 'assembly-branch-inactive'
                  ]"
                >
                  <div class="assembly-main-column">
                    <div class="assembly-row">
                      <div
                        :ref="(el) => setAssemblyNodeRef(assembly.id, el)"
                        :class="['hierarchy-node', 'assembly-node', isCurrentAssembly(assembly) ? 'assembly-node-active' : '']"
                        @click="selectAssembly(assembly.id)"
                        @keydown.enter.prevent="selectAssembly(assembly.id)"
                        @keydown.space.prevent="selectAssembly(assembly.id)"
                        role="button"
                        tabindex="0"
                      >
                        <div class="node-top">
                          <div class="node-title-stack">
                            <div class="node-title-row">
                              <span class="node-title">{{ assembly.name }}</span>
                              <div class="node-tags">
                                <span v-if="assembly.is_default" class="status-tag status-default">default</span>
                              </div>
                            </div>
                            <div class="node-meta">
                              <span>{{ assembly.files?.length || 0 }} assembly files</span>
                              <span>{{ assembly.annotations?.length || 0 }} annotations</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            class="node-inline-link node-inline-link-assembly"
                            @click.stop="openGenomeCard(assembly)"
                          >Genome details</button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-if="assembly.annotations?.length" class="annotation-column">
                    <div
                      v-for="annotation in assembly.annotations"
                      :key="annotation.id"
                      :class="[
                        'annotation-row',
                        isSelectedAnnotation(assembly, annotation) ? 'annotation-row-active' : 'annotation-row-muted'
                      ]"
                    >
                      <div
                        :ref="(el) => setAnnotationNodeRef(assembly.id, annotation.id, el)"
                        :class="[
                          'hierarchy-node',
                          'annotation-node',
                          isSelectedAnnotation(assembly, annotation) ? 'annotation-node-active' : 'annotation-node-muted'
                        ]"
                        @click="selectAnnotation(assembly.id, annotation.id)"
                        @keydown.enter.prevent="selectAnnotation(assembly.id, annotation.id)"
                        @keydown.space.prevent="selectAnnotation(assembly.id, annotation.id)"
                        role="button"
                        tabindex="0"
                      >
                        <div class="node-top">
                          <div class="node-title-stack">
                            <div class="node-title-row">
                              <span class="node-title">{{ annotation.name }}</span>
                              <div class="node-tags">
                                <span v-if="annotation.is_default" class="status-tag status-default">default</span>
                              </div>
                            </div>
                            <div class="node-meta">
                              {{ annotation.files?.length || 0 }} annotation files
                            </div>
                          </div>
                          <button
                            type="button"
                            class="node-inline-link node-inline-link-annotation"
                            @click.stop="openAnnotationCard(assembly, annotation)"
                          >Annotation details</button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-else class="annotation-ghost annotation-ghost-inline">
                    No annotations in this assembly
                  </div>
                </article>
              </div>
            </div>

            <div v-if="false" class="assembly-list">
              <article
                v-for="assembly in assemblies"
                :key="assembly.id"
                :class="['assembly-card', isCurrentAssembly(assembly) ? 'assembly-card-active' : '']"
              >
                <button class="assembly-card-header" type="button" @click="selectAssembly(assembly.id)">
                  <div class="assembly-main">
                    <div class="assembly-title-row">
                      <span class="assembly-title">{{ assembly.name }}</span>
                      <span v-if="assembly.is_default" class="status-tag status-default">default</span>
                      <span v-if="isCurrentAssembly(assembly)" class="status-tag status-current">selected</span>
                    </div>
                    <div class="assembly-meta">
                      <span>{{ assembly.files?.length || 0 }} assembly files</span>
                      <span>{{ assembly.annotations?.length || 0 }} annotations</span>
                    </div>
                  </div>
                </button>

                <div v-if="isCurrentAssembly(assembly)" class="annotation-panel">
                  <div class="annotation-panel-header">
                    <span class="annotation-panel-title">Annotations</span>
                    <span class="annotation-panel-tip">
                      {{ assembly.annotations?.length || 0 }} in current assembly
                    </span>
                  </div>

                  <div v-if="assembly.annotations?.length" class="annotation-list">
                    <button
                      v-for="annotation in assembly.annotations"
                      :key="annotation.id"
                      type="button"
                      :class="[
                        'annotation-card',
                        isCurrentAnnotation(annotation) ? 'annotation-card-active' : ''
                      ]"
                      @click="selectAnnotation(assembly.id, annotation.id)"
                    >
                      <div class="annotation-title-row">
                        <span class="annotation-title">{{ annotation.name }}</span>
                        <span v-if="annotation.is_default" class="status-tag status-default">default</span>
                      </div>
                      <div class="annotation-meta">
                        {{ annotation.files?.length || 0 }} annotation files
                      </div>
                    </button>
                  </div>

                  <div v-else class="annotation-empty">
                    <el-empty description="当前 assembly 暂无 annotation" :image-size="72" />
                  </div>
                </div>
              </article>
            </div>

            <div v-if="!assemblies.length" class="hierarchy-empty">
              <el-empty description="当前 accession 暂无 assembly" :image-size="80" />
            </div>
          </section>

          <section v-if="false" class="panel context-panel context-panel-bottom">
            <div class="panel-header">
              <div>
                <h3 class="panel-title">Current Context</h3>
                <div class="panel-subtitle">Active selection after URL normalization</div>
              </div>
            </div>

            <div v-if="false" class="resource-grid">
              <article
                v-for="resource in resourceCards"
                :key="resource.key"
                :class="['resource-card', resource.enabled ? 'resource-card-active' : 'resource-card-disabled']"
              >
                <div class="resource-top">
                  <div class="resource-title">{{ resource.title }}</div>
                  <span :class="['resource-pill', resource.enabled ? 'pill-available' : 'pill-unavailable']">
                    {{ resource.enabled ? 'Available' : 'Unavailable' }}
                  </span>
                </div>

                <div class="resource-scope">{{ resource.scopeLabel }}</div>
                <div class="resource-file">{{ resource.fileLabel }}</div>
                <div class="resource-desc">{{ resource.description }}</div>

                <div class="resource-actions">
                  <el-button
                    v-if="resource.file?.id"
                    link
                    type="primary"
                    @click="openResource(resource)"
                  >
                    下载文件
                  </el-button>
                </div>
              </article>
            </div>

            <div class="context-grid">
              <div class="context-item">
                <div class="context-label">Accession</div>
                <div class="context-value">{{ accessionDetail.accession || '-' }}</div>
              </div>
              <div class="context-item">
                <div class="context-label">Assembly</div>
                <div class="context-value">
                  {{ currentAssembly?.name || '-' }}
                  <span v-if="currentAssembly?.is_default" class="context-tag">default</span>
                </div>
              </div>
              <div class="context-item">
                <div class="context-label">Annotation</div>
                <div class="context-value">
                  {{ currentAnnotation?.name || 'No annotation' }}
                  <span v-if="currentAnnotation?.is_default" class="context-tag">default</span>
                </div>
              </div>
              <div class="context-item">
                <div class="context-label">Assembly Files</div>
                <div class="context-value">{{ currentAssembly?.files?.length || 0 }}</div>
              </div>
              <div class="context-item">
                <div class="context-label">Annotation Files</div>
                <div class="context-value">{{ currentAnnotation?.files?.length || 0 }}</div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <div v-else class="empty-state">
        <el-empty description="未获取到 accession 数据" />
      </div>
    </div>
  </div>
</template>

<script>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Refresh, Search } from '@element-plus/icons-vue';
import { useRoute, useRouter } from 'vue-router';

const TRANSCRIPTOME_CATEGORIES = [
  'transcriptome.all',
  'transcriptome.root',
  'transcriptome.stem',
  'transcriptome.leaf',
  'transcriptome.panicles',
  'transcriptome.shoot'
];

const RECENT_ACCESSIONS_KEY = 'recent_accessions';

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

export default {
  name: 'AccessionCard',
  components: {
    Refresh,
    Search
  },
  setup() {
    const route = useRoute();
    const router = useRouter();

    const loading = ref(false);
    const loadingOrganisms = ref(false);
    const selectedAccession = ref('');
    const organismOptions = ref([]);
    const recentAccessions = ref([]);
    const accessionDetail = ref(null);
    const assemblies = ref([]);
    const summary = ref({});
    const errorMessage = ref('');
    const loadedAccession = ref('');
    const selectedAssemblyId = ref(null);
    const selectedAnnotationId = ref(null);
    const isReplacingRoute = ref(false);
    const hierarchyGraphRef = ref(null);
    const accessionNodeRef = ref(null);
    const hierarchySvgSize = ref({ width: 0, height: 0 });
    const hierarchyLinePaths = ref([]);
    const assemblyNodeRefs = new Map();
    const annotationNodeRefs = new Map();
    let hierarchyLineFrame = 0;

    const routeAccession = computed(() => {
      return normalizeQueryValue(route.query.accession) || normalizeQueryValue(route.query.organism);
    });

    const currentAssembly = computed(() => {
      return assemblies.value.find((item) => matchesId(item, selectedAssemblyId.value)) || null;
    });

    const currentAnnotation = computed(() => {
      const annotations = currentAssembly.value?.annotations || [];
      return annotations.find((item) => matchesId(item, selectedAnnotationId.value)) || null;
    });

    const currentContextSummary = computed(() => {
      const parts = [
        accessionDetail.value?.accession || routeAccession.value,
        currentAssembly.value?.name,
        currentAnnotation.value?.name
      ].filter(Boolean);

      return parts.join(' / ');
    });

    const locationLabel = computed(() => {
      const parts = [
        accessionDetail.value?.country,
        accessionDetail.value?.region
      ].filter((item) => String(item || '').trim());

      return parts.length ? parts.join(' / ') : '-';
    });

    const subPopulationTagClass = computed(() => {
      const value = String(accessionDetail.value?.sub_population || '').trim().toLowerCase();

      if (!value) {
        return 'sub-pop-unknown';
      }

      if (value === 'ca') {
        return 'sub-pop-ca';
      }

      if (value === 'cb') {
        return 'sub-pop-cb';
      }

      if (value === 'gj' || value.includes('japonica') || value.includes('geng')) {
        return 'sub-pop-gj';
      }

      if (value === 'xi' || value.includes('indica')) {
        return 'sub-pop-xi';
      }

      if (value === 'wild') {
        return 'sub-pop-wild';
      }

      if (value === 'o.glaberrima') {
        return 'sub-pop-glaberrima';
      }

      if (value === 'unknown' || value === '未知亚群') {
        return 'sub-pop-unknown';
      }

      return 'sub-pop-default';
    });

    const formatFeatureTypePreview = (value) => {
      const text = String(value || '').trim();
      if (!text || text === '-') {
        return '-';
      }

      const priority = [
        'gene',
        'mRNA',
        'exon',
        'CDS',
        'transcript',
        'five_prime_UTR',
        'three_prime_UTR'
      ];

      const parts = Array.from(new Set(
        text
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean)
      ));

      const sortedParts = parts.slice().sort((left, right) => {
        const leftIndex = priority.indexOf(left);
        const rightIndex = priority.indexOf(right);
        const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex;
        const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex;

        if (normalizedLeft !== normalizedRight) {
          return normalizedLeft - normalizedRight;
        }

        return left.localeCompare(right);
      }).slice(0, 3);

      return sortedParts.length ? sortedParts.join(',') : '-';
    };

    const assemblyCount = computed(() => assemblies.value.length || 0);
    const annotationCount = computed(() => assemblies.value
      .reduce((sum, assembly) => sum + ((assembly?.annotations || []).length), 0));
    const assemblyNames = computed(() => assemblies.value
      .map((assembly) => assembly?.name)
      .filter(Boolean));
    const annotationNames = computed(() => assemblies.value
      .flatMap((assembly) => assembly?.annotations || [])
      .map((annotation) => annotation?.name)
      .filter(Boolean));
    const assemblyTooltipEntries = computed(() => assemblies.value.slice(0, 3).map((assembly) => {
      return {
        id: assembly?.id ?? assembly?.name ?? Math.random(),
        name: assembly?.display_name || assembly?.name || '-',
        bioProject: assembly?.bio_project || '-'
      };
    }));
    const annotationTooltipEntries = computed(() => assemblies.value.flatMap((assembly) => {
      return (assembly?.annotations || []).map((annotation) => ({
        id: annotation?.id ?? `${assembly?.id || 'assembly'}-${annotation?.name || 'annotation'}`,
        name: annotation?.display_name || annotation?.name || '-',
        featureTypes: formatFeatureTypePreview(annotation?.feature_types_summary),
        source: annotation?.source_name || annotation?.source_summary || '-'
      }));
    }).slice(0, 3));

    const goToDataOverview = () => {
      const accession = accessionDetail.value?.accession || selectedAccession.value;
      if (!accession) return;
      router.push({ name: 'home', query: { accession } });
    };

    const goToAccessionMap = () => {
      const accession = accessionDetail.value?.accession || selectedAccession.value;
      if (!accession) return;
      router.push({ name: 'accession-map', query: { accession } });
    };

    const goToDetailTable = (focus = '') => {
      const accession = accessionDetail.value?.accession || selectedAccession.value;
      if (!accession) return;
      const query = { accession };
      if (focus) {
        query.focus = focus;
      }
      router.push({ name: 'accession-detail', query });
    };

    const findFirstDownloadableFile = (files, categories) => {
      const categorySet = new Set(categories);
      const matchedFiles = (files || []).filter((file) => {
        return categorySet.has(file?.category) && Number(file?.size) > 0;
      });

      return matchedFiles[0] || null;
    };

    const buildNodeKey = (...parts) => parts.map((part) => String(part)).join(':');

    const setAssemblyNodeRef = (assemblyId, element) => {
      const key = buildNodeKey('assembly', assemblyId);
      if (element) {
        assemblyNodeRefs.set(key, element);
      } else {
        assemblyNodeRefs.delete(key);
      }
    };

    const setAnnotationNodeRef = (assemblyId, annotationId, element) => {
      const key = buildNodeKey('annotation', assemblyId, annotationId);
      if (element) {
        annotationNodeRefs.set(key, element);
      } else {
        annotationNodeRefs.delete(key);
      }
    };

    const getElementAnchor = (element, graphRect, side) => {
      if (!element || !graphRect) {
        return null;
      }

      const rect = element.getBoundingClientRect();
      const x = side === 'left' ? rect.left - graphRect.left : rect.right - graphRect.left;
      const y = rect.top - graphRect.top + rect.height / 2;
      return { x, y };
    };

    const buildOrthogonalPath = (start, end) => {
      const distance = Math.max(end.x - start.x, 0);
      const turnX = start.x + Math.min(96, Math.max(42, distance * 0.42));
      const radius = Math.min(16, Math.max(8, Math.abs(end.y - start.y) * 0.28), Math.max((end.x - turnX) / 2, 8));

      if (Math.abs(end.y - start.y) <= 2) {
        return `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
      }

      const verticalDirection = end.y > start.y ? 1 : -1;
      const firstY = start.y + radius * verticalDirection;
      const secondY = end.y - radius * verticalDirection;

      return [
        `M ${start.x} ${start.y}`,
        `L ${turnX - radius} ${start.y}`,
        `Q ${turnX} ${start.y} ${turnX} ${firstY}`,
        `L ${turnX} ${secondY}`,
        `Q ${turnX} ${end.y} ${turnX + radius} ${end.y}`,
        `L ${end.x} ${end.y}`
      ].join(' ');
    };

    const updateHierarchyLines = () => {
      const graphElement = hierarchyGraphRef.value;
      const accessionElement = accessionNodeRef.value;

      if (!graphElement || !accessionElement || typeof window === 'undefined' || window.innerWidth <= 1200) {
        hierarchySvgSize.value = { width: 0, height: 0 };
        hierarchyLinePaths.value = [];
        return;
      }

      const graphRect = graphElement.getBoundingClientRect();
      const svgWidth = Math.ceil(Math.max(graphRect.width, graphElement.scrollWidth || 0));
      const svgHeight = Math.ceil(Math.max(graphRect.height, graphElement.scrollHeight || 0));

      if (!svgWidth || !svgHeight) {
        hierarchySvgSize.value = { width: 0, height: 0 };
        hierarchyLinePaths.value = [];
        return;
      }

      const rootAnchor = getElementAnchor(accessionElement, graphRect, 'right');
      const lines = [];

      assemblies.value.forEach((assembly) => {
        const assemblyElement = assemblyNodeRefs.get(buildNodeKey('assembly', assembly.id));
        const assemblyStart = rootAnchor;
        const assemblyEnd = getElementAnchor(assemblyElement, graphRect, 'left');

        if (assemblyStart && assemblyEnd) {
          lines.push({
            key: `accession-${assembly.id}`,
            path: buildOrthogonalPath(assemblyStart, assemblyEnd),
            active: matchesId(assembly, selectedAssemblyId.value)
          });
        }

        (assembly.annotations || []).forEach((annotation) => {
          const annotationElement = annotationNodeRefs.get(
            buildNodeKey('annotation', assembly.id, annotation.id)
          );
          const annotationStart = getElementAnchor(assemblyElement, graphRect, 'right');
          const annotationEnd = getElementAnchor(annotationElement, graphRect, 'left');

          if (annotationStart && annotationEnd) {
            lines.push({
              key: `assembly-${assembly.id}-annotation-${annotation.id}`,
              path: buildOrthogonalPath(annotationStart, annotationEnd),
              active:
                matchesId(assembly, selectedAssemblyId.value) &&
                matchesId(annotation, selectedAnnotationId.value)
            });
          }
        });
      });

      hierarchySvgSize.value = {
        width: svgWidth,
        height: svgHeight
      };
      hierarchyLinePaths.value = lines;
    };

    const scheduleHierarchyLinesUpdate = () => {
      if (typeof window === 'undefined') {
        return;
      }

      if (hierarchyLineFrame) {
        window.cancelAnimationFrame(hierarchyLineFrame);
      }

      nextTick(() => {
        hierarchyLineFrame = window.requestAnimationFrame(() => {
          updateHierarchyLines();
          hierarchyLineFrame = 0;
        });
      });
    };

    const loadRecentAccessions = () => {
      try {
        const raw = localStorage.getItem(RECENT_ACCESSIONS_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        recentAccessions.value = Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        recentAccessions.value = [];
      }
    };

    const saveRecentAccession = (accession) => {
      if (!accession) {
        return;
      }

      const next = [
        accession,
        ...recentAccessions.value.filter((item) => item !== accession)
      ].slice(0, 8);

      recentAccessions.value = next;
      localStorage.setItem(RECENT_ACCESSIONS_KEY, JSON.stringify(next));
    };

    const clearAccessionData = () => {
      accessionDetail.value = null;
      assemblies.value = [];
      summary.value = {};
      errorMessage.value = '';
      loadedAccession.value = '';
      selectedAssemblyId.value = null;
      selectedAnnotationId.value = null;
    };

    const fetchOrganisms = async (query = '') => {
      try {
        loadingOrganisms.value = true;

        if (query) {
          const response = await axios.get(`/files/genome-files/organisms/?search=${encodeURIComponent(query)}`);
          const remoteOptions = response.data || [];
          const merged = [...recentAccessions.value, ...remoteOptions];
          organismOptions.value = Array.from(new Set(merged));
        } else {
          organismOptions.value = recentAccessions.value;
        }
      } catch (error) {
        console.error('获取 accession 列表失败:', error);
        ElMessage.error('获取 accession 列表失败');
      } finally {
        loadingOrganisms.value = false;
      }
    };

    const searchOrganisms = (query) => {
      if (query && query.length >= 2) {
        fetchOrganisms(query);
      } else {
        organismOptions.value = recentAccessions.value;
      }
    };

    const handleSearchVisibleChange = (visible) => {
      if (visible) {
        organismOptions.value = recentAccessions.value;
      }
    };

    const buildNormalizedQuery = (accession, assembly, annotation) => {
      const query = {};
      if (accession) {
        query.accession = accession;
      }
      if (assembly?.id) {
        query.assembly = String(assembly.id);
      }
      if (annotation?.id) {
        query.annotation = String(annotation.id);
      }
      return query;
    };

    const replaceRouteQuery = async (query) => {
      const currentAccession = normalizeQueryValue(route.query.accession);
      const currentAssembly = normalizeQueryValue(route.query.assembly);
      const currentAnnotation = normalizeQueryValue(route.query.annotation);
      const targetAccession = normalizeQueryValue(query.accession);
      const targetAssembly = normalizeQueryValue(query.assembly);
      const targetAnnotation = normalizeQueryValue(query.annotation);
      const routeHasLegacyOrganism = Boolean(normalizeQueryValue(route.query.organism));

      const isSameQuery =
        currentAccession === targetAccession &&
        currentAssembly === targetAssembly &&
        currentAnnotation === targetAnnotation &&
        !routeHasLegacyOrganism;

      if (isSameQuery) {
        return;
      }

      isReplacingRoute.value = true;
      try {
        await router.replace({
          path: route.path,
          query
        });
      } finally {
        isReplacingRoute.value = false;
      }
    };

    const pickAssembly = (requestedAssemblyId) => {
      if (!assemblies.value.length) {
        return null;
      }

      return (
        assemblies.value.find((item) => matchesId(item, requestedAssemblyId)) ||
        assemblies.value.find((item) => item.is_default) ||
        assemblies.value[0]
      );
    };

    const pickAnnotation = (assembly, requestedAnnotationId) => {
      if (!assembly?.annotations?.length) {
        return null;
      }

      return (
        assembly.annotations.find((item) => matchesId(item, requestedAnnotationId)) ||
        assembly.annotations.find((item) => item.is_default) ||
        assembly.annotations[0]
      );
    };

    const applyContextSelection = async () => {
      const assembly = pickAssembly(route.query.assembly);
      const annotation = pickAnnotation(assembly, route.query.annotation);

      selectedAssemblyId.value = assembly?.id ?? null;
      selectedAnnotationId.value = annotation?.id ?? null;

      await replaceRouteQuery(
        buildNormalizedQuery(routeAccession.value, assembly, annotation)
      );
    };

    const fetchAccessionDetail = async (accession) => {
      if (!accession) {
        clearAccessionData();
        return;
      }

      try {
        loading.value = true;
        errorMessage.value = '';

        const response = await axios.get(`/files/accessions/${accession}/`);

        if (!response.data?.success) {
          throw new Error(response.data?.message || '接口返回失败');
        }

        const data = response.data.data || {};
        accessionDetail.value = data.accession || null;
        assemblies.value = data.assemblies || [];
        summary.value = data.summary || {};
        loadedAccession.value = accession;
        selectedAccession.value = accession;

        if (!accessionDetail.value) {
          errorMessage.value = '未获取到 accession 详情';
        }
      } catch (error) {
        console.error('获取 accession 详情失败:', error);
        clearAccessionData();
        errorMessage.value = '获取 accession 详情失败';
        ElMessage.error('获取 accession 详情失败');
      } finally {
        loading.value = false;
      }
    };

    const syncFromRoute = async () => {
      const accession = routeAccession.value;
      selectedAccession.value = accession;

      if (!accession) {
        clearAccessionData();
        return;
      }

      saveRecentAccession(accession);

      if (loadedAccession.value !== accession || !accessionDetail.value) {
        await fetchAccessionDetail(accession);
      }

      if (accessionDetail.value) {
        await applyContextSelection();
      }
    };

    const handleAccessionChange = async (value) => {
      const accession = value || '';
      selectedAccession.value = accession;

      if (!accession) {
        clearAccessionData();
        await replaceRouteQuery({});
        return;
      }

      saveRecentAccession(accession);
      await replaceRouteQuery({ accession });
      await syncFromRoute();
    };

    const refreshPage = async () => {
      if (!routeAccession.value) {
        clearAccessionData();
        return;
      }

      await fetchAccessionDetail(routeAccession.value);
      if (accessionDetail.value) {
        await applyContextSelection();
      }
    };

    const selectAssembly = async (assemblyId) => {
      const assembly = assemblies.value.find((item) => matchesId(item, assemblyId));
      if (!assembly) {
        return;
      }

      const annotation = pickAnnotation(assembly, null);
      selectedAssemblyId.value = assembly.id;
      selectedAnnotationId.value = annotation?.id ?? null;

      await replaceRouteQuery(
        buildNormalizedQuery(routeAccession.value, assembly, annotation)
      );
    };

    const selectAnnotation = async (assemblyId, annotationId) => {
      const assembly = assemblies.value.find((item) => matchesId(item, assemblyId));
      if (!assembly) {
        return;
      }

      const annotation = assembly.annotations?.find((item) => matchesId(item, annotationId)) || null;
      const nextAnnotation = annotation || pickAnnotation(assembly, null);

      selectedAssemblyId.value = assembly.id;
      selectedAnnotationId.value = nextAnnotation?.id ?? null;

      await replaceRouteQuery(
        buildNormalizedQuery(routeAccession.value, assembly, nextAnnotation)
      );
    };

    const openGenomeCard = async (assembly) => {
      if (!routeAccession.value || !assembly?.id) {
        return;
      }

      await router.push({
        name: 'genome-card',
        query: {
          accession: routeAccession.value,
          assembly: String(assembly.id)
        }
      });
    };

    const openAnnotationCard = async (assembly, annotation) => {
      if (!routeAccession.value || !assembly?.id || !annotation?.id) {
        return;
      }

      await router.push({
        name: 'annotation-card',
        query: {
          accession: routeAccession.value,
          assembly: String(assembly.id),
          annotation: String(annotation.id)
        }
      });
    };

    const summaryCards = computed(() => {
      return [
        {
          key: 'assembly',
          label: 'Assembly',
          value: summary.value?.assembly_count ?? 0
        },
        {
          key: 'annotation',
          label: 'Annotation',
          value: summary.value?.annotation_count ?? 0
        },
        {
          key: 'file',
          label: 'File',
          value: summary.value?.file_count ?? 0
        }
      ];
    });

    const resourceCards = computed(() => {
      const currentAccession = accessionDetail.value?.accession || routeAccession.value;
      const currentAssemblyId = currentAssembly.value?.id ? String(currentAssembly.value.id) : '';
      const currentAnnotationId = currentAnnotation.value?.id ? String(currentAnnotation.value.id) : '';
      const genomeFile = findFirstDownloadableFile(currentAssembly.value?.files, ['genome']);
      const annotationFile = findFirstDownloadableFile(currentAnnotation.value?.files, ['annotation']);
      const transcriptomeFile = findFirstDownloadableFile(currentAssembly.value?.files, TRANSCRIPTOME_CATEGORIES);
      const coreBlocksFile = findFirstDownloadableFile(currentAssembly.value?.files, ['coreBlocks']);
      const hasCoordinates =
        Number.isFinite(Number(accessionDetail.value?.longitude)) &&
        Number.isFinite(Number(accessionDetail.value?.latitude));

      return [
        {
          key: 'transcriptome',
          title: 'Transcriptome',
          enabled: Boolean(currentAccession),
          scopeLabel: 'Assembly-level',
          fileLabel: transcriptomeFile?.name || (currentAssembly.value?.name ? `Current assembly: ${currentAssembly.value.name}` : '-'),
          description: 'Open transcriptome resources for the current accession',
          routeName: 'transcriptome',
          query: currentAccession ? { accession: currentAccession } : {},
          file: transcriptomeFile,
          downloadLabel: transcriptomeFile ? 'Download' : ''
        },
        {
          key: 'geographic',
          title: 'Geographic Distribution',
          enabled: Boolean(currentAccession && hasCoordinates),
          scopeLabel: 'Accession-level',
          fileLabel: hasCoordinates
            ? `Coordinates: ${accessionDetail.value.longitude}, ${accessionDetail.value.latitude}`
            : 'No geographic coordinates',
          description: 'Open the map view filtered to the current accession',
          routeName: 'accession-map',
          query: currentAccession ? { accession: currentAccession } : {},
          file: null,
          downloadLabel: ''
        },
        {
          key: 'genome',
          title: 'Genome',
          enabled: Boolean(currentAccession && currentAssemblyId),
          scopeLabel: 'Assembly-level',
          fileLabel: genomeFile?.name || (currentAssembly.value?.name ? `Current assembly: ${currentAssembly.value.name}` : '-'),
          description: 'Open the genome view for the current assembly',
          routeName: 'genome-card',
          query: currentAccession && currentAssemblyId
            ? { accession: currentAccession, assembly: currentAssemblyId }
            : {},
          file: genomeFile,
          downloadLabel: genomeFile ? 'Download' : ''
        },
        {
          key: 'annotation',
          title: 'Annotation',
          enabled: Boolean(currentAccession && currentAssemblyId && currentAnnotationId),
          scopeLabel: 'Annotation-level',
          fileLabel: annotationFile?.name || (currentAnnotation.value?.name ? `Current annotation: ${currentAnnotation.value.name}` : '-'),
          description: 'Open the annotation view for the current annotation',
          routeName: 'annotation-card',
          query: currentAccession && currentAssemblyId && currentAnnotationId
            ? {
                accession: currentAccession,
                assembly: currentAssemblyId,
                annotation: currentAnnotationId
              }
            : {},
          file: annotationFile,
          downloadLabel: annotationFile ? 'Download' : ''
        },
        {
          key: 'core-variable',
          title: 'Core / Variable Blocks',
          enabled: Boolean(currentAccession && currentAssemblyId),
          scopeLabel: 'Assembly-level',
          fileLabel: coreBlocksFile?.name || (currentAssembly.value?.name ? `Assembly context: ${currentAssembly.value.name}` : '-'),
          description: 'Open core and variable block analysis for the current assembly',
          routeName: 'core-variable-blocks-card',
          query: currentAccession && currentAssemblyId
            ? { accession: currentAccession, assembly: currentAssemblyId }
            : {},
          file: coreBlocksFile,
          downloadLabel: coreBlocksFile ? 'Download' : ''
        },
        {
          key: 'codon',
          title: 'Codon',
          enabled: Boolean(currentAccession),
          scopeLabel: 'Accession-level',
          fileLabel: currentAccession ? `Current accession: ${currentAccession}` : '-',
          description: 'Open codon usage analysis for the current accession',
          routeName: 'codon-card',
          query: currentAccession ? { accession: currentAccession } : {},
          file: null,
          downloadLabel: ''
        }
      ];
    });

    const isCurrentAssembly = (assembly) => matchesId(assembly, selectedAssemblyId.value);
    const isCurrentAnnotation = (annotation) => matchesId(annotation, selectedAnnotationId.value);
    const isSelectedAnnotation = (assembly, annotation) => {
      return isCurrentAssembly(assembly) && matchesId(annotation, selectedAnnotationId.value);
    };

    const downloadFile = (file) => {
      if (!file?.id) {
        ElMessage.error('文件缺少下载标识');
        return;
      }

      const baseApiUrl = (axios.defaults.baseURL || '/gd/api').replace(/\/$/, '');
      const downloadUrl = `${baseApiUrl}/files/genome-files/${file.id}/download/`;
      window.open(downloadUrl, '_blank');
    };

    const openResource = async (resource) => {
      if (!resource?.enabled || !resource?.routeName) {
        return;
      }

      await router.push({
        name: resource.routeName,
        query: resource.query || {}
      });
    };

    watch(
      () => [
        route.query.accession,
        route.query.organism,
        route.query.assembly,
        route.query.annotation
      ],
      async () => {
        if (isReplacingRoute.value) {
          return;
        }
        await syncFromRoute();
      },
      { immediate: true }
    );

    watch(
      () => [assemblies.value, selectedAssemblyId.value, selectedAnnotationId.value],
      () => {
        scheduleHierarchyLinesUpdate();
      },
      { deep: true }
    );

    onMounted(() => {
      loadRecentAccessions();
      window.addEventListener('resize', scheduleHierarchyLinesUpdate);
      scheduleHierarchyLinesUpdate();
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', scheduleHierarchyLinesUpdate);
      if (hierarchyLineFrame && typeof window !== 'undefined') {
        window.cancelAnimationFrame(hierarchyLineFrame);
      }
    });

    return {
      accessionDetail,
      accessionNodeRef,
      assemblies,
      assemblyTooltipEntries,
      annotationTooltipEntries,
      currentAnnotation,
      currentAssembly,
      currentContextSummary,
      locationLabel,
      subPopulationTagClass,
      assemblyCount,
      annotationCount,
      assemblyNames,
      annotationNames,
      downloadFile,
      errorMessage,
      handleAccessionChange,
      handleSearchVisibleChange,
      hierarchyGraphRef,
      hierarchyLinePaths,
      hierarchySvgSize,
      isCurrentAnnotation,
      isCurrentAssembly,
      isSelectedAnnotation,
      loading,
      loadingOrganisms,
      openAnnotationCard,
      openGenomeCard,
      openResource,
      organismOptions,
      refreshPage,
      resourceCards,
      searchOrganisms,
      selectedAccession,
      setAnnotationNodeRef,
      setAssemblyNodeRef,
      selectAnnotation,
      selectAssembly,
      goToDataOverview,
      goToAccessionMap,
      goToDetailTable,
      summary,
      summaryCards
    };
  }
};
</script>

<style scoped>
.accession-card-view {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1a56db;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.search-container {
  margin-bottom: 24px;
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  padding: 0 16px;
  max-width: 420px;
}

.search-icon {
  color: #606266;
  margin-right: 8px;
  flex-shrink: 0;
}

.search-select {
  flex-grow: 1;
  min-width: 220px;
}

.data-card {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 24px;
}

.loading {
  padding: 20px;
}

.empty-state {
  padding: 48px 20px;
}

.content-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.top-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(520px, 1fr);
  gap: 24px;
}

.main-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
}

.panel {
  background: #ffffff;
  border: 1px solid #eef2f7;
  border-radius: 12px;
  padding: 20px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1a56db;
}

.panel-subtitle {
  color: #6b7280;
  font-size: 13px;
  margin-top: 6px;
}

.panel-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef4ff;
  color: #1a56db;
  font-size: 12px;
  font-weight: 600;
}

.detail-table-button {
  border-radius: 999px;
}

.info-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: grid;
  gap: 12px;
}

.info-row-2 {
  grid-template-columns: 3fr 1fr;
}

.info-row-4 {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.info-row-3 {
  grid-template-columns: 1fr 1.4fr 2fr;
}

.info-row-1 {
  grid-template-columns: 1fr;
}

.info-panel {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e3e8f6;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.06);
}

.context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.info-item,
.context-item {
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  border-radius: 12px;
  border: 1px solid #e3e8f6;
  padding: 10px 12px;
  min-height: 64px;
}

.info-item {
  grid-column: auto;
}

.context-panel-bottom .context-grid {
  grid-template-columns: 1fr;
  gap: 12px;
}

.context-panel-bottom .context-item {
  min-height: 64px;
  padding: 12px 14px;
}

.info-item-wide {
  grid-column: auto;
}

.info-item-compact {
  grid-column: auto;
}

.info-item-tall {
  min-height: 96px;
}

.info-item-compact-tight {
  min-height: 70px;
}

.info-item-list {
  min-height: 96px;
}

.info-item-list-narrow {
  min-height: 96px;
}

.info-item-list-medium {
  min-height: 96px;
}

.info-item-list-wide {
  min-height: 96px;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-list-item {
  font-size: 13px;
  color: #1a56db;
  line-height: 1.4;
  word-break: break-word;
  margin-bottom: 4px;
}

.info-list-empty {
  font-size: 13px;
  color: #9ca3af;
}

.info-item-summary {
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease, transform 0.18s ease;
  cursor: pointer;
}

.info-item-summary:hover,
.info-item-summary:focus-within {
  border-color: #8fb2f0;
  box-shadow: 0 12px 26px rgba(37, 99, 235, 0.12);
  background: linear-gradient(180deg, #eef5ff 0%, #ffffff 100%);
  transform: translateY(-1px);
}

.summary-card-trigger {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
}

.summary-interactive-block {
  width: 100%;
  min-height: 0;
  flex: 1;
  border: none;
  border-radius: 0;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 0;
  box-shadow: none;
}

.summary-card-trigger:focus-visible {
  outline: none;
}

.summary-quantity {
  font-size: 16px;
  line-height: 1.5;
  font-weight: 600;
  color: #1a56db;
  text-align: left;
}

:deep(.accession-summary-tooltip),
:deep(.accession-summary-tooltip.el-popper),
:deep(.accession-summary-tooltip.el-popper.is-light),
:deep(.accession-summary-tooltip.el-popper.is-dark) {
  --el-text-color-primary: #1e293b;
  --el-text-color-regular: #475569;
  --el-border-color-light: #e5edf9;
  --el-popover-bg-color: #f8fbff;
  --el-bg-color-overlay: #f8fbff;
  --el-tooltip-bg-color: #f8fbff;
  color: #1e293b;
  max-width: 420px;
  padding: 12px 14px;
  border-radius: 12px !important;
  border: 1px solid #e5edf9;
  box-shadow: 0 14px 30px rgba(59, 130, 246, 0.10);
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 72%, #eef5ff 100%);
  overflow: hidden;
}

:deep(.accession-summary-tooltip.el-popper[data-popper-placement^='bottom']),
:deep(.accession-summary-tooltip.el-popper.is-light[data-popper-placement^='bottom']),
:deep(.accession-summary-tooltip.el-popper.is-dark[data-popper-placement^='bottom']) {
  background: linear-gradient(180deg, #eef5ff 0%, #f8fbff 28%, #ffffff 100%);
}

:deep(.accession-summary-tooltip.el-popper[data-popper-placement^='left']),
:deep(.accession-summary-tooltip.el-popper.is-light[data-popper-placement^='left']),
:deep(.accession-summary-tooltip.el-popper.is-dark[data-popper-placement^='left']) {
  background: linear-gradient(90deg, #ffffff 0%, #f8fbff 70%, #eef5ff 100%);
}

:deep(.accession-summary-tooltip.el-popper[data-popper-placement^='right']),
:deep(.accession-summary-tooltip.el-popper.is-light[data-popper-placement^='right']),
:deep(.accession-summary-tooltip.el-popper.is-dark[data-popper-placement^='right']) {
  background: linear-gradient(90deg, #eef5ff 0%, #f8fbff 30%, #ffffff 100%);
}

:deep(.accession-summary-tooltip .el-popper__arrow::before),
:deep(.accession-summary-tooltip.el-popper .el-popper__arrow::before),
:deep(.accession-summary-tooltip.el-popper.is-light .el-popper__arrow::before),
:deep(.accession-summary-tooltip.el-popper.is-dark .el-popper__arrow::before) {
  background: #eef5ff;
  border: 1px solid #e5edf9;
  box-sizing: border-box;
}

.summary-tooltip {
  min-width: 280px;
  max-width: 380px;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 6px 0 0;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.55);
}

.summary-tooltip-row {
  display: grid;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: transparent;
  border: none;
  border-radius: 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.85);
}

.summary-tooltip-row-2 {
  grid-template-columns: minmax(150px, 1.5fr) minmax(110px, 1fr);
}

.summary-tooltip-row-3 {
  grid-template-columns: minmax(150px, 1.4fr) minmax(110px, 1fr) minmax(96px, 0.95fr);
}

.summary-tooltip-row:last-of-type {
  border-bottom: none;
}

.summary-tooltip-cell {
  min-width: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
  word-break: break-word;
}

.summary-tooltip-cell-primary {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.summary-tooltip-cell-mono {
  font-family: 'SF Mono', Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  color: #334155;
}

.summary-tooltip-footer {
  margin-top: 0;
  padding: 10px 14px 6px;
  border-radius: 0;
  background: transparent;
  border: none;
  border-top: 1px solid rgba(226, 232, 240, 0.85);
  color: #3b82f6;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.summary-tooltip-footer-icon {
  font-size: 12px;
  line-height: 1;
}

.inline-link {
  appearance: none;
  border: none;
  background: none;
  padding: 0;
  margin: 0;
  cursor: pointer;
  color: #1a56db;
  font-weight: 600;
  text-align: left;
}

.inline-link:hover {
  text-decoration: underline;
}

.location-link {
  margin-top: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #2563eb;
}

.info-label,
.context-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.info-value,
.context-value {
  color: #111827;
  line-height: 1.5;
  word-break: break-word;
}

.seq-link {
  color: #1a56db;
  text-decoration: none;
}

.seq-link:hover {
  text-decoration: underline;
}

.context-tag,
.status-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 8px;
}

.status-default,
.context-tag {
  color: #1d4ed8;
  background: #dbeafe;
}

.status-current {
  color: #1d4ed8;
  background: #e0ecff;
}

.sub-population-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.sub-pop-ca {
  background-color: #e0f2fe;
  color: #0369a1;
}

.sub-pop-cb {
  background-color: #fef3c7;
  color: #d97706;
}

.sub-pop-gj {
  background-color: #ecfdf5;
  color: #059669;
}

.sub-pop-xi {
  background-color: #f3f0ff;
  color: #7c3aed;
}

.sub-pop-wild {
  background-color: #fef2f2;
  color: #dc2626;
}

.sub-pop-glaberrima {
  background-color: #fdf4ff;
  color: #c026d3;
}

.sub-pop-unknown {
  background-color: #f3f4f6;
  color: #6b7280;
}

.sub-pop-default {
  background-color: #f9fafb;
  color: #6b7280;
}

.hierarchy-header {
  align-items: center;
}

.hierarchy-current-summary {
  margin-top: 10px;
  font-size: 13px;
  color: #5f7c78;
  font-weight: 600;
}

.hierarchy-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.legend-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 100px;
  padding: 8px 14px;
  border: 1px solid #d7e7e7;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  color: #476168;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
}

.legend-accession {
  background: #dfeaff;
  border-color: #9bbcff;
  color: #234f9a;
}

.legend-assembly {
  background: #edf4ff;
  border-color: #b7cdfa;
  color: #3b6cae;
}

.legend-annotation {
  background: #f6f9ff;
  border-color: #d5e2fb;
  color: #5b7eaf;
}

.hierarchy-graph {
  position: relative;
  display: grid;
  grid-template-columns: minmax(160px, 220px) minmax(0, 1fr);
  gap: 24px;
  align-items: stretch;
  padding: 8px 0;
}

.hierarchy-lines {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: visible;
  z-index: 0;
}

.hierarchy-line {
  fill: none;
  stroke: #9fb4d6;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: stroke 0.18s ease, stroke-width 0.18s ease, opacity 0.18s ease;
}

.hierarchy-line-muted {
  opacity: 0.52;
}

.hierarchy-line-active {
  stroke: #285ea8;
  stroke-width: 3.4;
  opacity: 1;
}

.accession-lane {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}

.branch-lane {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-left: 34px;
  position: relative;
  z-index: 1;
}

.assembly-branch {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 24px;
}

.assembly-main-column {
  position: relative;
  flex: 0 0 auto;
}

.assembly-row,
.annotation-row {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
  z-index: 1;
}

.annotation-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-left: 0;
  padding-left: 34px;
  padding-top: 2px;
  position: relative;
  z-index: 1;
}

.hierarchy-node {
  border: 1px solid #d8e4f5;
  border-radius: 16px;
  padding: 12px 16px;
  background: #ffffff;
  text-align: left;
  box-shadow: 0 10px 24px rgba(31, 67, 122, 0.06);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease,
    background-color 0.18s ease,
    opacity 0.18s ease,
    filter 0.18s ease;
}

.accession-node {
  width: 100%;
  background: linear-gradient(180deg, #e4edff 0%, #d8e6ff 100%);
  border-color: #96b6f2;
}

.assembly-node,
.annotation-node {
  cursor: pointer;
}

.assembly-node {
  flex: 0 0 320px;
  background: linear-gradient(180deg, #eff5ff 0%, #e6f0ff 100%);
  border-color: #b7cdfa;
}

.annotation-node {
  flex: 0 0 340px;
  background: linear-gradient(180deg, #fafcff 0%, #f4f8ff 100%);
  border-color: #d5e2fb;
}

.assembly-branch-inactive {
  opacity: 0.82;
  filter: saturate(0.92);
}

.assembly-branch-inactive .assembly-node,
.assembly-branch-inactive .annotation-node {
  box-shadow: 0 8px 18px rgba(31, 67, 122, 0.04);
}

.annotation-row-muted {
  opacity: 0.88;
}

.assembly-node:hover,
.assembly-node:focus-visible,
.annotation-node:hover,
.annotation-node:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 18px 34px rgba(31, 67, 122, 0.14);
  outline: none;
}

.assembly-node:hover,
.assembly-node:focus-visible {
  border-color: #5b90e6;
}

.annotation-node:hover,
.annotation-node:focus-visible {
  border-color: #8cb0ea;
}

.assembly-node-active,
.annotation-node-active,
.assembly-branch-active > .assembly-main-column .assembly-row .assembly-node {
  border-color: #3f7ed8;
  box-shadow: 0 20px 38px rgba(63, 126, 216, 0.18);
}

.assembly-node-active {
  background: linear-gradient(180deg, #e4efff 0%, #dbe9ff 100%);
}

.annotation-node-active {
  background: linear-gradient(180deg, #eef4ff 0%, #e4edff 100%);
}

.annotation-node-muted {
  border-color: #d5e2fb;
}

.node-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.node-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.2;
  word-break: break-word;
}

.assembly-node .node-title {
  color: #2f5f9f;
}

.annotation-node .node-title {
  color: #5273a4;
}

.accession-node .node-title {
  color: #234f9a;
}

.node-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.node-title-stack {
  min-width: 0;
  flex: 1 1 auto;
}

.node-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.node-tags .status-tag {
  margin-left: 0;
}

.node-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-top: 8px;
  color: #687b96;
  font-size: 12px;
}

.node-inline-link {
  border: 0;
  background: transparent;
  padding: 0;
  margin-top: 2px;
  color: #275ea8;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
  white-space: nowrap;
  flex: 0 0 auto;
}

.node-inline-link:hover {
  color: #1e4f8f;
}

.node-inline-link-annotation {
  color: #4f74ab;
}

.node-inline-link-annotation:hover {
  color: #355f9f;
}

.node-route-link {
  border: 0;
  background: transparent;
  color: #2f6f89;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: inset 0 0 0 1px #b7d8e5;
}

.node-route-link:hover {
  background: rgba(143, 201, 222, 0.14);
}

.node-route-link-annotation {
  color: #4f7d65;
  box-shadow: inset 0 0 0 1px #bfd9ca;
}

.node-route-link-annotation:hover {
  background: rgba(167, 212, 185, 0.15);
}

.annotation-ghost {
  margin-left: 86px;
  padding: 10px 14px;
  border-radius: 12px;
  background: #f6f9ff;
  color: #6b7f9b;
  font-size: 13px;
  border: 1px dashed #d5e2fb;
}

.annotation-ghost-inline {
  margin-left: 0;
  margin-top: 6px;
}

.assembly-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.assembly-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  background: #ffffff;
}

.assembly-card-active {
  border-color: #bfdbfe;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
}

.assembly-card-header {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 18px 20px;
  text-align: left;
  cursor: pointer;
}

.assembly-main {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.assembly-title-row,
.annotation-title-row,
.resource-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.assembly-title,
.annotation-title,
.resource-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.assembly-meta,
.annotation-meta,
.resource-scope {
  color: #6b7280;
  font-size: 13px;
}

.annotation-panel {
  border-top: 1px solid #eef2f7;
  padding: 16px 20px 20px;
  background: #fafcff;
}

.annotation-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.annotation-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.annotation-panel-tip {
  color: #6b7280;
  font-size: 12px;
}

.annotation-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.annotation-card {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #ffffff;
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
}

.annotation-card-active {
  border-color: #bfdbfe;
  background: #f8fbff;
}

.annotation-empty,
.hierarchy-empty {
  padding: 12px 0;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.resource-card {
  border-radius: 12px;
  padding: 18px;
  border: 1px solid #e5e7eb;
}

.resource-card-active {
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  border-color: #cfe0ff;
}

.resource-card-disabled {
  background: #f9fafb;
}

.resource-pill {
  font-size: 11px;
  font-weight: 700;
  border-radius: 999px;
  padding: 4px 8px;
  white-space: nowrap;
}

.pill-available {
  color: #1a56db;
  background: #eaf2ff;
}

.pill-unavailable {
  color: #6b7280;
  background: #eceff3;
}

.resource-file {
  color: #374151;
  font-size: 13px;
  margin: 12px 0 10px;
  min-height: 20px;
  word-break: break-word;
}

.resource-desc {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.5;
  min-height: 40px;
}

.resource-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}

@media (max-width: 1200px) {
  .top-grid,
  .main-grid {
    grid-template-columns: 1fr;
  }

  .hierarchy-graph {
    grid-template-columns: 1fr;
    gap: 20px;
  }

  .accession-lane {
    justify-content: flex-start;
  }

  .hierarchy-lines {
    display: none;
  }

  .branch-lane,
  .annotation-column,
  .annotation-ghost {
    padding-left: 0;
    margin-left: 0;
  }

  .assembly-branch {
    flex-direction: column;
    gap: 12px;
  }
}

@media (max-width: 900px) {
  .summary-grid,
  .resource-grid,
  .info-grid,
  .context-grid {
    grid-template-columns: 1fr;
  }

  .info-item,
  .info-item-wide,
  .info-item-compact {
    grid-column: span 1;
  }

  .hierarchy-header,
  .assembly-branch,
  .assembly-row,
  .annotation-row,
  .node-top,
  .node-title-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .hierarchy-legend {
    justify-content: flex-start;
  }

  .legend-chip,
  .assembly-node,
  .annotation-node,
  .node-route-link,
  .node-inline-link {
    width: 100%;
  }

  .annotation-column {
    gap: 14px;
  }
}
</style>

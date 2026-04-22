<template>
  <div class="accession-detail-table-view">
    <div class="page-header">
      <div class="title-block">
        <h2 class="title">Accession</h2>
        <div class="title-accent"></div>
      </div>

      <div class="header-actions">
        <el-button class="back-button" @click="goBackToCard">
          <el-icon><ArrowLeft /></el-icon>
          Back to Accession Card
        </el-button>
        <el-tooltip content="Refresh" placement="top">
          <el-button circle size="small" @click="refreshPage">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <div v-if="routeAccession && !errorMessage" class="toolbar-shell">
      <div class="toolbar">
        <div class="toolbar-item toolbar-item-accession">
            <span class="toolbar-label">Accession</span>
            <span class="toolbar-value">{{ routeAccession }}</span>
          </div>
        <div class="toolbar-divider"></div>
        <div class="toolbar-item toolbar-item-filter">
          <span class="toolbar-label">Assembly</span>
          <el-select
            v-model="selectedAssemblyId"
            class="toolbar-select"
            placeholder="All assemblies"
            clearable
          >
            <el-option label="All assemblies" value="" />
            <el-option
              v-for="entry in assemblyFilterOptions"
              :key="`assembly-option-${entry.id}`"
              :label="entry.displayName"
              :value="String(entry.id)"
            />
          </el-select>
        </div>
        <div class="toolbar-divider"></div>
        <div class="toolbar-item toolbar-item-filter">
          <span class="toolbar-label">Annotation</span>
          <el-select
            v-model="selectedAnnotationId"
            class="toolbar-select"
            placeholder="All annotations"
            clearable
          >
            <el-option label="All annotations" value="" />
            <el-option
              v-for="entry in annotationFilterOptions"
              :key="`annotation-option-${entry.id}`"
              :label="entry.displayName"
              :value="String(entry.id)"
            />
          </el-select>
        </div>
        <div class="toolbar-actions">
          <el-button class="toolbar-action-button" @click="expandAll">Expand All</el-button>
          <el-button class="toolbar-action-button" @click="collapseAll">Collapse All</el-button>
        </div>
      </div>
    </div>

    <div class="data-card">
      <div v-if="loading" class="loading">
        <el-skeleton :rows="14" animated />
      </div>

      <div v-else-if="!routeAccession" class="empty-state">
        <el-empty description="Please select an accession from Accession Card first." />
      </div>

      <div v-else-if="errorMessage" class="empty-state">
        <el-empty :description="errorMessage" />
      </div>

      <div v-else-if="accessionDetail" class="content-shell">
        <div class="content-main">
          <section ref="accessionSummaryRef" :class="['info-section', activeDetailTarget.type === 'accession' ? 'linked-highlight' : '']">
            <div class="section-heading">
              <div>
                <h3 class="section-title">Accession Summary</h3>
              </div>
            </div>

            <div class="accession-grid">
              <div
                v-for="row in accessionRows"
                :key="`accession-${row.label}`"
                :class="['info-row', row.type === 'link' ? 'info-row-wide' : '']"
              >
                <div class="info-label">{{ row.label }}</div>
                <div class="info-value">
                  <template v-if="row.type === 'link' && row.value !== '-'">
                    <a
                      :href="row.value"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="value-link"
                    >
                      {{ row.value }}
                    </a>
                  </template>
                  <template v-else>
                    {{ row.value }}
                  </template>
                </div>
              </div>
            </div>
          </section>

          <section class="info-section">
            <div class="section-heading">
              <div>
                <h3 class="section-title">Assembly</h3>
              </div>
              <span class="section-chip">{{ filteredAssemblyEntries.length }}</span>
            </div>

            <div class="accordion-list">
              <article
                v-for="entry in filteredAssemblyEntries"
                :key="`assembly-entry-${entry.id}`"
                :ref="(el) => setAssemblyCardRef(entry.id, el)"
                :class="['accordion-card', activeDetailTarget.type === 'assembly' && normalizeEntryId(entry.id) === activeDetailTarget.id ? 'linked-highlight' : '']"
              >
                <button type="button" class="accordion-trigger" @click="toggleAssembly(entry.id)">
                  <div class="accordion-main">
                    <span class="accordion-arrow">{{ isAssemblyExpanded(entry.id) ? '-' : '+' }}</span>
                    <span class="accordion-title-text" :title="entry.displayName">{{ entry.displayName }}</span>
                    <span v-if="entry.isDefault" class="default-badge">default</span>
                  </div>
                  <div class="accordion-meta">{{ entry.fileSummary }}</div>
                </button>

                <div v-if="isAssemblyExpanded(entry.id)" class="accordion-body">
                  <div
                    v-for="row in entry.rows"
                    :key="`assembly-${entry.id}-${row.label}`"
                    class="info-row compact"
                  >
                    <div class="info-label">{{ row.label }}</div>
                    <div class="info-value">{{ row.value }}</div>
                  </div>
                </div>
              </article>
            </div>
          </section>

          <section class="info-section">
            <div class="section-heading">
              <div>
                <h3 class="section-title">Annotation</h3>
              </div>
              <span class="section-chip">{{ filteredAnnotationEntries.length }}</span>
            </div>

            <div class="accordion-list">
              <article
                v-for="entry in filteredAnnotationEntries"
                :key="`annotation-entry-${entry.id}`"
                :ref="(el) => setAnnotationCardRef(entry.id, el)"
                :class="['accordion-card', activeDetailTarget.type === 'annotation' && normalizeEntryId(entry.id) === activeDetailTarget.id ? 'linked-highlight' : '']"
              >
                <button type="button" class="accordion-trigger" @click="toggleAnnotation(entry.id)">
                  <div class="accordion-main">
                    <span class="accordion-arrow">{{ isAnnotationExpanded(entry.id) ? '-' : '+' }}</span>
                    <span class="accordion-title-text" :title="entry.displayName">{{ entry.displayName }}</span>
                    <span v-if="entry.isDefault" class="default-badge">default</span>
                  </div>
                  <div class="accordion-meta">
                    <span>{{ entry.fileSummary }}</span>
                    <span v-if="entry.sourceDisplay" class="annotation-assembly">{{ entry.sourceDisplay }}</span>
                  </div>
                </button>

                <div v-if="isAnnotationExpanded(entry.id)" class="accordion-body">
                  <div
                    v-for="row in entry.rows"
                    :key="`annotation-${entry.id}-${row.label}`"
                    class="info-row compact"
                  >
                    <div class="info-label">{{ row.label }}</div>
                    <div class="info-value">
                      <el-button
                        v-if="row.type === 'action'"
                        link
                        type="primary"
                        class="value-action-button"
                        @click="openAnnotationDetail(entry)"
                      >
                        {{ row.value }}
                      </el-button>
                      <template v-else>
                        {{ row.value }}
                      </template>
                    </div>
                  </div>
                </div>
              </article>
            </div>
          </section>
        </div>

        <aside class="structure-shell">
          <section class="structure-card">
            <div class="structure-heading">
              <h3 class="section-title structure-title">Accession Structure</h3>
            </div>

            <div class="structure-legend-row">
              <div class="structure-legend" aria-label="Structure legend">
                <span class="structure-legend-item">
                  <span class="structure-legend-dot structure-legend-dot-accession"></span>
                  Accession
                </span>
                <span class="structure-legend-item">
                  <span class="structure-legend-dot structure-legend-dot-assembly"></span>
                  Assembly
                </span>
                <span class="structure-legend-item">
                  <span class="structure-legend-dot structure-legend-dot-annotation"></span>
                  Annotation
                </span>
              </div>
            </div>

            <div class="structure-tree">
              <div
                class="structure-graph-stage"
                :style="{ width: `${structureGraph.width}px`, minHeight: `${structureGraph.height}px` }"
              >
                <svg
                  class="structure-svg"
                  :viewBox="`0 0 ${structureGraph.width} ${structureGraph.height}`"
                  preserveAspectRatio="xMidYMin meet"
                  aria-hidden="true"
                >
                  <path
                    v-for="edge in structureGraph.edges"
                    :key="edge.key"
                    :d="edge.path"
                    class="structure-edge"
                  />
                </svg>

                <div
                  v-for="node in structureGraph.nodes"
                  :key="node.key"
                  :class="['tree-node-anchor', `label-${node.labelSide}`]"
                  :style="getStructureNodeAnchorStyle(node)"
                >
                  <button
                    type="button"
                    :class="[
                      'tree-node-card',
                      `tree-node-card-${node.type}`,
                      node.active ? 'tree-node-active' : '',
                      node.muted ? 'tree-node-muted' : ''
                    ]"
                    :title="node.label"
                    @click="handleStructureNodeClick(node)"
                  >
                    <span :class="['tree-dot', `tree-dot-${node.type}`]"></span>
                    <span class="tree-label">{{ node.label }}</span>
                  </button>
                </div>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { ArrowLeft, Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';

const normalizeQueryValue = (value) => {
  return value ? String(value).trim() : '';
};

const buildFileSummary = (files) => {
  const count = Array.isArray(files) ? files.length : 0;
  if (!count) {
    return '-';
  }
  return `${count} file${count === 1 ? '' : 's'}`;
};

const normalizeEntryId = (value) => {
  return value === null || value === undefined ? '' : String(value);
};

const clamp = (value, min, max) => {
  return Math.min(Math.max(value, min), max);
};

const distributeNodes = (count, centerX, minX, maxX, preferredGap) => {
  if (count <= 0) {
    return [];
  }

  if (count === 1) {
    return [clamp(centerX, minX, maxX)];
  }

  const span = maxX - minX;
  const requiredSpan = preferredGap * (count - 1);
  const gap = requiredSpan <= span ? preferredGap : span / (count - 1);
  const usedSpan = gap * (count - 1);
  let start = centerX - (usedSpan / 2);

  if (start < minX) {
    start = minX;
  }

  if ((start + usedSpan) > maxX) {
    start = maxX - usedSpan;
  }

  return Array.from({ length: count }, (_, index) => Number((start + (index * gap)).toFixed(2)));
};

const buildBezierPath = (fromX, fromY, toX, toY) => {
  const verticalDistance = Math.max(toY - fromY, 0);
  const curveOffset = Math.max(26, verticalDistance * 0.5);
  return `M ${fromX} ${fromY} C ${fromX} ${fromY + curveOffset}, ${toX} ${toY - curveOffset}, ${toX} ${toY}`;
};

export default {
  name: 'AccessionDetailTableView',
  components: {
    ArrowLeft,
    Refresh
  },
  setup() {
    const route = useRoute();
    const router = useRouter();

    const loading = ref(false);
    const errorMessage = ref('');
    const accessionDetail = ref(null);
    const assemblies = ref([]);
    const selectedAssemblyId = ref('');
    const selectedAnnotationId = ref('');
    const expandedAssemblies = ref([]);
    const expandedAnnotations = ref([]);
    const structureRootExpanded = ref(true);
    const structureExpandedAssemblyId = ref('');
    const activeStructureNode = ref({ type: 'accession', id: 'root' });
    const activeDetailTarget = ref({ type: '', id: '' });
    const accessionSummaryRef = ref(null);
    const assemblyCardRefs = new Map();
    const annotationCardRefs = new Map();
    let highlightTimer = 0;

    const routeAccession = computed(() => {
      return normalizeQueryValue(route.query.accession) || normalizeQueryValue(route.query.organism);
    });

    const accessionRows = computed(() => {
      const detail = accessionDetail.value || {};
      const locationParts = [detail.country, detail.region].filter((item) => String(item || '').trim());

      return [
        { label: 'Name', value: detail.accession || '-' },
        { label: 'Genetic Stock ID', value: detail.genetic_stock_id || '-' },
        { label: 'Country Origin', value: locationParts.length ? locationParts.join(' / ') : '-' },
        { label: 'Subpopulation', value: detail.sub_population || '-' },
        { label: 'Links', value: detail.seq_data || '-', type: detail.seq_data ? 'link' : 'text' }
      ];
    });

    const assemblyEntries = computed(() => {
      if (!assemblies.value.length) {
        return [
          {
            id: 'assembly-empty',
            name: '-',
            displayName: '-',
            isDefault: false,
            fileSummary: '-',
            rows: [
              { label: 'Stander ID', value: '-' },
              { label: 'NCBI BioProject', value: '-' },
              { label: 'Reference', value: '-' },
              { label: 'Files', value: '-' }
            ]
          }
        ];
      }

      return assemblies.value.map((assembly) => ({
        id: assembly.id,
        name: assembly.name || `Assembly ${assembly.id}`,
        displayName: assembly.display_name || assembly.name || `Assembly ${assembly.id}`,
        isDefault: Boolean(assembly.is_default),
        fileSummary: buildFileSummary(assembly.files),
        rows: [
          { label: 'Stander ID', value: assembly.standard_id || '-' },
          { label: 'NCBI BioProject', value: assembly.bio_project || '-' },
          { label: 'Reference', value: assembly.reference || '-' },
          { label: 'Files', value: buildFileSummary(assembly.files) }
        ]
      }));
    });

    const annotationEntries = computed(() => {
      const allAnnotations = assemblies.value.flatMap((assembly) => {
        return (assembly.annotations || []).map((annotation) => ({
          id: annotation.id,
          name: annotation.name || `Annotation ${annotation.id}`,
          displayName: annotation.display_name || annotation.name || `Annotation ${annotation.id}`,
          assemblyId: assembly.id,
          assemblyName: assembly.name || `Assembly ${assembly.id}`,
          isDefault: Boolean(annotation.is_default),
          fileSummary: buildFileSummary(annotation.files),
          sourceDisplay: annotation.source_name || '',
          rows: [
            { label: 'Stander ID', value: annotation.standard_id || annotation.display_name || '-' },
            { label: 'Source', value: annotation.source_name || annotation.source_summary || '-' },
            { label: 'Feature Types', value: annotation.feature_types_summary || '-' },
            { label: 'Chromosomes', value: annotation.chromosomes_summary || '-' },
            { label: 'Coordinate Range', value: annotation.coordinate_range_summary || '-' },
            { label: 'Files', value: buildFileSummary(annotation.files) },
            { label: 'Details', value: 'View Annotation Table', type: 'action' }
          ]
        }));
      });

      if (allAnnotations.length) {
        return allAnnotations;
      }

      return [
        {
          id: 'annotation-empty',
          name: '-',
          displayName: '-',
          assemblyId: '',
          assemblyName: '-',
          isDefault: false,
          fileSummary: '-',
          sourceDisplay: '',
          rows: [
            { label: 'Stander ID', value: '-' },
            { label: 'Source', value: '-' },
            { label: 'Feature Types', value: '-' },
            { label: 'Chromosomes', value: '-' },
            { label: 'Coordinate Range', value: '-' },
            { label: 'Files', value: '-' },
            { label: 'Details', value: '-' }
          ]
        }
      ];
    });

    const structureAssemblies = computed(() => {
      return assemblies.value.map((assembly) => ({
        id: assembly.id,
        displayName: assembly.display_name || assembly.name || `Assembly ${assembly.id}`,
        annotations: (assembly.annotations || []).map((annotation) => ({
          id: annotation.id,
          displayName: annotation.display_name || annotation.name || `Annotation ${annotation.id}`,
          assemblyId: assembly.id
        }))
      }));
    });

    const structureGraph = computed(() => {
      const width = 420;
      const rootY = 52;
      const assemblyY = 136;
      const annotationY = 238;
      const innerMinX = 54;
      const innerMaxX = width - 54;
      const rootX = width / 2;
      const nodes = [];
      const edges = [];
      const rootLabel = accessionDetail.value?.accession || routeAccession.value || '-';

      nodes.push({
        key: 'structure-root',
        type: 'accession',
        id: 'root',
        label: rootLabel,
        x: rootX,
        y: rootY,
        labelSide: 'right',
        active: activeStructureNode.value.type === 'accession',
        muted: false
      });

      if (!structureRootExpanded.value || !structureAssemblies.value.length) {
        return {
          width,
          height: 104,
          nodes,
          edges
        };
      }

      const assemblyXs = distributeNodes(
        structureAssemblies.value.length,
        rootX,
        innerMinX,
        innerMaxX,
        128
      );

      const assemblyNodeById = new Map();
      structureAssemblies.value.forEach((assembly, index) => {
        const normalizedAssemblyId = normalizeEntryId(assembly.id);
        const x = assemblyXs[index] || rootX;
        const labelSide = x <= (width / 2) - 14 ? 'left' : 'right';

        nodes.push({
          key: `structure-assembly-${normalizedAssemblyId}`,
          type: 'assembly',
          id: normalizedAssemblyId,
          label: assembly.displayName,
          x,
          y: assemblyY,
          labelSide,
          active: activeStructureNode.value.type === 'assembly' && activeStructureNode.value.id === normalizedAssemblyId,
          muted: !assembly.annotations.length,
          assembly
        });

        assemblyNodeById.set(normalizedAssemblyId, { x, assembly });
        edges.push({
          key: `edge-root-${normalizedAssemblyId}`,
          path: buildBezierPath(rootX, rootY + 22, x, assemblyY - 22)
        });
      });

      let height = 188;
      const expandedAssemblyId = normalizeEntryId(structureExpandedAssemblyId.value);
      const expandedAssemblyNode = assemblyNodeById.get(expandedAssemblyId);
      const expandedAnnotations = expandedAssemblyNode?.assembly?.annotations || [];

      if (expandedAssemblyNode && expandedAnnotations.length) {
        const annotationXs = distributeNodes(
          expandedAnnotations.length,
          expandedAssemblyNode.x,
          innerMinX,
          innerMaxX,
          112
        );

        expandedAnnotations.forEach((annotation, index) => {
          const normalizedAnnotationId = normalizeEntryId(annotation.id);
          const x = annotationXs[index] || expandedAssemblyNode.x;
          const labelSide = x <= expandedAssemblyNode.x - 10 ? 'left' : 'right';

          nodes.push({
            key: `structure-annotation-${normalizedAnnotationId}`,
            type: 'annotation',
            id: normalizedAnnotationId,
            label: annotation.displayName,
            x,
            y: annotationY,
            labelSide,
            active: activeStructureNode.value.type === 'annotation' && activeStructureNode.value.id === normalizedAnnotationId,
            muted: false,
            annotation,
            assembly: expandedAssemblyNode.assembly
          });

          edges.push({
            key: `edge-${expandedAssemblyId}-${normalizedAnnotationId}`,
            path: buildBezierPath(expandedAssemblyNode.x, assemblyY + 22, x, annotationY - 22)
          });
        });

        height = 292;
      }

      return {
        width,
        height,
        nodes,
        edges
      };
    });

    const assemblyFilterOptions = computed(() => {
      return assemblyEntries.value.filter((entry) => entry.id !== 'assembly-empty');
    });

    const annotationFilterOptions = computed(() => {
      return annotationEntries.value.filter((entry) => entry.id !== 'annotation-empty');
    });

    const filteredAssemblyEntries = computed(() => {
      if (!selectedAssemblyId.value) {
        return assemblyEntries.value;
      }

      return assemblyEntries.value.filter((entry) => normalizeEntryId(entry.id) === selectedAssemblyId.value);
    });

    const filteredAnnotationEntries = computed(() => {
      let entries = annotationEntries.value;

      if (selectedAssemblyId.value) {
        entries = entries.filter((entry) => normalizeEntryId(entry.assemblyId) === selectedAssemblyId.value);
      }

      if (selectedAnnotationId.value) {
        entries = entries.filter((entry) => normalizeEntryId(entry.id) === selectedAnnotationId.value);
      }

      return entries;
    });

    const syncExpandedState = () => {
      const availableAssemblyIds = filteredAssemblyEntries.value
        .map((entry) => normalizeEntryId(entry.id))
        .filter((id) => id && id !== 'assembly-empty');
      const availableAnnotationIds = filteredAnnotationEntries.value
        .map((entry) => normalizeEntryId(entry.id))
        .filter((id) => id && id !== 'annotation-empty');

      expandedAssemblies.value = expandedAssemblies.value.filter((id) => availableAssemblyIds.includes(id));
      expandedAnnotations.value = expandedAnnotations.value.filter((id) => availableAnnotationIds.includes(id));

      if (!expandedAssemblies.value.length && availableAssemblyIds.length) {
        expandedAssemblies.value = [availableAssemblyIds[0]];
      }

      if (!expandedAnnotations.value.length && availableAnnotationIds.length) {
        expandedAnnotations.value = [availableAnnotationIds[0]];
      }
    };

    const isAssemblyExpanded = (id) => {
      return expandedAssemblies.value.includes(normalizeEntryId(id));
    };

    const isAnnotationExpanded = (id) => {
      return expandedAnnotations.value.includes(normalizeEntryId(id));
    };

    const toggleAssembly = (id) => {
      const normalizedId = normalizeEntryId(id);
      if (!normalizedId || normalizedId === 'assembly-empty') {
        return;
      }

      activeStructureNode.value = { type: 'assembly', id: normalizedId };
      activeDetailTarget.value = { type: 'assembly', id: normalizedId };
      structureRootExpanded.value = true;
      structureExpandedAssemblyId.value = normalizedId;

      if (expandedAssemblies.value.includes(normalizedId)) {
        expandedAssemblies.value = expandedAssemblies.value.filter((item) => item !== normalizedId);
        return;
      }

      expandedAssemblies.value = [...expandedAssemblies.value, normalizedId];
    };

    const toggleAnnotation = (id) => {
      const normalizedId = normalizeEntryId(id);
      if (!normalizedId || normalizedId === 'annotation-empty') {
        return;
      }

      activeStructureNode.value = { type: 'annotation', id: normalizedId };
      activeDetailTarget.value = { type: 'annotation', id: normalizedId };

      if (expandedAnnotations.value.includes(normalizedId)) {
        expandedAnnotations.value = expandedAnnotations.value.filter((item) => item !== normalizedId);
        return;
      }

      expandedAnnotations.value = [...expandedAnnotations.value, normalizedId];
    };

    const expandAll = () => {
      expandedAssemblies.value = filteredAssemblyEntries.value
        .map((entry) => normalizeEntryId(entry.id))
        .filter((id) => id && id !== 'assembly-empty');
      expandedAnnotations.value = filteredAnnotationEntries.value
        .map((entry) => normalizeEntryId(entry.id))
        .filter((id) => id && id !== 'annotation-empty');
    };

    const collapseAll = () => {
      expandedAssemblies.value = [];
      expandedAnnotations.value = [];
    };

    const setAssemblyCardRef = (id, element) => {
      const key = normalizeEntryId(id);
      if (!key) return;
      if (element) {
        assemblyCardRefs.set(key, element);
      } else {
        assemblyCardRefs.delete(key);
      }
    };

    const setAnnotationCardRef = (id, element) => {
      const key = normalizeEntryId(id);
      if (!key) return;
      if (element) {
        annotationCardRefs.set(key, element);
      } else {
        annotationCardRefs.delete(key);
      }
    };

    const clearHighlightTimer = () => {
      if (highlightTimer) {
        clearTimeout(highlightTimer);
        highlightTimer = 0;
      }
    };

    const flashDetailTarget = (type, id = '') => {
      clearHighlightTimer();
      activeDetailTarget.value = { type, id };
      highlightTimer = window.setTimeout(() => {
        activeDetailTarget.value = { type: '', id: '' };
        highlightTimer = 0;
      }, 2200);
    };

    const scrollToElement = async (element) => {
      if (!element) {
        return;
      }
      await nextTick();
      element.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    };

    const handleStructureRootClick = async () => {
      activeStructureNode.value = { type: 'accession', id: 'root' };
      structureRootExpanded.value = !structureRootExpanded.value;
      if (!structureRootExpanded.value) {
        structureExpandedAssemblyId.value = '';
      }
      flashDetailTarget('accession');
      await scrollToElement(accessionSummaryRef.value);
    };

    const handleStructureAssemblyClick = async (assembly) => {
      const normalizedId = normalizeEntryId(assembly?.id);
      if (!normalizedId) {
        return;
      }

      structureRootExpanded.value = true;
      structureExpandedAssemblyId.value = structureExpandedAssemblyId.value === normalizedId ? '' : normalizedId;
      activeStructureNode.value = { type: 'assembly', id: normalizedId };

      if (!expandedAssemblies.value.includes(normalizedId)) {
        expandedAssemblies.value = [...expandedAssemblies.value, normalizedId];
      }

      flashDetailTarget('assembly', normalizedId);
      await scrollToElement(assemblyCardRefs.get(normalizedId));
    };

    const handleStructureAnnotationClick = async (assembly, annotation) => {
      const assemblyId = normalizeEntryId(assembly?.id);
      const annotationId = normalizeEntryId(annotation?.id);

      if (!assemblyId || !annotationId) {
        return;
      }

      structureRootExpanded.value = true;
      structureExpandedAssemblyId.value = assemblyId;
      activeStructureNode.value = { type: 'annotation', id: annotationId };

      if (!expandedAssemblies.value.includes(assemblyId)) {
        expandedAssemblies.value = [...expandedAssemblies.value, assemblyId];
      }

      if (!expandedAnnotations.value.includes(annotationId)) {
        expandedAnnotations.value = [...expandedAnnotations.value, annotationId];
      }

      flashDetailTarget('annotation', annotationId);
      await scrollToElement(annotationCardRefs.get(annotationId));
    };

    const handleStructureNodeClick = async (node) => {
      if (!node) {
        return;
      }

      if (node.type === 'accession') {
        await handleStructureRootClick();
        return;
      }

      if (node.type === 'assembly') {
        await handleStructureAssemblyClick(node.assembly);
        return;
      }

      if (node.type === 'annotation') {
        await handleStructureAnnotationClick(node.assembly, node.annotation);
      }
    };

    const getStructureNodeAnchorStyle = (node) => {
      return {
        left: `${((node.x / structureGraph.value.width) * 100).toFixed(3)}%`,
        top: `${node.y}px`
      };
    };

    const fetchAccessionDetail = async (accession) => {
      if (!accession) {
        accessionDetail.value = null;
        assemblies.value = [];
        errorMessage.value = '';
        selectedAssemblyId.value = '';
        selectedAnnotationId.value = '';
        expandedAssemblies.value = [];
        expandedAnnotations.value = [];
        return;
      }

      try {
        loading.value = true;
        errorMessage.value = '';

        const response = await axios.get(`/files/accessions/${accession}/`);

        if (!response.data?.success) {
          throw new Error(response.data?.message || 'Failed to load accession details');
        }

        const data = response.data.data || {};
        accessionDetail.value = data.accession || null;
        assemblies.value = data.assemblies || [];

        if (!accessionDetail.value) {
          errorMessage.value = 'No accession detail data was returned.';
        }
      } catch (error) {
        console.error('Failed to load accession detail table:', error);
        accessionDetail.value = null;
        assemblies.value = [];
        errorMessage.value = 'Failed to load accession detail table.';
        ElMessage.error('Failed to load accession detail table.');
      } finally {
        loading.value = false;
      }
    };

    const refreshPage = async () => {
      await fetchAccessionDetail(routeAccession.value);
    };

    const goBackToCard = async () => {
      const query = routeAccession.value ? { accession: routeAccession.value } : {};
      await router.push({
        name: 'accession-card',
        query
      });
    };

    const openAnnotationDetail = async (entry) => {
      if (!routeAccession.value || !entry?.assemblyId || !entry?.id || entry.id === 'annotation-empty') {
        return;
      }

      await router.push({
        name: 'annotation-card',
        query: {
          accession: routeAccession.value,
          assembly: String(entry.assemblyId),
          annotation: String(entry.id)
        }
      });
    };

    watch(
      () => [route.query.accession, route.query.organism],
      async () => {
        await fetchAccessionDetail(routeAccession.value);
      },
      { immediate: true }
    );

    watch(
      [assemblyEntries, annotationEntries, selectedAssemblyId, selectedAnnotationId],
      () => {
        const validAssemblyIds = assemblyFilterOptions.value.map((entry) => normalizeEntryId(entry.id));
        const validAnnotationIds = annotationFilterOptions.value
          .filter((entry) => {
            if (!selectedAssemblyId.value) {
              return true;
            }
            return normalizeEntryId(entry.assemblyId) === selectedAssemblyId.value;
          })
          .map((entry) => normalizeEntryId(entry.id));

        if (selectedAssemblyId.value && !validAssemblyIds.includes(selectedAssemblyId.value)) {
          selectedAssemblyId.value = '';
          return;
        }

        if (selectedAnnotationId.value && !validAnnotationIds.includes(selectedAnnotationId.value)) {
          selectedAnnotationId.value = '';
          return;
        }

        syncExpandedState();

        const availableStructureAssemblyIds = structureAssemblies.value
          .map((entry) => normalizeEntryId(entry.id))
          .filter(Boolean);

        if (
          structureExpandedAssemblyId.value &&
          !availableStructureAssemblyIds.includes(structureExpandedAssemblyId.value)
        ) {
          structureExpandedAssemblyId.value = '';
        }

        if (!structureExpandedAssemblyId.value && availableStructureAssemblyIds.length) {
          structureExpandedAssemblyId.value = availableStructureAssemblyIds[0];
        }
      },
      { immediate: true }
    );

    onBeforeUnmount(() => {
      clearHighlightTimer();
    });

    return {
      activeDetailTarget,
      activeStructureNode,
      accessionDetail,
      accessionSummaryRef,
      accessionRows,
      annotationFilterOptions,
      ArrowLeft,
      assemblyFilterOptions,
      collapseAll,
      expandAll,
      errorMessage,
      filteredAnnotationEntries,
      filteredAssemblyEntries,
      goBackToCard,
      isAnnotationExpanded,
      isAssemblyExpanded,
      loading,
      openAnnotationDetail,
      refreshPage,
      routeAccession,
      selectedAnnotationId,
      selectedAssemblyId,
      normalizeEntryId,
      setAnnotationCardRef,
      setAssemblyCardRef,
      structureAssemblies,
      structureGraph,
      structureExpandedAssemblyId,
      structureRootExpanded,
      handleStructureAnnotationClick,
      handleStructureAssemblyClick,
      handleStructureNodeClick,
      handleStructureRootClick,
      getStructureNodeAnchorStyle,
      toggleAnnotation,
      toggleAssembly
    };
  }
};
</script>

<style scoped>
.accession-detail-table-view {
  padding: 6px 0 36px;
  background: #f5f7fb;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  width: 100%;
  max-width: none;
  min-width: 0;
  margin: 0 0 26px;
}

.title-block {
  min-width: 0;
}

.title {
  margin: 0;
  font-size: 34px;
  line-height: 1.15;
  font-weight: 500;
  color: #182433;
}

.page-subtitle {
  margin-top: 8px;
  color: #5f6b7a;
  font-size: 14px;
}

.title-accent {
  width: 132px;
  height: 4px;
  margin-top: 14px;
  background: linear-gradient(90deg, #1a56db 0%, #5b8bdd 100%);
  border-radius: 999px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.back-button {
  border-radius: 999px;
  border-color: #d4def4;
  color: #1a56db;
}

.data-card {
  background: transparent;
  border-radius: 0;
  box-shadow: none;
  padding: 0;
}

.loading {
  padding: 20px;
}

.empty-state {
  padding: 48px 20px;
}

.toolbar-shell,
.content-shell {
  width: 100%;
  max-width: none;
  min-width: 0;
  margin: 0;
}

.toolbar-shell {
  margin-bottom: 22px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 18px;
  width: 100%;
  padding: 14px 18px;
  background: #ffffff;
  border: 1px solid #e3ebfb;
  border-radius: 16px;
  box-shadow: 0 8px 20px rgba(36, 72, 129, 0.08);
}

.toolbar-item {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.toolbar-item-accession {
  flex: 0 0 auto;
}

.toolbar-item-filter {
  flex: 1 1 0;
}

.toolbar-label {
  flex: 0 0 auto;
  font-size: 14px;
  font-weight: 500;
  color: #50627b;
}

.toolbar-value {
  min-width: 0;
  padding: 0 14px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  border: 1px solid #dbe5f7;
  border-radius: 10px;
  background: #f9fbff;
  color: #1f2f46;
  font-weight: 500;
}

.toolbar-select {
  width: 100%;
  min-width: 180px;
}

.toolbar-divider {
  width: 1px;
  height: 28px;
  background: #e5ecf8;
}

.toolbar-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.toolbar-action-button {
  border-radius: 10px;
  border-color: #d4def4;
  color: #1a56db;
}

.content-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(360px, 26vw, 400px);
  gap: 24px;
  align-items: start;
}

.content-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.structure-shell {
  min-width: 0;
  align-self: start;
  position: sticky;
  top: 24px;
}

.structure-card {
  background: #ffffff;
  border: 1px solid #e2eaf8;
  border-radius: 18px;
  padding: 22px 24px 18px;
  box-shadow: 0 10px 24px rgba(36, 72, 129, 0.08);
  overflow: hidden;
}

.structure-heading {
  margin-bottom: 8px;
}

.structure-title {
  white-space: nowrap;
  font-size: 18px;
}

.structure-legend-row {
  margin-bottom: 14px;
}

.structure-tree {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 2px 0 8px;
  min-height: 180px;
  overflow-x: auto;
  overflow-y: hidden;
}

.structure-graph-stage {
  position: relative;
  flex: 0 0 auto;
}

.tree-dot {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 3px solid #64748b;
  box-shadow: 0 0 0 4px rgba(219, 231, 246, 0.30);
}

.tree-label {
  min-width: 0;
  max-width: 138px;
  color: #334155;
  font-size: 14px;
  line-height: 1.45;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.structure-legend {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: nowrap;
  gap: 12px;
  min-width: 0;
}

.structure-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #5f6f86;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.structure-legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 2px solid #64748b;
}

.structure-legend-dot-accession,
.tree-dot-accession {
  background: #f8d7da;
}

.structure-legend-dot-assembly,
.tree-dot-assembly {
  background: #fcead5;
}

.structure-legend-dot-annotation,
.tree-dot-annotation {
  background: #fbf7df;
}

.structure-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.structure-edge {
  fill: none;
  stroke: #dbe7f6;
  stroke-width: 2.2;
  stroke-linecap: round;
}

.tree-node-anchor {
  position: absolute;
  width: 0;
  height: 0;
  z-index: 1;
}

.tree-node-anchor.label-right .tree-node-card {
  transform: translate(-16px, -50%);
}

.tree-node-anchor.label-left .tree-node-card {
  flex-direction: row-reverse;
  transform: translate(calc(-100% + 16px), -50%);
}

.tree-node-card {
  border: none;
  background: transparent;
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: transform 0.2s ease, filter 0.2s ease;
}

.tree-node-card:hover {
  filter: brightness(1.02);
}

.tree-node-active .tree-label {
  color: #1d4ed8;
  font-weight: 700;
}

.tree-node-card.tree-node-active .tree-dot {
  border-color: #425d80;
  box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.12);
}

.tree-node-card.tree-node-active {
  filter: drop-shadow(0 6px 14px rgba(59, 130, 246, 0.14));
}

.tree-node-card.tree-node-muted .tree-label {
  color: #94a3b8;
}

.tree-node-card.tree-node-muted .tree-dot {
  opacity: 0.65;
}

.linked-highlight {
  border-color: #9cbcf5 !important;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.08), 0 12px 28px rgba(36, 72, 129, 0.10) !important;
}

.info-section {
  background: #ffffff;
  border: 1px solid #e2eaf8;
  border-radius: 18px;
  padding: 22px;
  box-shadow: 0 10px 24px rgba(36, 72, 129, 0.08);
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.section-title {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
  font-weight: 600;
  color: #1d4ed8;
}

.section-note {
  margin: 6px 0 0;
  color: #75839a;
  font-size: 13px;
}

.section-chip {
  min-width: 34px;
  height: 30px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #edf4ff;
  color: #1a56db;
  font-size: 13px;
  font-weight: 700;
}

.accession-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 1fr));
  gap: 14px 18px;
}

.info-row-wide {
  grid-column: 1 / -1;
  grid-template-columns: minmax(150px, 200px) minmax(0, 1fr);
}

.accordion-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.accordion-card {
  border: 1px solid #e3ebfb;
  border-radius: 14px;
  background: #fbfdff;
  overflow: hidden;
}

.accordion-trigger {
  width: 100%;
  padding: 16px 18px;
  border: none;
  background: #f7faff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s ease;
}

.accordion-trigger:hover {
  background: #f0f5ff;
}

.accordion-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.accordion-arrow {
  flex: 0 0 auto;
  width: 20px;
  color: #5c6f8d;
  font-size: 14px;
  font-weight: 700;
  text-align: center;
}

.accordion-title-text {
  min-width: 0;
  color: #1f2f46;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.default-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: #e9f1ff;
  color: #1a56db;
  font-size: 12px;
  font-weight: 700;
}

.accordion-meta {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  color: #6c7b92;
  font-size: 13px;
  text-align: right;
}

.annotation-assembly {
  padding-left: 12px;
  border-left: 1px solid #d9e4f7;
}

.accordion-body {
  padding: 18px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(150px, 200px) minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid #ecf1fb;
  border-radius: 12px;
  background: #f9fbff;
}

.info-row.compact {
  padding: 12px 14px;
}

.info-label {
  color: #1a56db;
  font-size: 14px;
  font-weight: 600;
}

.info-value {
  min-width: 0;
  color: #4a5563;
  font-size: 14px;
  line-height: 1.6;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.value-link {
  color: #4c78c7;
  text-decoration: none;
  word-break: break-all;
}

.value-link:hover {
  text-decoration: underline;
}

.value-action-button {
  padding: 0;
  font-size: 14px;
  font-weight: 500;
  color: #1a56db;
}

@media (max-width: 992px) {
  .page-header {
    flex-direction: column;
    width: 100%;
    min-width: 0;
    margin-bottom: 20px;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .title {
    font-size: 28px;
  }

  .title-accent {
    width: 112px;
  }

  .toolbar-shell,
  .content-shell {
    width: 100%;
    min-width: 0;
  }

  .toolbar {
    flex-wrap: wrap;
  }

  .toolbar-item-accession {
    flex-basis: 100%;
  }

  .toolbar-item-filter {
    flex: 1 1 100%;
  }

  .toolbar-divider {
    display: none;
  }

  .toolbar-actions {
    width: 100%;
    margin-left: 0;
    justify-content: flex-start;
  }

  .content-shell {
    grid-template-columns: 1fr;
  }

  .structure-shell {
    position: static;
    top: auto;
  }

  .structure-card {
    padding: 22px;
  }

  .structure-legend {
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 8px 12px;
  }

  .accession-grid {
    grid-template-columns: 1fr;
  }

  .info-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .accordion-trigger {
    flex-direction: column;
    align-items: flex-start;
  }

  .accordion-meta {
    text-align: left;
  }
}
</style>

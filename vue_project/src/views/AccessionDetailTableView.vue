<template>
  <div :class="['accession-page', embedded ? 'is-embedded' : '']">
    <div class="accession-breadcrumb">首页 / 品种信息 / {{ routeAccession || '-' }}</div>
    <div class="page-heading">
      <div>
        <div class="page-kicker">ACCESSION</div>
        <h1>Accession · {{ accessionDetail?.accession || routeAccession || '-' }}</h1>
        <div v-if="accessionDetail" class="heading-tags">
          <span class="heading-tag species-tag">物种：{{ speciesLabel }}</span>
          <span class="heading-tag population-tag">亚群：{{ accessionDetail.sub_population || '-' }}</span>
        </div>
      </div>
      <div class="heading-actions">
        <button v-if="!embedded" type="button" class="back-search-button" @click="goBackToSearch">返回品种信息</button>
        <el-tooltip content="刷新" placement="top"><el-button circle class="refresh-button" @click="refreshPage"><el-icon><Refresh /></el-icon></el-button></el-tooltip>
      </div>
    </div>

    <div class="page-body">
      <div v-if="loading" class="state-card"><el-skeleton :rows="14" animated /></div>
      <div v-else-if="!routeAccession" class="state-card"><el-empty description="请选择 Accession 查看信息" /></div>
      <div v-else-if="errorMessage" class="state-card"><el-empty :description="errorMessage" /></div>

      <template v-else-if="accessionDetail">
        <div class="summary-grid">
          <article v-for="card in summaryCards" :key="card.key" class="summary-card"><span class="summary-icon">{{ card.icon }}</span><div><div class="summary-label">{{ card.label }}</div><div class="summary-value">{{ card.value }}</div></div></article>
        </div>

        <div class="accession-layout">
          <main class="detail-column">
            <nav class="section-tabs" aria-label="Accession sections">
              <button type="button" @click="scrollToSection('basic-section')">基本信息</button>
              <button type="button" @click="scrollToSection('assembly-section')">Assembly / 组装版本</button>
              <button type="button" @click="scrollToSection('annotation-section')">Annotation / 注释版本</button>
              <button type="button" @click="scrollToSection('files-section')">相关文件</button>
            </nav>

            <section id="basic-section" ref="accessionSummaryRef" :class="['detail-section', activeDetailTarget.type === 'accession' ? 'linked-highlight' : '']">
              <h2>基本信息</h2>
              <div class="basic-info-grid">
                <div v-for="row in basicInfoRows" :key="row.label" :class="['basic-info-row', row.wide ? 'wide' : '']"><span class="field-label">{{ row.label }}</span><a v-if="row.link && row.value !== '-'" :href="row.value" target="_blank" rel="noopener noreferrer" class="field-link">{{ row.value }}</a><span v-else class="field-value">{{ row.value }}</span></div>
              </div>
            </section>

            <section id="assembly-section" class="detail-section">
              <h2>Assembly / 组装版本</h2>
              <div class="table-shell"><table class="detail-table"><thead><tr><th>组装版本</th><th>组装编码</th><th>参考基因组</th><th>BioProject</th><th>Reference</th><th>文件数</th><th>操作</th></tr></thead><tbody>
                <tr v-for="entry in assemblyTableRows" :key="entry.id" :ref="(el) => setAssemblyCardRef(entry.id, el)" :class="activeDetailTarget.type === 'assembly' && normalizeEntryId(entry.id) === activeDetailTarget.id ? 'linked-highlight' : ''"><td><strong>{{ entry.displayName }}</strong><span v-if="entry.isDefault" class="default-chip">default</span></td><td>{{ entry.standardId }}</td><td>{{ entry.referenceName }}</td><td>{{ entry.bioProject }}</td><td>{{ entry.reference }}</td><td>{{ entry.fileCount }}</td><td><button type="button" class="table-action" @click="showRelatedFiles('assembly', entry.id)">查看文件</button></td></tr>
                <tr v-if="!assemblyTableRows.length"><td colspan="7" class="empty-table-cell">暂无组装版本</td></tr>
              </tbody></table></div>
            </section>

            <section id="annotation-section" class="detail-section">
              <h2>Annotation / 注释版本</h2>
              <div class="table-shell"><table class="detail-table"><thead><tr><th>注释版本</th><th>注释编码</th><th>来源 / 方法</th><th>关联 Assembly</th><th>文件数</th><th>操作</th></tr></thead><tbody>
                <tr v-for="entry in annotationTableRows" :key="entry.id" :ref="(el) => setAnnotationCardRef(entry.id, el)" :class="activeDetailTarget.type === 'annotation' && normalizeEntryId(entry.id) === activeDetailTarget.id ? 'linked-highlight' : ''"><td><strong>{{ entry.displayName }}</strong><span v-if="entry.isDefault" class="default-chip">default</span></td><td>{{ entry.standardId }}</td><td>{{ entry.source }}</td><td>{{ entry.assemblyName }}</td><td>{{ entry.fileCount }}</td><td class="action-cell"><button type="button" class="table-action secondary" @click="openAnnotationDetail(entry)">查看详情</button><button type="button" class="table-action" @click="showRelatedFiles('annotation', entry.id)">查看文件</button></td></tr>
                <tr v-if="!annotationTableRows.length"><td colspan="6" class="empty-table-cell">暂无注释版本</td></tr>
              </tbody></table></div>
            </section>

            <section id="files-section" class="detail-section">
              <div class="section-title-row"><h2>相关文件（DataFile + FileRelation）</h2><button v-if="fileScopeFilter.type" type="button" class="clear-filter" @click="clearFileFilter">显示全部文件</button></div>
              <div class="table-shell"><table class="detail-table files-table"><thead><tr><th>文件名</th><th>文件角色</th><th>关联类型</th><th>关联对象</th><th>文件类型</th><th>大小</th><th>下载</th></tr></thead><tbody>
                <tr v-for="file in displayedFiles" :key="file.id"><td class="file-name-cell">{{ file.file_name || file.name }}</td><td><span class="role-chip">{{ file.file_role || '-' }}</span></td><td>{{ file.related_type || '-' }}</td><td>{{ file.related_object || file.related_code || '-' }}</td><td>{{ file.file_type || '-' }}</td><td>{{ file.size_display || formatFileSize(file.file_size) }}</td><td><button type="button" class="download-action" @click="downloadFile(file)">DataFile 下载</button></td></tr>
                <tr v-if="!displayedFiles.length"><td colspan="7" class="empty-table-cell">暂无相关文件</td></tr>
              </tbody></table></div>
            </section>
          </main>

          <aside class="side-column">
            <section class="side-card relation-card">
              <div class="side-card-heading"><h2>关系概览</h2><span>Accession Structure</span></div>
              <div class="structure-legend" aria-label="Structure legend"><span><i class="legend-dot accession"></i>Accession</span><span><i class="legend-dot assembly"></i>Assembly</span><span><i class="legend-dot annotation"></i>Annotation</span></div>
              <div class="structure-tree"><div class="structure-graph-stage" :style="{ width: structureGraph.width + 'px', minHeight: structureGraph.height + 'px' }"><svg class="structure-svg" :viewBox="'0 0 ' + structureGraph.width + ' ' + structureGraph.height" preserveAspectRatio="xMidYMin meet" aria-hidden="true"><path v-for="edge in structureGraph.edges" :key="edge.key" :d="edge.path" class="structure-edge" /></svg><div v-for="node in structureGraph.nodes" :key="node.key" :class="['tree-node-anchor', 'label-' + node.labelSide]" :style="getStructureNodeAnchorStyle(node)"><button type="button" :class="['tree-node-card', 'tree-node-card-' + node.type, node.active ? 'tree-node-active' : '', node.muted ? 'tree-node-muted' : '']" :title="node.label" @click="handleStructureNodeClick(node)"><span :class="['tree-dot', 'tree-dot-' + node.type]"></span><span class="tree-label">{{ node.label }}</span></button></div></div></div>
            </section>
            <section class="side-card quick-card"><h2>快捷导航</h2><button type="button" @click="scrollToSection('basic-section')">基本信息</button><button type="button" @click="scrollToSection('assembly-section')">组装版本</button><button type="button" @click="scrollToSection('annotation-section')">注释版本</button><button type="button" @click="scrollToSection('files-section')">相关文件</button></section>
            <section class="side-card status-card"><h2>数据状态</h2><div v-for="item in dataStatusRows" :key="item.key" class="status-row"><span>{{ item.label }}</span><span :class="['status-chip', item.status]">{{ item.text }}</span></div></section>
            <section class="side-card audit-card"><h2>创建与更新信息</h2><div v-for="item in auditRows" :key="item.label" class="audit-row"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div></section>
          </aside>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';

const normalizeQueryValue = (value) => {
  return value ? String(value).trim() : '';
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
    Refresh
  },
  props: {
    embedded: {
      type: Boolean,
      default: false
    }
  },
  setup(props) {
    const route = useRoute();
    const router = useRouter();

    const loading = ref(false);
    const errorMessage = ref('');
    const accessionDetail = ref(null);
    const assemblies = ref([]);
    const summary = ref({});
    const files = ref([]);
    const projects = ref([]);
    const datasets = ref([]);
    const dataStatus = ref({});
    const audit = ref({});
    const fileScopeFilter = ref({ type: '', id: '' });
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

    const speciesLabel = computed(() => {
      const species = accessionDetail.value?.species;
      if (!species) return '-';
      const primaryName = species.chinese_name || species.common_name || species.species_code;
      return species.scientific_name
        ? `${primaryName || species.scientific_name} (${species.scientific_name})`
        : primaryName || '-';
    });

    const summaryCards = computed(() => [
      { key: 'sample', label: '样本数', value: summary.value.sample_count ?? 0, icon: '⚗' },
      { key: 'dataset', label: '数据集数', value: summary.value.dataset_count ?? 0, icon: '▰' },
      { key: 'file', label: '文件数', value: summary.value.file_count ?? 0, icon: '▤' },
      { key: 'size', label: '总数据量', value: summary.value.total_size_display || '0 B', icon: '▣' },
      { key: 'assembly', label: 'Assembly 数', value: summary.value.assembly_count ?? 0, icon: '⌛' },
      { key: 'annotation', label: 'Annotation 数', value: summary.value.annotation_count ?? 0, icon: '✎' }
    ]);

    const basicInfoRows = computed(() => {
      const detail = accessionDetail.value || {};
      const location = [detail.country, detail.region].filter(Boolean).join(' / ') || '-';
      const coordinates = [detail.latitude, detail.longitude]
        .filter((value) => value !== null && value !== undefined)
        .join(', ') || '-';
      const projectText = projects.value
        .map((item) => item.project_name || item.project_code)
        .filter(Boolean)
        .join('、') || '-';
      const datasetText = datasets.value
        .map((item) => item.dataset_name || item.dataset_code)
        .filter(Boolean)
        .join('、') || '-';

      return [
        { label: 'Accession 编号', value: detail.accession || '-' },
        { label: '经纬度', value: coordinates },
        { label: '物种', value: speciesLabel.value },
        { label: 'Project', value: projectText },
        { label: '亚群 / 分组', value: detail.sub_population || '-' },
        { label: 'Dataset', value: datasetText },
        { label: '国家 / 地区', value: location },
        { label: '外部链接', value: detail.seq_data || '-', link: Boolean(detail.seq_data) },
        { label: '描述', value: detail.description || '-', wide: true }
      ];
    });

    const assemblyTableRows = computed(() => assemblies.value.map((assembly) => ({
      id: assembly.id,
      displayName: assembly.display_name || assembly.name || `Assembly ${assembly.id}`,
      standardId: assembly.standard_id || '-',
      referenceName: assembly.reference_name || assembly.reference_genome || '-',
      bioProject: assembly.bio_project || '-',
      reference: assembly.reference || '-',
      fileCount: assembly.file_count ?? 0,
      isDefault: Boolean(assembly.is_default)
    })));

    const annotationTableRows = computed(() => assemblies.value.flatMap((assembly) => (
      (assembly.annotations || []).map((annotation) => ({
        id: annotation.id,
        assemblyId: assembly.id,
        displayName: annotation.display_name || annotation.name || `Annotation ${annotation.id}`,
        standardId: annotation.standard_id || '-',
        source: annotation.source_name || annotation.source_summary || '-',
        assemblyName: assembly.display_name || assembly.name || `Assembly ${assembly.id}`,
        fileCount: annotation.file_count ?? 0,
        isDefault: Boolean(annotation.is_default)
      }))
    )));

    const displayedFiles = computed(() => {
      if (!fileScopeFilter.value.type) {
        return files.value;
      }
      return files.value.filter((item) => {
        const relations = item.relations?.length
          ? item.relations
          : [{ related_type: item.related_type, related_id: item.related_id }];
        return relations.some((relation) => (
          relation.related_type === fileScopeFilter.value.type
          && String(relation.related_id) === String(fileScopeFilter.value.id)
        ));
      });
    });

    const dataStatusRows = computed(() => {
      const labels = {
        genome: 'Genome',
        annotation: 'Annotation',
        transcriptome: 'Transcriptome',
        population: 'Population'
      };
      const text = {
        ready: '已就绪',
        partial: '部分可用',
        unavailable: '无数据'
      };
      return Object.keys(labels).map((key) => ({
        key,
        label: labels[key],
        status: dataStatus.value[key] || 'unavailable',
        text: text[dataStatus.value[key]] || text.unavailable
      }));
    });

    const formatDateTime = (value) => {
      if (!value) return '-';
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false });
    };

    const auditRows = computed(() => [
      { label: '创建日期', value: formatDateTime(audit.value.created_at || accessionDetail.value?.created_at) },
      { label: '更新日期', value: formatDateTime(audit.value.updated_at || accessionDetail.value?.updated_at) },
      { label: '创建者', value: audit.value.created_by || '-' }
    ]);

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
      const visibleAnnotations = expandedAssemblyNode?.assembly?.annotations || [];

      if (expandedAssemblyNode && visibleAnnotations.length) {
        const annotationXs = distributeNodes(
          visibleAnnotations.length,
          expandedAssemblyNode.x,
          innerMinX,
          innerMaxX,
          112
        );

        visibleAnnotations.forEach((annotation, index) => {
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

    const scrollToSection = async (sectionId) => {
      await nextTick();
      document.getElementById(sectionId)?.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
    };

    const showRelatedFiles = async (type, id) => {
      fileScopeFilter.value = { type, id: String(id) };
      await scrollToSection('files-section');
    };

    const clearFileFilter = () => {
      fileScopeFilter.value = { type: '', id: '' };
    };

    const formatFileSize = (value) => {
      let size = Number(value || 0);
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let unitIndex = 0;
      while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex += 1;
      }
      return unitIndex === 0 ? `${Math.round(size)} B` : `${size.toFixed(2)} ${units[unitIndex]}`;
    };

    const downloadFile = (file) => {
      const downloadUrl = file?.datafile_download_url || file?.download_url;
      if (!downloadUrl) {
        ElMessage.error('文件缺少 DataFile 下载地址');
        return;
      }
      window.open(new URL(downloadUrl, window.location.origin).toString(), '_blank');
    };

    const fetchAccessionDetail = async (accession) => {
      if (!accession) {
        accessionDetail.value = null;
        assemblies.value = [];
        summary.value = {};
        files.value = [];
        projects.value = [];
        datasets.value = [];
        dataStatus.value = {};
        audit.value = {};
        errorMessage.value = '';
        structureExpandedAssemblyId.value = '';
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
        summary.value = data.summary || {};
        files.value = data.files || [];
        projects.value = data.projects || [];
        datasets.value = data.datasets || [];
        dataStatus.value = data.data_status || {};
        audit.value = data.audit || {};
        fileScopeFilter.value = { type: '', id: '' };
        const assemblyIds = assemblies.value
          .map((item) => normalizeEntryId(item.id))
          .filter(Boolean);
        if (!assemblyIds.includes(structureExpandedAssemblyId.value)) {
          structureExpandedAssemblyId.value = assemblyIds[0] || '';
        }

        if (!accessionDetail.value) {
          errorMessage.value = 'No accession detail data was returned.';
        }
      } catch (error) {
        console.error('Failed to load accession detail table:', error);
        accessionDetail.value = null;
        assemblies.value = [];
        summary.value = {};
        files.value = [];
        projects.value = [];
        datasets.value = [];
        dataStatus.value = {};
        audit.value = {};
        errorMessage.value = 'Failed to load accession detail table.';
        ElMessage.error('Failed to load accession detail table.');
      } finally {
        loading.value = false;
      }
    };

    const refreshPage = async () => {
      await fetchAccessionDetail(routeAccession.value);
    };

    const goBackToSearch = async () => {
      await router.push({ name: 'accession-card' });
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

    onBeforeUnmount(() => {
      clearHighlightTimer();
    });

    return {
      activeDetailTarget,
      activeStructureNode,
      embedded: computed(() => props.embedded),
      accessionDetail,
      accessionSummaryRef,
      annotationTableRows,
      assemblyTableRows,
      auditRows,
      basicInfoRows,
      clearFileFilter,
      dataStatusRows,
      displayedFiles,
      downloadFile,
      errorMessage,
      fileScopeFilter,
      formatFileSize,
      goBackToSearch,
      loading,
      openAnnotationDetail,
      refreshPage,
      routeAccession,
      normalizeEntryId,
      setAnnotationCardRef,
      setAssemblyCardRef,
      showRelatedFiles,
      speciesLabel,
      scrollToSection,
      summaryCards,
      structureAssemblies,
      structureGraph,
      structureExpandedAssemblyId,
      structureRootExpanded,
      handleStructureAnnotationClick,
      handleStructureAssemblyClick,
      handleStructureNodeClick,
      handleStructureRootClick,
      getStructureNodeAnchorStyle
    };
  }
};
</script>

<style scoped>
.accession-page { padding: 8px 0 36px; background: #f4f7fb; color: #15233d; }
.accession-breadcrumb { margin-bottom: 12px; color: #76849a; font-size: 13px; }
.page-heading { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-kicker { color: #1760e8; font-size: 11px; font-weight: 800; letter-spacing: .16em; }
.page-heading h1 { margin: 4px 0 10px; font-size: 30px; line-height: 1.1; color: #15233d; }
.heading-actions { display: flex; align-items: center; gap: 10px; }
.back-search-button { height: 34px; padding: 0 14px; border: 1px solid #d8e3f4; border-radius: 999px; background: #fff; color: #31516f; font-size: 12px; font-weight: 800; cursor: pointer; box-shadow: 0 6px 16px rgba(35, 68, 116, .06); }
.back-search-button:hover { border-color: #9fc0ff; color: #1760e8; background: #f6f9ff; }
.heading-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.heading-tag { padding: 5px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.species-tag { color: #1c5bc5; background: #eaf2ff; border: 1px solid #cfe0ff; }
.population-tag { color: #327b46; background: #eaf8ed; border: 1px solid #ccebd3; }
.refresh-button { border-color: #d8e3f4; color: #1760e8; }
.page-body { min-height: 300px; }
.state-card { padding: 40px; background: #fff; border: 1px solid #e2e9f4; border-radius: 14px; }
.summary-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { display: flex; align-items: center; gap: 12px; min-height: 78px; padding: 13px 14px; background: #fff; border: 1px solid #e1e8f3; border-radius: 12px; box-shadow: 0 6px 18px rgba(35, 68, 116, .06); }
.summary-icon { display: grid; place-items: center; width: 38px; height: 38px; flex: 0 0 auto; border-radius: 12px; background: #edf4ff; color: #1760e8; font-size: 20px; }
.summary-label { color: #718096; font-size: 12px; }
.summary-value { margin-top: 4px; color: #153a7a; font-size: 21px; font-weight: 800; }
.accession-layout { display: grid; grid-template-columns: minmax(0, 1fr) 270px; gap: 14px; align-items: start; }
.detail-column { min-width: 0; background: #fff; border: 1px solid #e1e8f3; border-radius: 13px; overflow: hidden; }
.section-tabs { position: sticky; top: 0; z-index: 5; display: flex; gap: 28px; height: 48px; padding: 0 18px; align-items: center; background: rgba(255,255,255,.96); border-bottom: 1px solid #e8edf5; backdrop-filter: blur(8px); }
.section-tabs button { height: 48px; padding: 0; border: 0; border-bottom: 3px solid transparent; background: transparent; color: #526079; font-size: 13px; cursor: pointer; }
.section-tabs button:first-child, .section-tabs button:hover { color: #1760e8; border-bottom-color: #1760e8; }
.detail-section { scroll-margin-top: 56px; padding: 15px 18px; transition: background .2s ease, box-shadow .2s ease; }
.detail-section + .detail-section { border-top: 1px solid #edf1f6; }
.detail-section h2, .side-card h2 { margin: 0 0 10px; color: #1556c2; font-size: 15px; font-weight: 800; }
.basic-info-grid { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid #e3e9f2; border-radius: 9px; overflow: hidden; }
.basic-info-row { display: grid; grid-template-columns: 125px minmax(0, 1fr); gap: 10px; min-height: 36px; padding: 9px 12px; border-bottom: 1px solid #edf1f6; }
.basic-info-row:nth-child(odd):not(.wide) { border-right: 1px solid #edf1f6; }
.basic-info-row.wide { grid-column: 1 / -1; border-bottom: 0; }
.field-label { color: #68778f; font-size: 12px; }
.field-value, .field-link { color: #172846; font-size: 12px; line-height: 1.5; word-break: break-word; }
.field-link { color: #1760e8; text-decoration: none; }
.table-shell { width: 100%; overflow-x: auto; border: 1px solid #e3e9f2; border-radius: 9px; }
.detail-table { width: 100%; min-width: 760px; border-collapse: collapse; font-size: 11px; }
.detail-table th { padding: 9px 10px; background: #f5f8fc; color: #52627a; text-align: left; font-weight: 700; white-space: nowrap; }
.detail-table td { padding: 9px 10px; border-top: 1px solid #edf1f6; color: #2d3c55; vertical-align: middle; }
.detail-table tbody tr:hover { background: #f9fbff; }
.default-chip, .role-chip { display: inline-flex; margin-left: 7px; padding: 2px 7px; border-radius: 999px; color: #1760e8; background: #eaf2ff; font-size: 10px; }
.role-chip { margin-left: 0; color: #634bc2; background: #f0edff; }
.table-action, .download-action, .clear-filter { border: 1px solid #8db4ff; border-radius: 5px; padding: 4px 9px; background: #fff; color: #1760e8; font-size: 11px; cursor: pointer; white-space: nowrap; }
.table-action.secondary { border-color: #c6d5ed; color: #536985; }
.action-cell { display: flex; gap: 6px; }
.file-name-cell { font-weight: 700; color: #173b76 !important; }
.empty-table-cell { padding: 24px !important; text-align: center; color: #8794a8 !important; }
.section-title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.clear-filter { border: 0; }
.side-column { display: grid; gap: 12px; }
.side-card { padding: 14px; background: #fff; border: 1px solid #e1e8f3; border-radius: 12px; box-shadow: 0 5px 16px rgba(35,68,116,.04); }
.side-card-heading { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; }
.side-card-heading span { color: #8a97aa; font-size: 10px; }
.structure-legend { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; color: #65738a; font-size: 9px; }
.structure-legend span { display: flex; align-items: center; gap: 4px; }
.legend-dot { width: 7px; height: 7px; border: 1px solid #5f7796; border-radius: 50%; }
.legend-dot.accession { background: #ffe6e1; }.legend-dot.assembly { background: #fff0dd; }.legend-dot.annotation { background: #fffbe7; }
.structure-tree { position: relative; min-height: 290px; overflow-x: auto; overflow-y: hidden; padding: 4px 0 10px; }
.structure-graph-stage { position: relative; min-width: 420px; margin: 0 auto; }
.structure-svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
.structure-edge { fill: none; stroke: #cfe0f8; stroke-width: 2; stroke-linecap: round; }
.tree-node-anchor { position: absolute; transform: translate(-50%, -50%); z-index: 2; }
.tree-node-card { position: relative; display: flex; align-items: center; border: 0; background: transparent; padding: 0; color: #1756c5; font-size: 11px; cursor: pointer; }
.tree-dot { display: block; width: 24px; height: 24px; flex: 0 0 auto; border: 3px solid #5b7698; border-radius: 50%; background: #fff; box-shadow: 0 0 0 5px #e8f1fd; }
.tree-dot-accession { background: #ffe8e3; }.tree-dot-assembly { background: #fff0df; }.tree-dot-annotation { background: #fffbe8; }
.tree-label { position: absolute; left: 30px; width: 100px; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.label-left .tree-label { right: 30px; left: auto; text-align: right; }
.tree-node-active .tree-dot { border-color: #1760e8; box-shadow: 0 0 0 6px #dceaff; }
.tree-node-muted { opacity: .65; }
.quick-card button { display: block; width: 100%; padding: 7px 0; border: 0; background: transparent; color: #1760e8; text-align: left; font-size: 12px; cursor: pointer; }
.status-row, .audit-row { display: flex; justify-content: space-between; gap: 10px; align-items: center; padding: 7px 0; border-top: 1px solid #edf1f6; font-size: 11px; }
.status-row:first-of-type, .audit-row:first-of-type { border-top: 0; }
.status-chip { padding: 2px 7px; border-radius: 999px; font-size: 10px; }
.status-chip.ready { color: #258743; background: #e8f7ec; }.status-chip.partial { color: #c97500; background: #fff3dc; }.status-chip.unavailable { color: #7d8796; background: #eef1f5; }
.audit-row span { color: #758399; }.audit-row strong { color: #34445c; font-weight: 600; text-align: right; }
.linked-highlight { background: #eef5ff !important; box-shadow: inset 0 0 0 2px #8db4ff; }
@media (max-width: 1180px) { .summary-grid { grid-template-columns: repeat(3, 1fr); } .accession-layout { grid-template-columns: 1fr; } .side-column { grid-template-columns: repeat(3, 1fr); } .relation-card { grid-column: 1 / -1; } }
@media (max-width: 760px) { .summary-grid { grid-template-columns: repeat(2, 1fr); } .basic-info-grid { grid-template-columns: 1fr; } .basic-info-row:nth-child(odd):not(.wide) { border-right: 0; } .basic-info-row.wide { grid-column: auto; } .section-tabs { gap: 14px; overflow-x: auto; } .side-column { grid-template-columns: 1fr; } }
</style>

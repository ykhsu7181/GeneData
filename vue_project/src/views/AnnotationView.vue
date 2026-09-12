<template>
  <div class="annotation-view">
    <!-- 复用数据一览表的标题样式 -->
    <div class="page-header">
      <h2 class="title">{{ $t('page.annotation.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.annotation.refreshData')" placement="top">
          <el-button circle size="small" @click="fetchFiles" :loading="loading">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>
    
    <!-- 复用数据一览表的搜索下拉框 -->
    <div class="search-container">
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-autocomplete
          v-model="selectedOrganism"
          :placeholder="$t('page.annotation.searchPlaceholder')"
          :fetch-suggestions="queryAccessionSuggestions"
          :trigger-on-focus="false"
          clearable
          @select="handleAccessionSelect"
          @keyup.enter="handleAccessionSearch"
          @clear="handleOrganismChange('')"
          class="search-select"
        />
        <el-tooltip content="Search exact Accession" placement="top">
          <el-button
            class="accession-search-button"
            :loading="loadingOrganisms"
            @click="handleAccessionSearch"
          >
            <el-icon><Search /></el-icon>
          </el-button>
        </el-tooltip>

        <div class="divider"></div>

        <!-- 染色体选择框 -->
        <div class="chromosome-select">
          <span class="select-label">Chromosome:</span>
          <el-select
            v-model="selectedChromosome"
            placeholder="Select chromosome"
            class="chromosome-dropdown"
            :loading="loadingChromosomes"
            clearable
            @change="handleChromosomeChange"
          >
            <el-option
              v-for="item in chromosomeOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </div>

        <div class="divider"></div>

        <!-- 特征类型选择框 -->
        <div class="feature-select">
          <span class="select-label">Feature:</span>
          <el-select
            v-model="selectedFeatureType"
            placeholder="Select feature type"
            class="feature-dropdown"
            clearable
            :disabled="viewMode === 'chart'"
            @change="handleFeatureTypeChange"
          >
            <el-option
              v-for="item in featureTypeOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </div>

        <div class="divider"></div>

        <!-- 图/表切换按钮 -->
        <div class="view-toggle">
          <el-button-group>
            <el-button
              :type="viewMode === 'table' ? 'primary' : 'default'"
              @click="viewMode = 'table'"
              size="small">
              <el-icon><Grid /></el-icon>
              {{ $t('page.annotation.tableView') }}
            </el-button>
            <el-button
              :type="viewMode === 'chart' ? 'primary' : 'default'"
              @click="viewMode = 'chart'"
              size="small">
              <el-icon><TrendCharts /></el-icon>
              {{ $t('page.annotation.chartView') }}
            </el-button>
          </el-button-group>
        </div>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="data-card">
      <div v-if="loading" class="loading">
        <el-skeleton :rows="6" animated />
      </div>

      <div v-else-if="!selectedOrganism" class="empty-state">
        <el-empty :description="$t('page.annotation.selectOrganismPrompt')" />
      </div>

      <div v-else class="content-container">
        <!-- 数据统计信息 - 仅在表格模式显示 -->
        <div v-if="annotationStatistics && viewMode === 'table'" class="data-stats">
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-label">{{ $t('page.annotation.totalFeatures') }}</span>
              <span class="stat-value">{{ annotationStatistics.total_features }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">{{ $t('page.annotation.chromosomes') }}</span>
              <span class="stat-value">{{ annotationStatistics.chromosomes.length }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">{{ $t('page.annotation.featureTypes') }}</span>
              <span class="stat-value">{{ annotationStatistics.feature_types.length }}</span>
            </div>
          </div>
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
          >
            <el-table-column prop="seqid" label="Chromosome" width="120" />
            <el-table-column prop="feature" label="Feature" width="100" />
            <el-table-column prop="start" label="Start" width="100" sortable />
            <el-table-column prop="end" label="End" width="100" sortable />
            <el-table-column prop="length" label="Length" width="100" sortable />
            <el-table-column prop="strand" label="Strand" width="80" />
            <el-table-column prop="source" label="Source" width="100" />
            <el-table-column prop="score" label="Score" width="80" />
            <el-table-column label="Attributes" min-width="300">
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
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
            />
          </div>
        </div>

        <!-- 图形模式 -->
        <div v-else-if="viewMode === 'chart'" class="annotation-visualization">
          <div v-if="loadingVisualization" class="loading-visualization">
            <div class="loading-content">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>{{ $t('page.annotation.loadingVisualization') }}</span>
            </div>
          </div>
          <div v-else-if="!selectedOrganism || !selectedChromosome" class="empty-state">
            <el-empty description="请选择生物体和染色体以查看可视化" />
          </div>
          <div v-else class="chart-content">
            <!-- 可视化控制面板 -->
            <div class="visualization-controls">
              <div class="control-group">
                <span class="control-label">显示特征类型:</span>
                <el-checkbox-group v-model="displayFeatures" @change="updateVisualization" class="feature-checkboxes">
                  <el-checkbox label="gene" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('gene') }"></span>
                    基因
                  </el-checkbox>
                  <el-checkbox label="mRNA" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('mRNA') }"></span>
                    mRNA
                  </el-checkbox>
                  <el-checkbox label="CDS" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('CDS') }"></span>
                    编码序列
                  </el-checkbox>
                  <el-checkbox label="exon" class="feature-checkbox">
                    <span class="feature-legend" :style="{ backgroundColor: getFeatureColor('exon') }"></span>
                    外显子
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
                <span class="control-label">每行长度 (Mb):</span>
                <div class="segment-length-controls">
                  <el-button
                    size="small"
                    @mousedown="startDecrease"
                    @mouseup="stopChange"
                    @mouseleave="stopChange"
                    @touchstart="startDecrease"
                    @touchend="stopChange"
                    class="fast-control-btn"
                  >
                    -
                  </el-button>
                  <el-input
                    v-model.number="segmentLengthMb"
                    type="number"
                    :min="0.01"
                    :max="50"
                    :step="0.01"
                    size="small"
                    @change="handleSegmentLengthChange"
                    @blur="validateInput"
                    class="segment-input"
                  />
                  <el-button
                    size="small"
                    @mousedown="startIncrease"
                    @mouseup="stopChange"
                    @mouseleave="stopChange"
                    @touchstart="startIncrease"
                    @touchend="stopChange"
                    class="fast-control-btn"
                  >
                    +
                  </el-button>
                  <el-button
                    size="small"
                    type="default"
                    @click="resetSegmentLength"
                    class="reset-button"
                  >
                    重置1Mb
                  </el-button>
                </div>
              </div>
            </div>

            <!-- 可视化容器 -->
            <div ref="annotationContainer" class="annotation-container"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, nextTick, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { Refresh, Search, Grid, TrendCharts, Loading } from '@element-plus/icons-vue';
import axios from 'axios';
import * as d3 from 'd3';

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
  name: 'AnnotationView',
  components: {
    Refresh,
    Search,
    Grid,
    TrendCharts,
    Loading
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const loading = ref(true);
    const loadingOrganisms = ref(false);
    const loadingAnnotation = ref(false);
    const loadingChromosomes = ref(false);
    const selectedOrganism = ref('');
    const selectedChromosome = ref('');
    const selectedFeatureType = ref('all');
    const allOrganisms = ref([]);
    const organismOptions = ref([]);
    const chromosomeOptions = ref([]);
    const featureTypeOptions = ref(['all']);
    const annotationData = ref([]);
    const annotationStatistics = ref(null);
    const currentPage = ref(1);
    const pageSize = ref(50);
    const totalCount = ref(0);

    // 可视化相关数据
    const viewMode = ref('table'); // 'table' 或 'chart'
    const loadingVisualization = ref(false);
    const annotationContainer = ref(null);
    const displayFeatures = ref([]); // 默认全部不勾选
    const segmentLength = ref(1000000); // 默认1.0Mb
    const chromosomeLength = ref(0);
    const visualizationData = ref([]);
    const contextAccession = ref('');
    const contextAssemblyId = ref('');
    const contextAnnotationId = ref('');
    const hierarchyAssemblies = ref([]);
    const loadedHierarchyAccession = ref('');
    const routeSyncInProgress = ref(false);

    // 计算属性：以Mb为单位的分段长度
    const segmentLengthMb = computed({
      get: () => {
        const mbValue = segmentLength.value / 1000000;
        return Math.round(mbValue * 100) / 100; // 始终保留两位小数
      },
      set: (value) => {
        segmentLength.value = Math.round(value * 1000000); // 转换为bp并四舍五入
      }
    });

    const buildNormalizedQuery = ({ accession, assembly, annotation }) => {
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

      if (
        currentAccession === targetAccession &&
        currentAssembly === targetAssembly &&
        currentAnnotation === targetAnnotation &&
        !routeHasLegacyOrganism
      ) {
        return;
      }

      routeSyncInProgress.value = true;
      try {
        await router.replace({
          path: route.path,
          query
        });
      } finally {
        routeSyncInProgress.value = false;
      }
    };

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
      if (!accession) {
        hierarchyAssemblies.value = [];
        loadedHierarchyAccession.value = '';
        return;
      }

      if (loadedHierarchyAccession.value === accession && hierarchyAssemblies.value.length) {
        return;
      }

      try {
        const response = await axios.get(`/files/accessions/${accession}/`);
        hierarchyAssemblies.value = response.data?.data?.assemblies || [];
        loadedHierarchyAccession.value = accession;
      } catch (error) {
        console.error('获取 accession hierarchy 失败:', error);
        hierarchyAssemblies.value = [];
        loadedHierarchyAccession.value = accession;
      }
    };

    const pickAssembly = (requestedAssemblyId) => {
      if (!hierarchyAssemblies.value.length) {
        return null;
      }

      return (
        hierarchyAssemblies.value.find((item) => matchesId(item, requestedAssemblyId)) ||
        hierarchyAssemblies.value.find((item) => item.is_default) ||
        hierarchyAssemblies.value[0]
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

    // 获取有注释文件的生物体列表
    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;
        const response = await axios.get('/files/query/annotation-organisms/');
        allOrganisms.value = response.data || [];
        organismOptions.value = allOrganisms.value;
      } catch (error) {
        console.error('获取有注释文件的生物体列表失败:', error);
        ElMessage.error('获取有注释文件的生物体列表失败');
      } finally {
        loadingOrganisms.value = false;
      }
    };

    // 获取注释数据
    const fetchAnnotationData = async () => {
      if (!selectedOrganism.value) {
        return;
      }

      try {
        loadingAnnotation.value = true;

        const params = buildAnnotationContextParams({
          featureType: selectedFeatureType.value,
          chromosome: selectedChromosome.value || null,
          page: currentPage.value,
          pageSizeValue: pageSize.value
        });

        const response = await axios.get('/files/query/annotation-data/', { params });
        const data = response.data;

        annotationData.value = data.results || [];
        totalCount.value = data.count || 0;
        annotationStatistics.value = data.statistics || null;

        // 更新染色体选项
        if (data.statistics && data.statistics.chromosomes) {
          chromosomeOptions.value = data.statistics.chromosomes;
          if (
            selectedChromosome.value &&
            !chromosomeOptions.value.includes(selectedChromosome.value)
          ) {
            selectedChromosome.value = '';
          }
        }

        // 更新特征类型选项
        if (data.statistics && data.statistics.feature_types) {
          featureTypeOptions.value = ['all', ...data.statistics.feature_types];
        }

      } catch (error) {
        console.error('获取注释数据失败:', error);
        ElMessage.error('获取注释数据失败');
      } finally {
        loadingAnnotation.value = false;
      }
    };

    // 获取可视化数据（获取更多数据用于绘图）
    const fetchVisualizationData = async () => {
      if (!selectedOrganism.value || !selectedChromosome.value) {
        return;
      }

      try {
        loadingVisualization.value = true;

        const params = buildAnnotationContextParams({
          featureType: 'all',
          chromosome: selectedChromosome.value,
          page: 1,
          pageSizeValue: 10000
        });

        const response = await axios.get('/files/query/annotation-data/', { params });
        const data = response.data;

        visualizationData.value = data.results || [];

        console.log('可视化数据加载完成:', {
          dataLength: visualizationData.value.length,
          organism: selectedOrganism.value,
          chromosome: selectedChromosome.value
        });

        // 获取染色体的实际长度
        await getChromosomeLength();

        // 绘制可视化
        await nextTick();
        console.log('开始绘制可视化, 容器:', annotationContainer.value);
        drawAnnotationVisualization();

      } catch (error) {
        console.error('获取可视化数据失败:', error);
        ElMessage.error('获取可视化数据失败');
      } finally {
        loadingVisualization.value = false;
      }
    };

    // 获取染色体长度
    const getChromosomeLength = async () => {
      if (!selectedOrganism.value || !selectedChromosome.value) {
        return;
      }

      try {
        const params = buildAnnotationContextParams({
          chromosome: selectedChromosome.value
        });

        const response = await axios.get('/files/query/chromosome-length/', { params });
        chromosomeLength.value = response.data.length;
        console.log('染色体实际长度:', chromosomeLength.value, 'bp');
        console.log('染色体实际长度:', (chromosomeLength.value / 1000000).toFixed(2), 'Mb');
      } catch (error) {
        console.error('获取染色体长度失败:', error);
        // 如果获取失败，使用注释数据中的最大位置作为备选
        if (visualizationData.value.length > 0) {
          chromosomeLength.value = Math.max(...visualizationData.value.map(d => d.end));
          console.log('使用注释数据计算的染色体长度:', chromosomeLength.value);
        }
      }
    };

    // 绘制注释可视化
    const drawAnnotationVisualization = () => {
      console.log('drawAnnotationVisualization 被调用', {
        container: annotationContainer.value,
        organism: selectedOrganism.value,
        chromosome: selectedChromosome.value,
        dataLength: visualizationData.value.length
      });

      if (!annotationContainer.value || !selectedOrganism.value || !selectedChromosome.value) {
        console.log('绘制条件不满足，退出');
        return;
      }

      // 清除之前的内容
      d3.select(annotationContainer.value).selectAll("*").remove();

      const container = d3.select(annotationContainer.value);
      const containerRect = annotationContainer.value.getBoundingClientRect();
      const width = Math.max(800, containerRect.width);

      // 过滤要显示的特征类型
      const filteredData = visualizationData.value.filter(d =>
        displayFeatures.value.includes(d.feature)
      );

      if (filteredData.length === 0) {
        container.append("div")
          .style("text-align", "center")
          .style("padding", "50px")
          .style("color", "#999")
          .text("没有要显示的注释特征");
        return;
      }

      // 计算分段参数
      const segmentLen = segmentLength.value;
      const numSegments = Math.ceil(chromosomeLength.value / segmentLen);
      const margin = { top: 50, right: 50, bottom: 50, left: 50 };
      const segmentWidth = width - margin.left - margin.right;

      console.log('绘制参数:', {
        chromosomeLength: chromosomeLength.value,
        segmentLen: segmentLen,
        numSegments: numSegments,
        segmentWidth: segmentWidth
      });

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
        const featureTypeHeight = displayFeatures.value.length * 8; // 每种特征类型8px（减少）
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
      segmentInfos.forEach((segmentInfo, i) => {
        const { start: segmentStart, end: segmentEnd, height: segmentHeight, y: segmentY } = segmentInfo;

        // 计算该分段的实际宽度（最后一行可能不满整行）
        const actualSegmentLength = segmentEnd - segmentStart;
        const actualSegmentWidth = (actualSegmentLength / segmentLen) * segmentWidth;

        console.log(`分段 ${i}:`, {
          segmentStart: segmentStart,
          segmentEnd: segmentEnd,
          actualSegmentLength: actualSegmentLength,
          actualSegmentWidth: actualSegmentWidth,
          segmentLen: segmentLen
        });

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
          .text(`${(segmentStart / 1000000).toFixed(1)} Mb`);

        // 添加分段标签 - 右侧显示终止位置
        svg.append("text")
          .attr("x", margin.left + actualSegmentWidth + 10)
          .attr("y", segmentY + segmentHeight / 2)
          .attr("text-anchor", "start")
          .attr("dominant-baseline", "middle")
          .style("font-size", "12px")
          .style("fill", "#666")
          .text(`${(segmentEnd / 1000000).toFixed(1)} Mb`);

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
          const trackHeight = 6; // 减少轨道高度
          const trackSpacing = 1; // 减少轨道间距
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
            const baseTrackY = segmentY + 8 + typeIndex * 15; // 每种特征类型占15px（减少）
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
                    位置: ${feature.start.toLocaleString()} - ${feature.end.toLocaleString()}<br/>
                    长度: ${feature.length.toLocaleString()} bp<br/>
                    链: ${feature.strand}<br/>
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

    // 重置分段长度为1Mb
    const resetSegmentLength = () => {
      segmentLengthMb.value = 1.00;
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
      const newValue = Math.min(50, segmentLengthMb.value + 0.01);
      segmentLengthMb.value = Math.round(newValue * 100) / 100; // 保持精度
      handleSegmentLengthChange();
    };

    const decreaseValue = () => {
      const newValue = Math.max(0.01, segmentLengthMb.value - 0.01);
      segmentLengthMb.value = Math.round(newValue * 100) / 100; // 保持精度
      handleSegmentLengthChange();
    };

    const validateInput = () => {
      if (segmentLengthMb.value < 0.01) {
        segmentLengthMb.value = 0.01;
      } else if (segmentLengthMb.value > 50) {
        segmentLengthMb.value = 50;
      }
      // 保持两位小数精度
      segmentLengthMb.value = Math.round(segmentLengthMb.value * 100) / 100;
      handleSegmentLengthChange();
    };

    // 更新可视化
    const updateVisualization = () => {
      if (viewMode.value === 'chart' && selectedOrganism.value && selectedChromosome.value) {
        drawAnnotationVisualization();
      }
    };

    const clearContextData = () => {
      contextAccession.value = '';
      contextAssemblyId.value = '';
      contextAnnotationId.value = '';
      hierarchyAssemblies.value = [];
      loadedHierarchyAccession.value = '';
      selectedOrganism.value = '';
      selectedChromosome.value = '';
      selectedFeatureType.value = 'all';
      currentPage.value = 1;
      annotationData.value = [];
      totalCount.value = 0;
      annotationStatistics.value = null;
      chromosomeOptions.value = [];
      featureTypeOptions.value = ['all'];
      visualizationData.value = [];
      chromosomeLength.value = 0;
    };

    const syncRouteContext = async () => {
      const accession = normalizeQueryValue(route.query.accession) || normalizeQueryValue(route.query.organism);
      const requestedAssemblyId = normalizeQueryValue(route.query.assembly);
      const requestedAnnotationId = normalizeQueryValue(route.query.annotation);

      if (!accession) {
        clearContextData();
        return;
      }

      selectedOrganism.value = accession;
      contextAccession.value = accession;

      await fetchAccessionHierarchy(accession);

      const assembly = pickAssembly(requestedAssemblyId);
      const annotation = pickAnnotation(assembly, requestedAnnotationId);

      contextAssemblyId.value = assembly?.id ? String(assembly.id) : '';
      contextAnnotationId.value = annotation?.id ? String(annotation.id) : '';

      if (allOrganisms.value.length && !allOrganisms.value.includes(accession)) {
        organismOptions.value = Array.from(new Set([accession, ...allOrganisms.value]));
      }

      await replaceRouteQuery(buildNormalizedQuery({
        accession,
        assembly: assembly?.id || '',
        annotation: annotation?.id || ''
      }));
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
        ElMessage.error('获取数据失败');
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
        ElMessage.warning('Please enter an Accession.');
        return;
      }

      const accession = allOrganisms.value.find(
        item => normalizeAccession(item) === normalizeAccession(keyword)
      );
      if (!accession) {
        ElMessage.warning(`No exact Accession match: ${keyword}`);
        return;
      }

      await handleOrganismChange(accession);
    };

    const handleAccessionSelect = async (item) => {
      await handleOrganismChange(item?.value || '');
    };

    // 生物体选择变化
    const handleOrganismChange = async (value) => {
      selectedOrganism.value = value;
      selectedChromosome.value = '';
      selectedFeatureType.value = 'all';
      currentPage.value = 1;

      if (value) {
        contextAccession.value = value;
        contextAssemblyId.value = '';
        contextAnnotationId.value = '';
        hierarchyAssemblies.value = [];
        loadedHierarchyAccession.value = '';
        visualizationData.value = [];
        chromosomeLength.value = 0;
        await replaceRouteQuery(buildNormalizedQuery({
          accession: value
        }));
        await handleRouteParams();
      } else {
        clearContextData();
        await replaceRouteQuery({});
      }
    };

    // 染色体选择变化
    const handleChromosomeChange = async (value) => {
      selectedChromosome.value = value;
      currentPage.value = 1;
      if (value) {
        if (viewMode.value === 'table') {
          await fetchAnnotationData();
        } else if (viewMode.value === 'chart') {
          await fetchVisualizationData();
        }
      }
    };

    // 特征类型选择变化
    const handleFeatureTypeChange = (value) => {
      selectedFeatureType.value = value;
      currentPage.value = 1;
      fetchAnnotationData();
    };

    // 分页大小变化
    const handleSizeChange = (size) => {
      pageSize.value = size;
      currentPage.value = 1;
      fetchAnnotationData();
    };

    // 当前页变化
    const handleCurrentChange = (page) => {
      currentPage.value = page;
      fetchAnnotationData();
    };

    // 处理URL参数
    const handleRouteParams = async () => {
      await syncRouteContext();
      await fetchFiles();
    };

    watch(
      () => [route.query.accession, route.query.organism, route.query.assembly, route.query.annotation],
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

    // 监听视图模式变化
    watch(viewMode, async (newMode) => {
      if (newMode === 'chart' && selectedOrganism.value && selectedChromosome.value) {
        await fetchVisualizationData();
      }
    });

    // 监听生物体和染色体选择，在图形模式下自动加载数据
    watch([selectedOrganism, selectedChromosome], async ([newOrganism, newChromosome]) => {
      if (viewMode.value === 'chart' && newOrganism && newChromosome) {
        await fetchVisualizationData();
      }
    });

    onMounted(async () => {
      await fetchOrganisms();
      await handleRouteParams();
    });

    return {
      loading,
      loadingOrganisms,
      loadingAnnotation,
      loadingChromosomes,
      loadingVisualization,
      selectedOrganism,
      selectedChromosome,
      selectedFeatureType,
      organismOptions,
      chromosomeOptions,
      featureTypeOptions,
      annotationData,
      annotationStatistics,
      currentPage,
      pageSize,
      totalCount,
      viewMode,
      annotationContainer,
      displayFeatures,
      segmentLength,
      segmentLengthMb,
      fetchFiles,
      fetchOrganisms,
      fetchAnnotationData,
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
      handleAccessionSearch,
      handleAccessionSelect,
      handleOrganismChange,
      handleChromosomeChange,
      handleFeatureTypeChange,
      handleSizeChange,
      handleCurrentChange,
      handleRouteParams
    };
  }
};
</script>

<style scoped>
.annotation-view {
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
  max-width: 1200px;
  gap: 16px;
}

.search-icon {
  color: #606266;
  margin-right: 8px;
}

.search-select {
  width: 100%;
}

.accession-search-button {
  flex-shrink: 0;
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
  padding: 40px 20px;
  text-align: center;
}

.content-container {
  padding: 20px 0;
}

.annotation-info h3 {
  color: #1a56db;
  margin-bottom: 16px;
}

.annotation-info p {
  color: #606266;
  line-height: 1.6;
}

.data-stats {
  background: #f0f5ff;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 20px;
  border-left: 4px solid #1a56db;
}

.data-stats p {
  margin: 0;
  color: #1a56db;
  font-size: 14px;
}

.divider {
  width: 1px;
  height: 24px;
  background-color: #e4e7ed;
  margin: 0 8px;
}

.chromosome-select,
.feature-select {
  display: flex;
  align-items: center;
  gap: 8px;
}

.select-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}

.chromosome-dropdown,
.feature-dropdown {
  min-width: 150px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-weight: 500;
  color: #606266;
}

.stat-value {
  font-weight: 600;
  color: #1a56db;
  font-size: 16px;
}

.annotation-table {
  margin-top: 24px;
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
  min-height: 400px;
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
</style>

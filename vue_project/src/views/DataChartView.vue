<template>
  <div class="data-chart-view">
    <!-- 复用数据一览表的标题样式 -->
    <div class="page-header">
      <h2 class="title">{{ $t('page.dataChart.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.dataChart.refreshData')" placement="top">
          <el-button circle size="small" @click="refreshData" :loading="loading">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip :content="$t('page.dataChart.exportChart')" placement="top">
          <el-button circle size="small" @click="exportChart">
            <el-icon><Download /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- 复用数据一览表的搜索下拉框 -->
    <div class="search-container">
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-select
          v-model="selectedOrganism"
          filterable
          remote
          :placeholder="$t('page.dataChart.searchPlaceholder')"
          :remote-method="searchOrganisms"
          :loading="loadingOrganisms"
          clearable
          @change="handleOrganismChange"
          @clear="handleOrganismChange"
          class="search-select"
          popper-class="search-popper"
          :teleported="false"
        >
          <el-option
            v-for="item in organismOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </div>

      <!-- 图/表切换按钮 -->
      <div class="view-toggle">
        <el-button-group>
          <el-button
            :type="viewMode === 'card' ? 'primary' : 'default'"
            @click="viewMode = 'card'"
            size="small">
            <el-icon><Grid /></el-icon>
            {{ $t('page.dataChart.cardView') }}
          </el-button>
          <el-button
            :type="viewMode === 'chart' ? 'primary' : 'default'"
            @click="viewMode = 'chart'"
            size="small">
            <el-icon><TrendCharts /></el-icon>
            {{ $t('page.dataChart.chartView') }}
          </el-button>
        </el-button-group>
      </div>
    </div>

    <!-- 三级联动容器 - 简化版 -->
    <div class="chart-container">
      <!-- 卡片模式 -->
      <template v-if="viewMode === 'card'">
        <!-- 左侧：亚群级别 -->
        <div class="left-panel">
          <h4 class="panel-title">{{ $t('page.dataChart.subPopulationDistribution') }}</h4>

          <!-- 亚群列表 -->
          <div class="subpop-list">
            <div
              v-for="subPop in subPopulations"
              :key="subPop.name"
              class="subpop-item"
              :class="{ active: selectedSubPopulation === subPop.name }"
              @click="selectSubPopulation(subPop.name)"
            >
              <div
                class="subpop-color"
                :style="{ backgroundColor: subPop.color }"
              ></div>
              <div class="subpop-info">
                <div class="subpop-name">{{ subPop.name }}</div>
                <div class="subpop-count">{{ subPop.count }} {{ $t('page.dataChart.species') }}</div>
              </div>
              <div class="subpop-percentage">
                {{ Math.round((subPop.count / totalSpeciesCount) * 100) }}%
              </div>
            </div>
          </div>

          <div class="panel-info">
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.totalSubPopulations') }}</span>
              <span class="info-value">{{ subPopulations.length }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.currentSelection') }}</span>
              <span class="info-value">{{ selectedSubPopulation || $t('page.dataChart.none') }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 图表模式 -->
      <template v-else>
        <!-- 左侧：亚群分布饼状图 -->
        <div class="left-panel chart-panel">
          <h4 class="panel-title">{{ $t('page.dataChart.subPopulationDistribution') }}</h4>
          <div class="chart-wrapper">
            <div ref="pieChartRef" class="pie-chart"></div>
          </div>
          <div class="panel-info">
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.totalSubPopulations') }}</span>
              <span class="info-value">{{ subPopulations.length }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.currentSelection') }}</span>
              <span class="info-value">{{ selectedSubPopulation || $t('page.dataChart.none') }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 中间：物种级别 -->
      <template v-if="viewMode === 'card'">
        <div class="center-panel">
          <h4 class="panel-title">
            {{ selectedSubPopulation }} {{ $t('page.dataChart.speciesInSubPopulation') }}
          </h4>
          <div class="species-grid" ref="speciesGridRef">
            <div
              v-for="species in displayedSpecies"
              :key="species.accession"
              :ref="el => { if (selectedSpecies === species.accession) selectedSpeciesRef = el }"
              class="species-item"
              :class="{ active: selectedSpecies === species.accession }"
              @click="selectSpecies(species.accession)"
            >
              <div class="species-name">{{ species.accession }}</div>
              <div class="species-info">
                <span class="species-subpop">{{ species.info.sub_population || $t('page.dataChart.unknown') }}</span>
                <span v-if="species.info.longitude && species.info.latitude" class="species-location">
                  📍 {{ species.info.longitude.toFixed(2) }}, {{ species.info.latitude.toFixed(2) }}
                </span>
              </div>
            </div>
          </div>
          <div class="panel-info">
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.speciesCount') }}</span>
              <span class="info-value">{{ currentSpeciesCount }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.currentSelection') }}</span>
              <span class="info-value">{{ currentDisplaySpecies }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 图表模式中间面板 -->
      <template v-else>
        <div class="center-panel chart-panel">
          <h4 class="panel-title">
            {{ selectedSubPopulation }} {{ $t('page.dataChart.speciesInSubPopulation') }}
          </h4>
          <div class="chart-wrapper">
            <div ref="speciesTreeChartRef" class="species-tree-chart"></div>
          </div>
          <div class="panel-info">
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.speciesCount') }}</span>
              <span class="info-value">{{ currentSpeciesCount }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.currentSelection') }}</span>
              <span class="info-value">{{ currentDisplaySpecies }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 右侧：功能模块级别 -->
      <template v-if="viewMode === 'card'">
        <div class="right-panel">
          <h4 class="panel-title">{{ $t('page.dataChart.dataTypes') }}</h4>
          <div class="modules-grid">
            <div
              v-for="(config, key) in availableModuleConfig"
              :key="key"
              class="module-item"
              @click="goToModule(key)"
            >
              <div class="module-icon">{{ config.icon }}</div>
              <div class="module-info">
                <div class="module-name">{{ config.name }}</div>
                <div class="module-desc">{{ $t('page.dataChart.clickToViewDetails') }}</div>
              </div>
              <div
                class="module-color"
                :style="{ backgroundColor: config.color }"
              ></div>
            </div>
          </div>
          <div class="panel-info">
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.dataTypesLabel') }}</span>
              <span class="info-value">{{ availableDataTypesCount }}{{ $t('page.dataChart.types') }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.targetSpecies') }}</span>
              <span class="info-value">{{ currentDisplaySpecies }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 图表模式右侧面板 -->
      <template v-else>
        <div class="right-panel chart-panel">
          <h4 class="panel-title">{{ $t('page.dataChart.dataTypes') }}</h4>
          <div class="chart-wrapper">
            <div ref="networkChartRef" class="network-chart"></div>
          </div>
          <div class="panel-info">
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.dataTypesLabel') }}</span>
              <span class="info-value">{{ availableDataTypesCount }}{{ $t('page.dataChart.types') }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('page.dataChart.targetSpecies') }}</span>
              <span class="info-value">{{ currentDisplaySpecies }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed, nextTick, watch } from 'vue';
import { Refresh, Download, Search, Grid, TrendCharts } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import * as echarts from 'echarts';

export default {
  name: 'DataChartView',
  components: {
    Refresh,
    Download,
    Search,
    Grid,
    TrendCharts
  },
  setup() {
    const router = useRouter();
    const { t } = useI18n();
    const loading = ref(true);
    const showLabels = ref(true);

    // 下拉搜索框相关
    const loadingOrganisms = ref(false);
    const selectedOrganism = ref(localStorage.getItem('dataChart_selectedOrganism') || '');
    const allOrganisms = ref([]);
    const organismOptions = ref([]);

    // 选择状态（从缓存中恢复）
    const selectedSubPopulation = ref(localStorage.getItem('dataChart_selectedSubPopulation') || 'XI');
    const selectedSpecies = ref(localStorage.getItem('dataChart_selectedSpecies') || '');

    // DOM引用
    const speciesGridRef = ref(null);
    const selectedSpeciesRef = ref(null);
    const pieChartRef = ref(null);
    const networkChartRef = ref(null);
    const speciesTreeChartRef = ref(null);

    // 视图模式
    const viewMode = ref('card'); // 'card' 或 'chart'

    // 数据相关
    const supplementaryData = ref({});
    const allSubPopulations = ref([]);
    const currentSpeciesData = ref(null);

    // 预定义亚群配置
    const predefinedSubPopulationConfig = {
      'cA': { color: '#2563eb', name: 'cA亚群' },
      'cB': { color: '#dc2626', name: 'cB亚群' },
      'GJ': { color: '#16a34a', name: 'GJ亚群' },
      'XI': { color: '#9333ea', name: 'XI亚群' },
      'WILD': { color: '#ea580c', name: 'WILD亚群' },
      'O.glaberrima': { color: '#db2777', name: 'O.glaberrima' },
      'Unknown': { color: '#64748b', name: 'Unknown' }
    };

    // 动态颜色池，用于新增亚群（去除重复颜色）
    const dynamicColorPool = [
      '#f97316', '#84cc16', '#06b6d4', '#8b5cf6', '#f59e0b',
      '#ef4444', '#10b981', '#3b82f6', '#f43f5e', '#6366f1',
      '#14b8a6', '#eab308', '#a855f7', '#0891b2', '#65a30d',
      '#dc2626', '#059669', '#2563eb', '#e11d48', '#7c3aed',
      '#0d9488', '#ca8a04', '#9333ea', '#0284c7', '#16a34a'
    ];

    // 获取亚群配置的函数
    const getSubPopulationConfig = (subPopName) => {
      if (predefinedSubPopulationConfig[subPopName]) {
        return predefinedSubPopulationConfig[subPopName];
      }

      const key = String(subPopName || 'Unknown');
      const colorIndex = Array.from(key).reduce(
        (sum, char) => sum + char.charCodeAt(0),
        0
      ) % dynamicColorPool.length;

      return {
        color: dynamicColorPool[colorIndex],
        name: `${subPopName}亚群`
      };
    };

    // 功能模块配置
    const moduleConfig = {
      'accession': { color: '#8b5cf6', name: 'Accession', icon: '📋' },
      'sequence': { color: '#06b6d4', name: 'Sequence data', icon: '🧬' },
      'genome': { color: '#3b82f6', name: 'Genome', icon: '🔬' },
      'annotation': { color: '#10b981', name: 'Annotation', icon: '📝' },
      'codon': { color: '#f59e0b', name: 'Codon', icon: '🔤' },
      'blocks': { color: '#ef4444', name: 'Core&Variable Blocks', icon: '🧱' },
      'location': { color: '#16a34a', name: 'Location', icon: '📍' }
    };

    const hasValidCoordinate = (value) => {
      return value !== null &&
        value !== undefined &&
        value !== '' &&
        value !== '-' &&
        !isNaN(parseFloat(value));
    };

    const hasUsableFileForCategories = (files, categories) => {
      return (files || []).some((file) => {
        const fileSize = Number(file?.size);
        return categories.includes(file?.category) && Number.isFinite(fileSize) && fileSize > 0;
      });
    };

    const pickDefaultAssembly = (assemblies) => {
      if (!Array.isArray(assemblies) || assemblies.length === 0) {
        return null;
      }

      return assemblies.find((assembly) => assembly?.is_default) || assemblies[0];
    };

    const pickDefaultAnnotation = (assembly) => {
      const annotations = Array.isArray(assembly?.annotations) ? assembly.annotations : [];

      if (!annotations.length) {
        return null;
      }

      return annotations.find((annotation) => annotation?.is_default) || annotations[0];
    };

    const buildEmptySpeciesData = (speciesName) => ({
      accession: speciesName,
      seqData: null,
      longitude: supplementaryData.value[speciesName]?.longitude ?? null,
      latitude: supplementaryData.value[speciesName]?.latitude ?? null,
      assemblyId: null,
      annotationId: null,
      genome: false,
      annotation: false,
      codon: false,
      coreBlocks: false,
      centromere: false,
      TEs: false,
      miRNA: false,
      tRNA: false,
      rRNA: false,
      hasTranscriptome: false,
      assemblyFiles: [],
      annotationFiles: []
    });

    const normalizeAccessionDetailData = (accession, payload) => {
      const accessionInfo = payload?.accession || {};
      const defaultAssembly = pickDefaultAssembly(payload?.assemblies);
      const defaultAnnotation = pickDefaultAnnotation(defaultAssembly);
      const assemblyFiles = defaultAssembly?.files || [];
      const annotationFiles = defaultAnnotation?.files || [];

      return {
        accession: accessionInfo.accession || accession,
        seqData: accessionInfo.seq_data || null,
        longitude: accessionInfo.longitude ?? null,
        latitude: accessionInfo.latitude ?? null,
        assemblyId: defaultAssembly?.id ?? null,
        annotationId: defaultAnnotation?.id ?? null,
        genome: hasUsableFileForCategories(assemblyFiles, ['genome']),
        annotation: hasUsableFileForCategories(annotationFiles, ['annotation']),
        codon: hasUsableFileForCategories(assemblyFiles, ['codon']),
        coreBlocks: hasUsableFileForCategories(assemblyFiles, ['coreBlocks']),
        centromere: hasUsableFileForCategories(assemblyFiles, ['centromere']),
        TEs: hasUsableFileForCategories(assemblyFiles, ['TEs']),
        miRNA: hasUsableFileForCategories(assemblyFiles, ['miRNA']),
        tRNA: hasUsableFileForCategories(assemblyFiles, ['tRNA']),
        rRNA: hasUsableFileForCategories(assemblyFiles, ['rRNA']),
        hasTranscriptome: hasUsableFileForCategories(assemblyFiles, [
          'transcriptome.all',
          'transcriptome.root',
          'transcriptome.stem',
          'transcriptome.leaf',
          'transcriptome.panicles',
          'transcriptome.shoot'
        ]),
        assemblyFiles,
        annotationFiles
      };
    };

    // 计算亚群统计
    const subPopulations = computed(() => {
      const stats = {};

      Object.entries(supplementaryData.value).forEach(([, info]) => {
        const subPop = info.sub_population || 'Unknown';
        if (!stats[subPop]) {
          stats[subPop] = 0;
        }
        stats[subPop]++;
      });

      const result = Object.entries(stats).map(([name, count]) => {
        const config = getSubPopulationConfig(name);
        return {
          name,
          count,
          color: config.color
        };
      })
      // 按照物种数量从大到小排序
      .sort((a, b) => b.count - a.count);

      console.log('亚群统计:', result);
      return result;
    });

    // 计算当前亚群的物种列表
    const currentSpeciesList = computed(() => {
      const targetSubPop = selectedSubPopulation.value || 'XI';
      return Object.entries(supplementaryData.value)
        .filter(([, info]) => (info.sub_population || 'Unknown') === targetSubPop)
        .map(([accession, info]) => ({ accession, info }));
    });

    // 计算当前物种数量
    const currentSpeciesCount = computed(() => {
      return currentSpeciesList.value.length;
    });

    // 计算总物种数量
    const totalSpeciesCount = computed(() => {
      const count = Object.keys(supplementaryData.value).length;
      console.log('总物种数量:', count);
      return count;
    });

    // 显示的物种列表（按物种名称排序）
    const displayedSpecies = computed(() => {
      return [...currentSpeciesList.value]
        .sort((a, b) => a.accession.localeCompare(b.accession)); // 按物种名称排序
    });

    // 当前显示的物种名称
    const currentDisplaySpecies = computed(() => {
      return selectedSpecies.value || getDefaultSpecies();
    });

    // 当前物种可用的模块配置
    const availableModuleConfig = computed(() => {
      const data = currentSpeciesData.value;
      const currentSpecies = selectedSpecies.value || getDefaultSpecies();
      const supplementary = supplementaryData.value[currentSpecies] || {};
      const hasLocation =
        (hasValidCoordinate(data?.longitude) || hasValidCoordinate(supplementary.longitude)) &&
        (hasValidCoordinate(data?.latitude) || hasValidCoordinate(supplementary.latitude));

      return {
        accession: moduleConfig.accession,
        ...(data?.seqData ? { sequence: moduleConfig.sequence } : {}),
        ...(data?.genome ? { genome: moduleConfig.genome } : {}),
        ...(data?.annotation ? { annotation: moduleConfig.annotation } : {}),
        ...(data?.codon ? { codon: moduleConfig.codon } : {}),
        ...(data?.coreBlocks || data?.centromere || data?.TEs || data?.miRNA || data?.tRNA || data?.rRNA
          ? { blocks: moduleConfig.blocks }
          : {}),
        ...(hasLocation ? { location: moduleConfig.location } : {})
      };
    });

    // 当前物种可用的数据类型数量
    const availableDataTypesCount = computed(() => {
      return Object.keys(availableModuleConfig.value).length;
    });

    // 选择亚群
    const selectSubPopulation = (subPopName) => {
      selectedSubPopulation.value = subPopName;

      // 清空搜索框
      selectedOrganism.value = '';

      // 重置滚动条到顶部
      resetScrollToTop();

      // 自动选择该亚群排序后的第一个物种
      const speciesInSubPop = Object.entries(supplementaryData.value)
        .filter(([, info]) => (info.sub_population || 'Unknown') === subPopName)
        .map(([accession, info]) => ({ accession, info }))
        .sort((a, b) => a.accession.localeCompare(b.accession)); // 按物种名称排序

      if (speciesInSubPop.length > 0) {
        selectedSpecies.value = speciesInSubPop[0].accession; // 选择排序后的第一个物种
      } else {
        selectedSpecies.value = ''; // 如果没有物种，重置选择
      }

      // 保存选择状态到缓存
      saveSelectionToCache();
    };

    // 选择物种
    const selectSpecies = (speciesName) => {
      selectedSpecies.value = speciesName;
      // 清空搜索框
      selectedOrganism.value = '';
      // 保存选择状态到缓存
      saveSelectionToCache();
      // 自动滚动到选中的物种
      scrollToSelectedSpecies();
    };

    // 获取默认物种（当前亚群排序后的第一个物种）
    const getDefaultSpecies = () => {
      const speciesInSubPop = Object.entries(supplementaryData.value)
        .filter(([, info]) => (info.sub_population || 'Unknown') === selectedSubPopulation.value)
        .map(([accession, info]) => ({ accession, info }))
        .sort((a, b) => a.accession.localeCompare(b.accession)); // 按物种名称排序

      return speciesInSubPop.length > 0 ? speciesInSubPop[0].accession : 'IR64';
    };

    // 初始化默认选择
    const initializeDefaultSelection = () => {
      if (!selectedSpecies.value && selectedSubPopulation.value) {
        selectedSpecies.value = getDefaultSpecies();
      }
    };

    // 跳转到模块页面
    const goToModule = async (moduleKey) => {
      const targetSpecies = selectedSpecies.value || getDefaultSpecies();
      const contextQuery = {
        accession: targetSpecies
      };

      if (currentSpeciesData.value?.assemblyId) {
        contextQuery.assembly = String(currentSpeciesData.value.assemblyId);
      }

      if (currentSpeciesData.value?.annotationId) {
        contextQuery.annotation = String(currentSpeciesData.value.annotationId);
      }

      // 如果是sequence模块，需要获取seqData URL并在新窗口打开
      if (moduleKey === 'sequence') {
        try {
          if (currentSpeciesData.value?.seqData) {
            window.open(currentSpeciesData.value.seqData, '_blank');
            ElMessage.success(t('messages.openingPage', { species: targetSpecies, module: moduleConfig[moduleKey].name }));
          } else {
            ElMessage.warning(t('messages.sequenceDataNotAvailable', { species: targetSpecies }));
          }
        } catch (error) {
          console.error('获取序列数据失败:', error);
          ElMessage.error(t('messages.getSequenceDataFailed'));
        }
        return;
      }

      // 其他模块的路由跳转
      let path = '';
      switch (moduleKey) {
        case 'accession':
          path = '/accession-card';
          break;
        case 'genome':
          path = '/genome-card';
          break;
        case 'annotation':
          path = '/annotation-card';
          break;
        case 'codon':
          path = '/codon-card';
          break;
        case 'blocks':
          path = '/core-variable-blocks-card';
          break;
        case 'location':
          path = '/accession-map';
          break;
        default:
          path = '/accession-card';
      }

      router.push({
        path: path,
        query: moduleKey === 'codon' || moduleKey === 'location'
          ? { organism: targetSpecies }
          : contextQuery
      });
      ElMessage.success(t('messages.jumpingToPage', { species: targetSpecies, module: moduleConfig[moduleKey].name }));
    };

    // 获取补充数据
    const fetchSupplementaryData = async () => {
      try {
        const response = await axios.get('/files/query/supplementary-data/');
        supplementaryData.value = response.data || {};
        console.log('补充数据加载成功:', Object.keys(supplementaryData.value).length, '条记录');

        // 如果没有数据，使用测试数据
        if (Object.keys(supplementaryData.value).length === 0) {
          console.log('使用测试数据');
          supplementaryData.value = {
            'IR64': { sub_population: 'XI' },
            'IRIS_313-10000': { sub_population: 'cA' },
            'IRIS_313-10001': { sub_population: 'cB' },
            'IRIS_313-10002': { sub_population: 'GJ' },
            'IRIS_313-10003': { sub_population: 'WILD' },
            'IRIS_313-10004': { sub_population: 'O.glaberrima' },
            'IRIS_313-10005': { sub_population: 'XI' },
            'IRIS_313-10006': { sub_population: 'cA' }
          };
        }
      } catch (error) {
        console.error('获取补充数据失败:', error);
        ElMessage.error(t('messages.getSupplementaryDataFailed'));

        // 使用测试数据
        supplementaryData.value = {
          'IR64': { sub_population: 'XI' },
          'IRIS_313-10000': { sub_population: 'cA' },
          'IRIS_313-10001': { sub_population: 'cB' },
          'IRIS_313-10002': { sub_population: 'GJ' },
          'IRIS_313-10003': { sub_population: 'WILD' },
          'IRIS_313-10004': { sub_population: 'O.glaberrima' }
        };
      }
    };

    // 获取亚群列表
    const fetchSubPopulations = async () => {
      try {
        const response = await axios.get('/files/query/sub-populations/');
        allSubPopulations.value = response.data || [];
      } catch (error) {
        console.error('获取亚群列表失败:', error);
        ElMessage.error(t('messages.getSubPopulationsFailed'));
      }
    };

    // 获取当前物种的详细数据
    const fetchCurrentSpeciesData = async (speciesName) => {
      if (!speciesName) return;

      try {
        const response = await axios.get(`/files/accessions/${speciesName}/`);
        const payload = response.data?.data || null;

        if (response.data?.success && payload) {
          currentSpeciesData.value = normalizeAccessionDetailData(speciesName, payload);
        } else {
          currentSpeciesData.value = buildEmptySpeciesData(speciesName);
        }
      } catch (error) {
        console.error('获取物种详细数据失败:', error);
        currentSpeciesData.value = buildEmptySpeciesData(speciesName);
      }
    };

    // 刷新数据
    const refreshData = async () => {
      loading.value = true;
      try {
        await Promise.all([
          fetchSupplementaryData(),
          fetchSubPopulations()
        ]);
        // 数据加载完成后初始化默认选择
        await nextTick();
        initializeDefaultSelection();
        ElMessage.success(t('messages.dataRefreshed'));
      } catch (error) {
        ElMessage.error(t('messages.dataRefreshFailed'));
      } finally {
        loading.value = false;
      }
    };

    // 导出数据
    const exportChart = () => {
      const dataToExport = {
        subPopulations: subPopulations.value,
        currentSpecies: currentSpeciesList.value,
        selectedSubPopulation: selectedSubPopulation.value,
        selectedSpecies: selectedSpecies.value
      };

      const dataStr = JSON.stringify(dataToExport, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `rice_data_overview_${new Date().toISOString().split('T')[0]}.json`;
      link.click();
      URL.revokeObjectURL(url);
      ElMessage.success(t('messages.dataExported'));
    };

    // 重置视图
    const resetView = () => {
      selectedSubPopulation.value = 'XI';
      selectedSpecies.value = getDefaultSpecies();
    };

    // 切换标签显示
    const toggleLabels = () => {
      showLabels.value = !showLabels.value;
    };

    // 获取所有生物体列表
    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;
        const response = await axios.get('/files/query/organisms/');
        allOrganisms.value = response.data || [];
        organismOptions.value = allOrganisms.value;
      } catch (error) {
        console.error('获取生物体列表失败:', error);
        ElMessage.error(t('messages.getOrganismsFailed'));
      } finally {
        loadingOrganisms.value = false;
      }
    };

    // 搜索生物体
    const searchOrganisms = (query) => {
      if (query) {
        organismOptions.value = allOrganisms.value.filter(item =>
          item.toLowerCase().includes(query.toLowerCase())
        );
      } else {
        organismOptions.value = allOrganisms.value;
      }
    };

    // 自动滚动到选中的物种
    const scrollToSelectedSpecies = () => {
      nextTick(() => {
        if (selectedSpeciesRef.value && speciesGridRef.value) {
          selectedSpeciesRef.value.scrollIntoView({
            behavior: 'instant',
            block: 'center',
            inline: 'nearest'
          });
        }
      });
    };

    // 重置滚动条到顶部
    const resetScrollToTop = () => {
      nextTick(() => {
        if (speciesGridRef.value) {
          speciesGridRef.value.scrollTop = 0;
        }
      });
    };

    // 保存选择状态到缓存
    const saveSelectionToCache = () => {
      localStorage.setItem('dataChart_selectedSubPopulation', selectedSubPopulation.value);
      localStorage.setItem('dataChart_selectedSpecies', selectedSpecies.value);
      localStorage.setItem('dataChart_selectedOrganism', selectedOrganism.value);
    };

    // 图表实例
    let pieChart = null;
    let networkChart = null;
    let speciesTreeChart = null;

    // 当前展开的首字母分组
    const expandedAlphabetGroup = ref(null);

    // 初始化饼状图
    const initPieChart = () => {
      if (!pieChartRef.value) return;

      pieChart = echarts.init(pieChartRef.value);
      updatePieChart();
    };

    // 更新饼状图数据
    const updatePieChart = () => {
      if (!pieChart) return;

      const totalCount = subPopulations.value.reduce((sum, subPop) => sum + subPop.count, 0);

      const currentSelected = selectedSubPopulation.value;

      const data = subPopulations.value.map(subPop => {
        const percentage = (subPop.count / totalCount * 100);
        const isSelected = subPop.name === currentSelected;

        // 根据选中状态和占比确定标签颜色
        let labelColor;
        if (isSelected) {
          labelColor = percentage > 8 ? '#fff' : '#333';
        } else {
          labelColor = percentage > 8 ? '#f0f0f0' : '#666';
        }

        return {
          name: subPop.name,
          value: subPop.count,
          percentage: percentage,
          isSelected: isSelected,
          itemStyle: {
            color: subPop.color
          },
          label: {
            show: true,
            formatter: percentage > 8 ? `${subPop.name}\n${percentage.toFixed(1)}%` : `${subPop.name} ${percentage.toFixed(1)}%`,
            position: percentage > 8 ? 'inside' : 'outside',
            fontSize: percentage > 8 ? 12 : 11,
            fontWeight: isSelected ? 'bold' : 'normal',
            color: labelColor
          }
        };
      });

      const option = {
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)'
        },
        // 删除图例配置
        series: [
          {
            name: '亚群分布',
            type: 'pie',
            radius: ['45%', '85%'],
            center: ['50%', '50%'], // 居中显示饼图
            avoidLabelOverlap: true,
            itemStyle: {
              borderRadius: 10,
              borderColor: '#fff',
              borderWidth: 2
            },
            label: {
              alignTo: 'labelLine',
              distanceToLabelLine: 5
            },
            emphasis: {
              label: {
                show: true,
                fontSize: '14',
                fontWeight: 'bold'
              }
            },
            labelLine: {
              show: true,
              length: 15,
              length2: 10,
              smooth: 0.2,
              lineStyle: {
                color: '#999',
                width: 1
              }
            },
            data: data
          }
        ]
      };

      pieChart.setOption(option);

      // 添加点击事件
      pieChart.off('click');
      pieChart.on('click', (params) => {
        selectSubPopulation(params.name);
      });
    };

    // 初始化网络图
    const initNetworkChart = () => {
      if (!networkChartRef.value) return;

      networkChart = echarts.init(networkChartRef.value);
      updateNetworkChart();
    };

    // 更新网络图数据
    const updateNetworkChart = () => {
      if (!networkChart) return;

      const targetSpecies = selectedSpecies.value || getDefaultSpecies();

      // 创建节点数据
      const nodes = [
        {
          id: targetSpecies,
          name: targetSpecies,
          x: 0,
          y: 0,
          symbolSize: 50,
          itemStyle: {
            color: '#ff6b6b'
          },
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          }
        }
      ];

      // 添加模块节点 - 使用动态的可用模块配置
      const availableModules = availableModuleConfig.value;
      const moduleKeys = Object.keys(availableModules);
      const angleStep = (2 * Math.PI) / moduleKeys.length;
      const radius = 150;

      moduleKeys.forEach((key, index) => {
        const angle = index * angleStep;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;

        nodes.push({
          id: key,
          name: availableModules[key].name,
          x: x,
          y: y,
          symbolSize: 40,
          itemStyle: {
            color: availableModules[key].color
          },
          label: {
            show: true,
            fontSize: 13
          }
        });
      });

      // 创建连线数据
      const links = moduleKeys.map(key => ({
        source: targetSpecies,
        target: key,
        lineStyle: {
          color: '#ccc',
          width: 2
        }
      }));

      const option = {
        tooltip: {
          trigger: 'item',
          formatter: (params) => {
            if (params.dataType === 'node') {
              return params.data.name;
            }
            return '';
          }
        },
        grid: {
          left: '5%',
          right: '5%',
          top: '5%',
          bottom: '5%'
        },
        series: [
          {
            type: 'graph',
            layout: 'none',
            symbolSize: 40,
            roam: false,
            label: {
              show: true,
              position: 'bottom'
            },
            edgeSymbol: ['none', 'arrow'],
            edgeSymbolSize: [0, 10],
            data: nodes,
            links: links,
            lineStyle: {
              opacity: 0.7,
              curveness: 0.1,
              width: 3
            }
          }
        ]
      };

      networkChart.setOption(option);

      // 添加点击事件
      networkChart.off('click');
      networkChart.on('click', (params) => {
        if (params.dataType === 'node' && params.data.id !== targetSpecies) {
          goToModule(params.data.id);
        }
      });
    };

    // 初始化物种树状图
    const initSpeciesTreeChart = () => {
      if (!speciesTreeChartRef.value) return;

      speciesTreeChart = echarts.init(speciesTreeChartRef.value);
      updateSpeciesTreeChart();
    };

    // 更新物种树状图数据
    const updateSpeciesTreeChart = () => {
      if (!speciesTreeChart) return;

      const currentSubPop = selectedSubPopulation.value;
      const subPopColor = getSubPopulationConfig(currentSubPop).color;
      const speciesCount = displayedSpecies.value.length;

      // 根据物种数量选择不同的展示策略
      if (speciesCount >= 51) {
        // 大量物种：使用首字母分组的两级树状结构
        updateAlphabetGroupedTreeChart(currentSubPop, subPopColor);
        return;
      }

      // 少量物种：构建树状图数据
      const treeData = {
        name: `${currentSubPop}（${currentSpeciesCount.value}）`,
        value: currentSpeciesCount.value,
        itemStyle: {
          color: subPopColor,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          fontSize: 16,
          fontWeight: 'bold',
          color: subPopColor,
          rotate: 0
        },
        children: displayedSpecies.value.map(species => ({
          name: species.accession,
          value: 1,
          itemStyle: {
            color: selectedSpecies.value === species.accession ? '#ff6b6b' : '#e2e8f0',
            borderColor: selectedSpecies.value === species.accession ? '#dc2626' : '#cbd5e1',
            borderWidth: selectedSpecies.value === species.accession ? 3 : 1
          },
          label: {
            show: true,
            fontSize: selectedSpecies.value === species.accession ? 13 : 12,
            color: selectedSpecies.value === species.accession ? '#dc2626' : '#374151',
            fontWeight: selectedSpecies.value === species.accession ? 'bold' : 'normal',
            position: 'bottom'
          },
          // 添加物种的额外信息
          tooltip: {
            formatter: () => {
              const info = species.info;
              let tooltipContent = `<strong>${species.accession}</strong><br/>`;
              tooltipContent += `亚群: ${info.sub_population || '未知'}<br/>`;
              if (info.longitude && info.latitude) {
                tooltipContent += `位置: ${info.longitude.toFixed(2)}, ${info.latitude.toFixed(2)}`;
              }
              return tooltipContent;
            }
          }
        }))
      };

      const option = {
        tooltip: {
          trigger: 'item',
          triggerOn: 'mousemove',
          formatter: (params) => {
            if (params.data.children) {
              // 根节点（亚群）
              const subPopName = params.data.name.split('（')[0]; // 提取亚群名称
              return `<strong>${subPopName} 亚群</strong><br/>物种数量: ${params.data.value}`;
            } else {
              // 叶子节点（物种）
              const species = displayedSpecies.value.find(s => s.accession === params.data.name);
              if (species) {
                let tooltipContent = `<strong>${species.accession}</strong><br/>`;
                tooltipContent += `亚群: ${species.info.sub_population || '未知'}<br/>`;
                if (species.info.longitude && species.info.latitude) {
                  tooltipContent += `位置: ${species.info.longitude.toFixed(2)}, ${species.info.latitude.toFixed(2)}`;
                }
                return tooltipContent;
              }
              return params.data.name;
            }
          }
        },
        series: [
          {
            type: 'tree',
            data: [treeData],
            top: '5%',
            left: '10%',
            bottom: '5%',
            right: '10%',
            symbolSize: (value, params) => {
              // 根据节点类型设置大小
              if (params.data.children) {
                // 根节点（亚群）
                return Math.max(40, Math.min(80, params.data.value * 2));
              } else {
                // 叶子节点（物种）
                return selectedSpecies.value === params.data.name ? 25 : 20;
              }
            },
            label: {
              position: 'inside',
              verticalAlign: 'middle',
              align: 'center',
              fontSize: 12
            },
            leaves: {
              label: {
                position: 'bottom',
                verticalAlign: 'top',
                align: 'center'
              }
            },
            emphasis: {
              focus: 'descendant'
            },
            expandAndCollapse: false,
            animationDuration: 550,
            animationDurationUpdate: 750,
            layout: 'radial',
            orient: 'vertical',
            roam: true,
            initialTreeDepth: 2
          }
        ]
      };

      speciesTreeChart.setOption(option);

      // 添加点击事件
      speciesTreeChart.off('click');
      speciesTreeChart.on('click', (params) => {
        if (!params.data.children) {
          // 点击的是物种节点
          selectSpecies(params.data.name);
        }
      });
    };

    // 生物体选择变化
    const handleOrganismChange = (value) => {
      selectedOrganism.value = value;
      if (value) {
        // 根据选择的物种，找到对应的亚群
        const speciesInfo = supplementaryData.value[value];
        if (speciesInfo) {
          const subPop = speciesInfo.sub_population || 'Unknown';
          selectedSubPopulation.value = subPop;
          selectedSpecies.value = value;
          // 保存选择状态到缓存
          saveSelectionToCache();
          // 自动滚动到选中的物种
          scrollToSelectedSpecies();
        }
      }
    };



    // 监听视图模式变化
    watch(viewMode, (newMode) => {
      if (newMode === 'chart') {
        nextTick(() => {
          initPieChart();
          initNetworkChart();
          initSpeciesTreeChart();
        });
      }
    });

    // 监听亚群数据变化，更新饼状图
    watch(subPopulations, () => {
      if (viewMode.value === 'chart') {
        nextTick(() => {
          updatePieChart();
        });
      }
    }, { deep: true });

    // 监听选中物种变化，更新网络图和树状图
    watch(selectedSpecies, async (newSpecies) => {
      if (newSpecies) {
        // 获取新物种的详细数据，等待完成
        await fetchCurrentSpeciesData(newSpecies);
      }

      if (viewMode.value === 'chart') {
        nextTick(() => {
          updateNetworkChart();
          updateSpeciesTreeChart();
        });
      }
    });

    // 监听物种数据变化，更新网络图
    watch(currentSpeciesData, () => {
      if (viewMode.value === 'chart') {
        nextTick(() => {
          updateNetworkChart();
        });
      }
    });

    // 监听亚群变化，更新饼状图和树状图
    watch(selectedSubPopulation, () => {
      // 重置展开状态
      expandedAlphabetGroup.value = null;

      if (viewMode.value === 'chart') {
        nextTick(() => {
          updatePieChart(); // 添加饼状图更新
          updateSpeciesTreeChart();
        });
      }
    });

    // 监听显示的物种列表变化，更新树状图
    watch(displayedSpecies, () => {
      if (viewMode.value === 'chart') {
        nextTick(() => {
          updateSpeciesTreeChart();
        });
      }
    }, { deep: true });

    onMounted(async () => {
      console.log('DataChartView 组件已挂载');
      await fetchOrganisms();
      await refreshData();

      // 获取默认物种的详细数据
      const defaultSpecies = getDefaultSpecies();
      if (defaultSpecies) {
        await fetchCurrentSpeciesData(defaultSpecies);
      }

      // 恢复缓存的选择状态
      const cachedSpecies = localStorage.getItem('dataChart_selectedSpecies');
      if (cachedSpecies && supplementaryData.value[cachedSpecies]) {
        // 如果缓存的物种存在，恢复选择状态
        selectedOrganism.value = cachedSpecies;
        // 获取缓存物种的详细数据
        await fetchCurrentSpeciesData(cachedSpecies);
        // 延迟执行滚动，确保DOM已渲染
        setTimeout(() => {
          scrollToSelectedSpecies();
        }, 100);
      }

      console.log('数据刷新完成，恢复选择状态:', cachedSpecies);
    });

    // 处理大量物种的首字母分组树状图
    const updateAlphabetGroupedTreeChart = (currentSubPop, subPopColor) => {
      const allSpecies = displayedSpecies.value;

      // 按首字母分组
      const alphabetGroups = {};
      allSpecies.forEach(species => {
        const firstLetter = species.accession.charAt(0).toUpperCase();
        if (!alphabetGroups[firstLetter]) {
          alphabetGroups[firstLetter] = [];
        }
        alphabetGroups[firstLetter].push(species);
      });

      // 找到被选中物种所在的首字母分组
      const selectedSpeciesLetter = selectedSpecies.value ? selectedSpecies.value.charAt(0).toUpperCase() : null;

      // 构建树状图数据
      const alphabetChildren = Object.keys(alphabetGroups)
        .sort()
        .map(letter => {
          const isExpanded = expandedAlphabetGroup.value === letter;
          const hasSelectedSpecies = selectedSpeciesLetter === letter;

          return {
            name: `${letter} (${alphabetGroups[letter].length})`,
            value: alphabetGroups[letter].length,
            itemStyle: {
              color: hasSelectedSpecies ? '#ff6b6b' : (isExpanded ? '#6366f1' : '#94a3b8'),
              borderColor: hasSelectedSpecies ? '#dc2626' : (isExpanded ? '#4f46e5' : '#64748b'),
              borderWidth: hasSelectedSpecies ? 3 : (isExpanded ? 2 : 1)
            },
            label: {
              fontSize: hasSelectedSpecies ? 13 : 12,
              color: hasSelectedSpecies ? '#dc2626' : (isExpanded ? '#fff' : '#374151'),
              fontWeight: 'bold'
            },
            collapsed: expandedAlphabetGroup.value !== letter, // 只有当前选中的分组展开
            children: alphabetGroups[letter].map(species => ({
              name: species.accession,
              value: 1,
              itemStyle: {
                color: selectedSpecies.value === species.accession ? '#ff6b6b' : '#e2e8f0',
                borderColor: selectedSpecies.value === species.accession ? '#dc2626' : '#cbd5e1',
                borderWidth: selectedSpecies.value === species.accession ? 2 : 1
              },
              label: {
                show: true,
                fontSize: selectedSpecies.value === species.accession ? 11 : 10,
                color: selectedSpecies.value === species.accession ? '#dc2626' : '#374151',
                fontWeight: selectedSpecies.value === species.accession ? 'bold' : 'normal',
                position: selectedSpecies.value === species.accession ? 'bottom' : 'bottom'
              }
            }))
          };
        });

      const treeData = {
        name: `${currentSubPop}（${allSpecies.length}）`,
        value: allSpecies.length,
        itemStyle: {
          color: subPopColor,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          fontSize: 16,
          fontWeight: 'bold',
          color: subPopColor,
          rotate: 0
        },
        children: alphabetChildren
      };

      const option = {
        tooltip: {
          trigger: 'item',
          formatter: (params) => {
            if (!params.data || !params.data.name) {
              return '数据加载中...';
            }

            if (params.data.children && params.data.children.length > 1) {
              if (params.data.name && params.data.name.includes('(') && params.data.name.length <= 10) {
                // 首字母分组节点
                const letter = params.data.name.charAt(0);
                const hasSelectedSpecies = selectedSpeciesLetter === letter;
                const statusText = hasSelectedSpecies ? '<br/><span style="color: #dc2626;">包含选中物种</span>' : '<br/>点击展开查看物种';
                return `<strong>首字母 ${letter} 组</strong><br/>物种数量: ${params.data.value}${statusText}`;
              } else {
                // 根节点（亚群）
                const groupName = params.data.name ? params.data.name.split('（')[0] : '未知';
                const expandStatus = expandedAlphabetGroup.value ? '折叠所有分组' : '展开分组';
                return `<strong>${groupName} 亚群</strong><br/>物种数量: ${params.data.value}<br/>点击${expandStatus}`;
              }
            } else {
              // 叶子节点（物种）
              const species = allSpecies.find(s => s.accession === params.data.name);
              if (species) {
                let tooltipContent = `<strong>${species.accession}</strong><br/>`;
                tooltipContent += `亚群: ${species.info.sub_population || '未知'}<br/>`;
                if (species.info.longitude && species.info.latitude) {
                  tooltipContent += `位置: ${species.info.longitude.toFixed(2)}, ${species.info.latitude.toFixed(2)}`;
                }
                return tooltipContent;
              }
              return params.data.name || '未知';
            }
          }
        },
        series: [
          {
            type: 'tree',
            data: [treeData],
            top: '5%',
            left: '5%',
            bottom: '5%',
            right: '5%',
            symbolSize: (value, params) => {
              if (!params.data || !params.data.name) {
                return 15;
              }

              if (!params.data.children) {
                // 叶子节点（物种）
                return selectedSpecies.value === params.data.name ? 14 : 10;
              } else if (params.data.name.includes('(') && params.data.name.length <= 10) {
                // 首字母分组节点
                return Math.max(18, Math.min(30, 12 + (params.data.value || 1) * 0.3));
              } else {
                // 根节点（亚群）
                return 40;
              }
            },
            label: {
              position: 'inside',
              verticalAlign: 'middle',
              align: 'center'
            },
            leaves: {
              label: {
                position: 'bottom',
                verticalAlign: 'top',
                align: 'center',
                fontSize: 9
              }
            },
            emphasis: {
              focus: 'descendant'
            },
            expandAndCollapse: true, // 启用展开/收起功能
            animationDuration: 550,
            animationDurationUpdate: 750,
            layout: 'radial', // 改为圆形布局
            orient: 'vertical',
            roam: true,
            initialTreeDepth: 2 // 初始只展开到第二层（首字母分组）
          }
        ]
      };

      speciesTreeChart.setOption(option);

      // 添加点击事件
      speciesTreeChart.off('click');
      speciesTreeChart.on('click', (params) => {
        if (!params.data.children) {
          // 点击的是物种节点
          selectSpecies(params.data.name);
        } else if (params.data.name && params.data.name.includes('(') && params.data.name.length <= 10) {
          // 点击的是首字母分组节点
          const clickedLetter = params.data.name.charAt(0);

          if (expandedAlphabetGroup.value === clickedLetter) {
            // 如果点击的是当前展开的分组，则收起
            expandedAlphabetGroup.value = null;
          } else {
            // 否则展开这个分组（会自动收起其他分组）
            expandedAlphabetGroup.value = clickedLetter;
          }

          // 重新更新图表
          updateAlphabetGroupedTreeChart(currentSubPop, subPopColor);
        } else if (params.data.name && params.data.name.includes('（')) {
          // 点击的是中心节点（亚群根节点）
          handleCenterNodeClick();
        }
      });
    };

    // 处理中心节点点击事件
    const handleCenterNodeClick = () => {
      const selectedSpeciesLetter = selectedSpecies.value ? selectedSpecies.value.charAt(0).toUpperCase() : null;

      if (expandedAlphabetGroup.value) {
        // 如果当前有展开的分组，则折叠所有分组
        expandedAlphabetGroup.value = null;
      } else {
        // 如果当前没有展开的分组
        if (selectedSpeciesLetter) {
          // 如果有选中的物种，展开其所在的分组
          expandedAlphabetGroup.value = selectedSpeciesLetter;
        } else {
          // 如果没有选中物种，展开第一个分组（A组）
          const allSpecies = displayedSpecies.value;
          if (allSpecies.length > 0) {
            const firstLetter = allSpecies[0].accession.charAt(0).toUpperCase();
            expandedAlphabetGroup.value = firstLetter;
          }
        }
      }

      // 重新更新图表
      const currentSubPop = selectedSubPopulation.value;
      const subPopColor = getSubPopulationConfig(currentSubPop).color;
      updateAlphabetGroupedTreeChart(currentSubPop, subPopColor);
    };

    return {
      loading,
      loadingOrganisms,
      selectedOrganism,
      organismOptions,
      showLabels,
      selectedSubPopulation,
      selectedSpecies,
      subPopulations,
      currentSpeciesCount,
      totalSpeciesCount,
      displayedSpecies,
      currentDisplaySpecies,
      moduleConfig,
      availableModuleConfig,
      availableDataTypesCount,
      currentSpeciesData,
      speciesGridRef,
      selectedSpeciesRef,
      pieChartRef,
      networkChartRef,
      speciesTreeChartRef,
      expandedAlphabetGroup,
      viewMode,
      refreshData,
      exportChart,
      resetView,
      toggleLabels,
      fetchOrganisms,
      searchOrganisms,
      handleOrganismChange,
      scrollToSelectedSpecies,
      resetScrollToTop,
      saveSelectionToCache,
      selectSubPopulation,
      selectSpecies,
      goToModule,
      initPieChart,
      initNetworkChart,
      initSpeciesTreeChart,
      updatePieChart,
      updateNetworkChart,
      updateSpeciesTreeChart,
      updateAlphabetGroupedTreeChart,
      handleCenterNodeClick,
      fetchCurrentSpeciesData
    };
  }
};
</script>

<style scoped>
.data-chart-view {
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
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-toggle {
  display: flex;
  align-items: center;
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  padding: 0 16px;
  max-width: 500px;
}

.search-icon {
  color: #606266;
  margin-right: 8px;
}

.search-select {
  width: 100%;
}

.chart-container {
  display: flex;
  gap: 20px;
  height: 700px;
  align-items: flex-start;
}

.left-panel,
.center-panel,
.right-panel {
  flex: 1;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  border: 1px solid #e2e8f0;
  padding: 20px;
  display: flex;
  flex-direction: column;
}

/* 阶梯式高度递减 - 体现逐级递进关系 */
.left-panel {
  height: 700px; /* 第一级：最高 */
}

.center-panel {
  height: 650px; /* 第二级：中等高度 */
  margin-top: 50px; /* 向下偏移 */
}

.right-panel {
  height: 600px; /* 第三级：最低 */
  margin-top: 100px; /* 向下偏移最多 */
}

.panel-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  text-align: center;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 8px;
}

/* 亚群列表样式 */
.subpop-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.subpop-item {
  display: flex;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  background: #f8fafc;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
}

.subpop-item:hover {
  background: #f1f5f9;
  transform: translateX(2px);
}

.subpop-item.active {
  background: #e0f2fe;
  border-color: #0ea5e9;
  box-shadow: 0 2px 8px rgba(14, 165, 233, 0.2);
}

.subpop-color {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  margin-right: 12px;
  border: 2px solid #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.subpop-info {
  flex: 1;
}

.subpop-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 2px;
}

.subpop-count {
  font-size: 12px;
  color: #6b7280;
}

.subpop-percentage {
  font-size: 12px;
  font-weight: 600;
  color: #059669;
  background: #d1fae5;
  padding: 2px 8px;
  border-radius: 12px;
}









/* 物种网格样式 */
.species-grid {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.species-item {
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
}

.species-item:hover {
  background: #f1f5f9;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.species-item.active {
  background: #fef3c7;
  border-color: #f59e0b;
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.2);
}

.species-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
}

.species-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.species-subpop {
  font-size: 11px;
  color: #6b7280;
  background: #e5e7eb;
  padding: 1px 6px;
  border-radius: 8px;
  width: fit-content;
}

.species-location {
  font-size: 10px;
  color: #059669;
}

/* 模块网格样式 */
.modules-grid {
  flex: 1;
  padding: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: repeat(4, 1fr); /* 固定4行，每行等高 */
  gap: 8px;
  overflow-y: auto;
  min-height: 300px; /* 确保最小高度 */
}

.module-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  min-height: 60px;
}

.module-item:hover {
  background: #f1f5f9;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.module-icon {
  font-size: 20px;
  margin-right: 10px;
  flex-shrink: 0;
}

.module-info {
  flex: 1;
  min-width: 0;
}

.module-name {
  font-size: 12px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 2px;
  line-height: 1.2;
}

.module-desc {
  font-size: 10px;
  color: #6b7280;
}

.module-color {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.panel-info {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
}

.info-value {
  font-size: 13px;
  color: #1f2937;
  font-weight: 600;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .chart-container {
    flex-direction: column;
    height: auto;
    align-items: stretch;
  }

  .left-panel,
  .center-panel,
  .right-panel {
    height: 400px;
    margin-top: 0;
    margin-bottom: 20px;
  }
}

@media (max-width: 1024px) {
}

@media (max-width: 768px) {

  .search-section {
    justify-content: center;
  }

  .control-buttons {
    justify-content: center;
  }

  .left-panel,
  .center-panel,
  .right-panel {
    height: 350px;
  }

  .panel-title {
    font-size: 14px;
  }

  .info-label,
  .info-value {
    font-size: 12px;
  }

  .species-grid {
    grid-template-columns: 1fr;
  }

  .modules-grid {
    grid-template-columns: 1fr;
  }
}

/* 图表模式样式 */
.chart-panel {
  display: flex;
  flex-direction: column;
}

.chart-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 10px;
}

.pie-chart {
  width: 100%;
  height: 400px;
}

.network-chart {
  width: 100%;
  height: 400px;
}

.species-tree-chart {
  width: 100%;
  height: 400px;
}

.species-chart-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
  text-align: center;
}

.species-chart-placeholder p {
  margin: 8px 0;
  font-size: 14px;
}

.placeholder-text {
  font-size: 12px !important;
  color: #ccc !important;
}

/* 搜索框优化，减少ResizeObserver触发 */
.search-select {
  width: 100% !important;
  min-width: 300px !important;
}

.search-select .el-input {
  transition: none !important;
}

.search-select .el-input__wrapper {
  transition: none !important;
}

.search-popper {
  z-index: 9999 !important;
}
</style>

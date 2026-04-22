<template>
  <div class="home-view">
    <div class="page-header">
      <h2 class="title">{{ $t('page.home.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.home.refreshData')" placement="top">
          <el-button circle size="small" @click="fetchFiles">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>
    
    <!-- 搜索框 -->
    <div class="search-container">
      <div class="search-toolbar">
        <div class="search-wrapper">
          <el-icon class="search-icon"><Search /></el-icon>
          <el-select
            v-model="selectedOrganism"
            filterable
            remote
            :placeholder="$t('page.home.searchPlaceholder')"
            :remote-method="searchOrganisms"
            :loading="loadingOrganisms"
            clearable
            @change="handleOrganismChange"
            class="search-select"
          >
            <el-option
              v-for="item in organismOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </div>

        <div class="column-config-trigger">
          <el-popover
            :visible="showColumnSelector"
            placement="bottom-end"
            :width="260"
            trigger="manual"
            :teleported="true"
            :persistent="false"
            popper-class="column-selector-popover"
          >
            <template #reference>
              <el-button
                size="small"
                class="column-config-button"
                @click="toggleColumnSelector"
              >
                显示列
              </el-button>
            </template>

            <div class="column-selector-panel">
              <div class="column-selector-title">显示列配置</div>
              <el-checkbox-group
                v-model="visibleColumnKeys"
                @change="handleVisibleColumnsChange"
                class="column-checkbox-group"
              >
                <el-checkbox
                  v-for="column in allColumns"
                  :key="column.key"
                  :label="column.key"
                  :disabled="column.required"
                  class="column-checkbox-item"
                >
                  {{ column.label }}
                </el-checkbox>
              </el-checkbox-group>

              <div class="column-selector-actions">
                <el-button link type="primary" @click="selectAllColumns">全选</el-button>
                <el-button link type="primary" @click="resetVisibleColumns">恢复默认</el-button>
              </div>
            </div>
          </el-popover>
        </div>
      </div>
    </div>
    
    <div class="data-card">
      <div v-if="loading" class="loading">
        <el-skeleton :rows="6" animated />
      </div>
      
      <div v-else class="table-container">
        <el-table
          :data="tableData"
          border
          highlight-current-row
          height="calc(100vh - 340px)"
          style="width: 100%"
          :header-cell-style="{ background: '#f0f5ff', color: '#1a56db', fontWeight: 'bold' }"
          key="stable-table">
          
          <el-table-column
            v-if="isColumnVisible('accession')"
            prop="accession"
            label="Accession"
            width="180"
          >
            <template #default="scope">
              <div class="accession-cell">
                <router-link
                  class="data-link accession-link"
                  :to="{ name: 'accession-card', query: buildAccessionQuery(scope.row) }">
                  {{ scope.row.accession }}
                </router-link>
              </div>
            </template>
          </el-table-column>

          <el-table-column v-if="isColumnVisible('subPopulation')" prop="subPopulation" width="150">
            <template #header>
              <div class="sub-population-header">
                <span>SubPopulation</span>
                <div class="filter-container">
                  <el-popover
                    :visible="showSubPopulationFilter"
                    placement="bottom-start"
                    :width="220"
                    trigger="manual"
                    :teleported="true"
                    :persistent="false"
                    :z-index="9999"
                    popper-class="sub-population-popover">
                    <template #reference>
                      <el-button
                        size="small"
                        type="text"
                        :loading="loadingSubPopulations"
                        @click="toggleSubPopulationFilter"
                        class="filter-button">
                        <el-icon><Filter /></el-icon>
                      </el-button>
                    </template>
                    <div class="sub-population-dropdown">
                      <div class="dropdown-header">
                        <el-checkbox
                          v-model="isAllSelected"
                          @change="handleSelectAllChange"
                          class="select-all-checkbox">
                          全选
                        </el-checkbox>
                      </div>
                      <el-checkbox-group
                        v-model="selectedSubPopulations"
                        @change="handleSubPopulationSelectionChange"
                        class="checkbox-group">
                        <el-checkbox
                          v-for="subPop in allSubPopulations"
                          :key="`filter-${subPop}`"
                          :label="subPop"
                          class="checkbox-item">
                          <span :class="['sub-population', getSubPopulationClass(subPop)]">
                            {{ subPop }}
                          </span>
                        </el-checkbox>
                      </el-checkbox-group>
                    </div>
                  </el-popover>
                </div>
              </div>
            </template>
            <template #default="scope">
              <span
                v-if="scope.row.subPopulation"
                :class="['sub-population', getSubPopulationClass(scope.row.subPopulation)]">
                {{ scope.row.subPopulation }}
              </span>
              <span
                v-else
                :class="['sub-population', getSubPopulationClass('Unknown')]">
                Unknown
              </span>
            </template>
          </el-table-column>

          <el-table-column v-if="isColumnVisible('seqData')" label="SeqData" min-width="200">
            <template #default="scope">
              <a
                v-if="scope.row.seqData"
                :href="scope.row.seqData"
                target="_blank"
                class="data-link">
                seqdata.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>

          <el-table-column v-if="isColumnVisible('genome')" label="Genome" min-width="150">
            <template #default="scope">
              <div class="resource-cell">
                <router-link
                  v-if="scope.row.genome"
                  class="data-link"
                  :to="{ name: 'genome-card', query: buildGenomeQuery(scope.row) }">
                  genome.{{ scope.row.accession }}
                </router-link>
                <span v-else class="data-empty">-</span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column v-if="isColumnVisible('annotation')" label="Annotation" min-width="150">
            <template #default="scope">
              <div class="resource-cell">
                <router-link
                  v-if="scope.row.annotation"
                  class="data-link"
                  :to="{ name: 'annotation-card', query: buildAnnotationQuery(scope.row) }">
                  annotation.{{ scope.row.accession }}
                </router-link>
                <span v-else class="data-empty">-</span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column v-if="isColumnVisible('transcriptome')" label="Transcriptome" min-width="150">
            <template #default="scope">
              <router-link 
                v-if="scope.row.hasTranscriptome" 
                :to="{ name: 'transcriptome', query: { accession: scope.row.accession } }"
                class="data-link">
                Transcriptome.{{ scope.row.accession }}
              </router-link>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column v-if="isColumnVisible('codon')" label="Codon" min-width="150">
            <template #default="scope">
              <router-link
                v-if="scope.row.codon"
                :to="{ name: 'codon-card', query: { accession: scope.row.accession } }"
                class="data-link">
                codon.{{ scope.row.accession }}
              </router-link>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column v-if="isColumnVisible('centromere')" label="Centromere" min-width="150">
            <template #default="scope">
              <a 
                v-if="scope.row.centromere" 
                href="javascript:;" 
                class="data-link"
                @click="downloadFile(scope.row.centromere)">
                centromere.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column v-if="isColumnVisible('TEs')" label="TEs" min-width="150">
            <template #default="scope">
              <a
                v-if="scope.row.TEs"
                href="javascript:;"
                class="data-link"
                @click="downloadFile(scope.row.TEs)">
                TEs.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>

          <el-table-column v-if="isColumnVisible('coreBlocks')" label="CoreBlocks" min-width="150">
            <template #default="scope">
              <a
                v-if="scope.row.coreBlocks"
                href="javascript:;"
                class="data-link"
                @click="downloadFile(scope.row.coreBlocks)">
                coreblocks.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>

          <el-table-column v-if="showSnoRNAGroup" label="SnoRNA" align="center">
            <el-table-column v-if="isColumnVisible('miRNA')" label="miRNA" min-width="150">
              <template #default="scope">
                <a 
                  v-if="scope.row.miRNA" 
                  href="javascript:;" 
                  class="data-link"
                  @click="downloadFile(scope.row.miRNA)">
                  miRNA.{{ scope.row.accession }}
                </a>
                <span v-else class="data-empty">-</span>
              </template>
            </el-table-column>
            
            <el-table-column v-if="isColumnVisible('tRNA')" label="tRNA" min-width="150">
              <template #default="scope">
                <a 
                  v-if="scope.row.tRNA" 
                  href="javascript:;" 
                  class="data-link"
                  @click="downloadFile(scope.row.tRNA)">
                  tRNA.{{ scope.row.accession }}
                </a>
                <span v-else class="data-empty">-</span>
              </template>
            </el-table-column>
            
            <el-table-column v-if="isColumnVisible('rRNA')" label="rRNA" min-width="150">
              <template #default="scope">
                <a 
                  v-if="scope.row.rRNA" 
                  href="javascript:;" 
                  class="data-link"
                  @click="downloadFile(scope.row.rRNA)">
                  rRNA.{{ scope.row.accession }}
                </a>
                <span v-else class="data-empty">-</span>
              </template>
            </el-table-column>
          </el-table-column>

          <el-table-column v-if="isColumnVisible('location')" label="Location" min-width="150">
            <template #default="scope">
              <router-link
                v-if="scope.row.longitude !== null && scope.row.latitude !== null"
                :to="{ name: 'accession-map', query: { accession: scope.row.accession } }"
                class="data-link geographic-link"
                @click="handleGeographicClick(scope.row.accession)">
                <el-icon class="geographic-icon"><Location /></el-icon>
                location.{{ scope.row.accession }}
              </router-link>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 分页组件 -->
        <div class="pagination-container">
          <el-pagination
            :current-page="currentPage"
            :page-size="pageSize"
            :total="totalCount"
            layout="total, prev, pager, next, jumper"
            background
            @current-change="handleCurrentChange"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Search, Refresh, Filter, Location } from '@element-plus/icons-vue';

const HOME_VISIBLE_COLUMNS_STORAGE_KEY = 'home_table_visible_columns';
const DEFAULT_VISIBLE_COLUMN_KEYS = [
  'accession',
  'subPopulation',
  'seqData',
  'genome',
  'annotation',
  'transcriptome',
  'codon',
  'location'
];
const REQUIRED_COLUMN_KEYS = ['accession'];

export default {
  name: 'HomeView',
  components: {
    Search,
    Refresh,
    Filter,
    Location
  },
  setup() {
    useI18n();
    const loading = ref(true);
    const tableData = ref([]);
    const selectedOrganism = ref('');
    const organismOptions = ref([]);
    const loadingOrganisms = ref(false);
    const allOrganisms = ref([]);
    const currentPage = ref(1);
    const pageSize = ref(20);
    const totalCount = ref(0);

    // 亚群筛选相关
    const allSubPopulations = ref([]);
    const selectedSubPopulations = ref([]);
    const loadingSubPopulations = ref(false);
    const showSubPopulationFilter = ref(false);
    const isAllSelected = ref(true);
    const isFilteringOnly = ref(false);
    const showColumnSelector = ref(false);
    const allColumns = [
      { key: 'accession', label: 'Accession', required: true },
      { key: 'subPopulation', label: 'SubPopulation', required: false },
      { key: 'seqData', label: 'SeqData', required: false },
      { key: 'genome', label: 'Genome', required: false },
      { key: 'annotation', label: 'Annotation', required: false },
      { key: 'transcriptome', label: 'Transcriptome', required: false },
      { key: 'codon', label: 'Codon', required: false },
      { key: 'centromere', label: 'Centromere', required: false },
      { key: 'TEs', label: 'TEs', required: false },
      { key: 'coreBlocks', label: 'CoreBlocks', required: false },
      { key: 'miRNA', label: 'miRNA', required: false },
      { key: 'tRNA', label: 'tRNA', required: false },
      { key: 'rRNA', label: 'rRNA', required: false },
      { key: 'location', label: 'Location', required: false }
    ];
    const validColumnKeys = allColumns.map((column) => column.key);
    const visibleColumnKeys = ref([...DEFAULT_VISIBLE_COLUMN_KEYS]);
    const sanitizeVisibleColumns = (keys) => {
      const incomingKeys = Array.isArray(keys) ? keys : [];
      const normalizedKeys = validColumnKeys.filter((key) => {
        return incomingKeys.includes(key) || REQUIRED_COLUMN_KEYS.includes(key);
      });

      return normalizedKeys.length ? normalizedKeys : [...DEFAULT_VISIBLE_COLUMN_KEYS];
    };

    const loadVisibleColumns = () => {
      try {
        const raw = localStorage.getItem(HOME_VISIBLE_COLUMNS_STORAGE_KEY);
        if (!raw) {
          visibleColumnKeys.value = [...DEFAULT_VISIBLE_COLUMN_KEYS];
          return;
        }

        visibleColumnKeys.value = sanitizeVisibleColumns(JSON.parse(raw));
      } catch (error) {
        visibleColumnKeys.value = [...DEFAULT_VISIBLE_COLUMN_KEYS];
      }
    };

    const persistVisibleColumns = () => {
      localStorage.setItem(
        HOME_VISIBLE_COLUMNS_STORAGE_KEY,
        JSON.stringify(visibleColumnKeys.value)
      );
    };

    const isColumnVisible = (key) => visibleColumnKeys.value.includes(key);

    const showSnoRNAGroup = computed(() => {
      return ['miRNA', 'tRNA', 'rRNA'].some((key) => isColumnVisible(key));
    });
    
    // 直接使用 tableData，因为分页在后端处理
    
    // 处理页码变化
    const handleCurrentChange = (page) => {
      currentPage.value = page;
      fetchFiles(); // 重新获取当前页数据
    };
    
    // 获取所有生物体列表
    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;
        const response = await axios.get('/files/genome-files/organisms/');
        allOrganisms.value = response.data || [];
        organismOptions.value = allOrganisms.value;
      } catch (error) {
        console.error('获取生物体列表失败:', error);
        ElMessage.error('获取生物体列表失败');
      } finally {
        loadingOrganisms.value = false;
      }
    };

    // 获取所有亚群列表
    const fetchSubPopulations = async () => {
      try {
        loadingSubPopulations.value = true;
        const response = await axios.get('/files/genome-files/sub_populations/');
        // 将后端返回的"未知亚群"替换为"Unknown"
        const subPopulations = (response.data || []).map(subPop =>
          subPop === '未知亚群' ? 'Unknown' : subPop
        );
        allSubPopulations.value = subPopulations;
        // 默认全选
        selectedSubPopulations.value = [...allSubPopulations.value];
        isAllSelected.value = true;
      } catch (error) {
        console.error('获取亚群列表失败:', error);
        ElMessage.error('获取亚群列表失败');
      } finally {
        loadingSubPopulations.value = false;
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
    
    // 生物体选择变化
    const handleOrganismChange = (value) => {
      selectedOrganism.value = value;
      // 重置页码并重新获取数据
      currentPage.value = 1;
      fetchFiles();
    };
    
    // 静默获取文件列表（不显示loading，用于筛选）
    const fetchFilesQuietly = async () => {
      try {
        const params = {
          page: currentPage.value,
          page_size: pageSize.value
        };

        // 如果有搜索条件，添加到参数中
        if (selectedOrganism.value) {
          params.search = selectedOrganism.value;
        }

        // 如果有亚群筛选条件，添加到参数中
        if (selectedSubPopulations.value.length > 0 && selectedSubPopulations.value.length < allSubPopulations.value.length) {
          params.sub_populations = selectedSubPopulations.value.join(',');
        } else if (selectedSubPopulations.value.length === 0) {
          params.sub_populations = 'NONE';
        }

        const response = await axios.get('/files/genome-files/paginated_overview/', { params });
        const data = response.data;

        // 处理表格数据中的亚群信息，将"未知亚群"替换为"Unknown"
        const processedResults = (data.results || []).map(item => {
          if (item.subPopulation === '未知亚群') {
            item.subPopulation = 'Unknown';
          }
          return item;
        });

        // 只更新数据，不触发整个组件重新渲染
        tableData.value = processedResults;
        totalCount.value = data.count || 0;

      } catch (error) {
        console.error('获取文件列表失败:', error);
        ElMessage.error('获取文件列表失败');
      }
    };

    // 获取文件列表（使用分页接口，显示loading）
    const fetchFiles = async () => {
      try {
        // 只有在非筛选状态下才显示 loading
        if (!isFilteringOnly.value) {
          loading.value = true;
        }
        await fetchFilesQuietly();
      } catch (error) {
        console.error('获取文件列表失败:', error);
        ElMessage.error('获取文件列表失败');
      } finally {
        loading.value = false;
      }
    };
    

    
    // 获取亚群样式类名
    const getSubPopulationClass = (subPopulation) => {
      const classMap = {
        'cA': 'sub-pop-ca',
        'cB': 'sub-pop-cb',
        'GJ': 'sub-pop-gj',
        'XI': 'sub-pop-xi',
        'WILD': 'sub-pop-wild',
        'O.glaberrima': 'sub-pop-glaberrima',
        'Unknown': 'sub-pop-unknown'
      };
      return classMap[subPopulation] || 'sub-pop-default';
    };

    // 亚群筛选相关函数
    const toggleSubPopulationFilter = () => {
      showSubPopulationFilter.value = !showSubPopulationFilter.value;
    };

    const toggleColumnSelector = () => {
      showColumnSelector.value = !showColumnSelector.value;
    };

    const handleVisibleColumnsChange = (value) => {
      visibleColumnKeys.value = sanitizeVisibleColumns(value);
    };

    const selectAllColumns = () => {
      visibleColumnKeys.value = [...validColumnKeys];
    };

    const resetVisibleColumns = () => {
      visibleColumnKeys.value = [...DEFAULT_VISIBLE_COLUMN_KEYS];
    };

    const handleSelectAllChange = (checked) => {
      if (checked) {
        selectedSubPopulations.value = [...allSubPopulations.value];
      } else {
        selectedSubPopulations.value = [];
      }
      // 静默筛选，不影响下拉框状态
      applyFilterSilently();
    };

    const handleSubPopulationSelectionChange = () => {
      // 更新全选状态
      isAllSelected.value = selectedSubPopulations.value.length === allSubPopulations.value.length;

      // 静默筛选，不影响下拉框状态
      applyFilterSilently();
    };

    // 静默筛选函数
    const applyFilterSilently = async () => {
      isFilteringOnly.value = true;
      currentPage.value = 1;
      await fetchFilesQuietly();
      isFilteringOnly.value = false;
    };

    // 点击外部关闭弹出框
    const handleClickOutside = (event) => {
      const popover = document.querySelector('.sub-population-popover');
      const button = event.target.closest('.filter-button');
      const columnPopover = document.querySelector('.column-selector-popover');
      const columnButton = event.target.closest('.column-config-button');

      if (showSubPopulationFilter.value && !popover?.contains(event.target) && !button) {
        showSubPopulationFilter.value = false;
      }

      if (showColumnSelector.value && !columnPopover?.contains(event.target) && !columnButton) {
        showColumnSelector.value = false;
      }
    };

    // 下载文件
    const downloadFile = (file) => {
      if (!file || !file.id) return;

      const url = `/files/genome-files/${file.id}/download/`;
      window.open(axios.defaults.baseURL + url, '_blank');
    };

    const buildAccessionQuery = (row) => {
      const query = { accession: row.accession };
      if (row.default_assembly_id) {
        query.assembly = String(row.default_assembly_id);
      }
      if (row.default_annotation_id) {
        query.annotation = String(row.default_annotation_id);
      }
      return query;
    };

    const buildGenomeQuery = (row) => {
      const query = { accession: row.accession };
      if (row.default_assembly_id) {
        query.assembly = String(row.default_assembly_id);
      }
      return query;
    };

    const buildAnnotationQuery = (row) => {
      const query = buildGenomeQuery(row);
      if (row.default_annotation_id) {
        query.annotation = String(row.default_annotation_id);
      }
      return query;
    };

    watch(
      visibleColumnKeys,
      () => {
        persistVisibleColumns();
      },
      { deep: true }
    );
    
    onMounted(async () => {
      loadVisibleColumns();
      fetchOrganisms();
      await fetchSubPopulations();
      fetchFiles();
      // 添加全局点击事件监听
      document.addEventListener('click', handleClickOutside);
    });

    // 处理地理位置点击事件
    const handleGeographicClick = (accession) => {
      ElMessage.success(`正在跳转到 ${accession} 的地理分布图`);
    };

    onUnmounted(() => {
      // 清理事件监听
      document.removeEventListener('click', handleClickOutside);
    });
    
    return {
      loading,
      tableData,
      currentPage,
      pageSize,
      totalCount,
      selectedOrganism,
      organismOptions,
      loadingOrganisms,
      allSubPopulations,
      selectedSubPopulations,
      loadingSubPopulations,
      showSubPopulationFilter,
      isAllSelected,
      showColumnSelector,
      allColumns,
      visibleColumnKeys,
      showSnoRNAGroup,
      searchOrganisms,
      handleOrganismChange,
      handleCurrentChange,
      fetchFiles,
      getSubPopulationClass,
      toggleSubPopulationFilter,
      toggleColumnSelector,
      handleSelectAllChange,
      handleSubPopulationSelectionChange,
      handleVisibleColumnsChange,
      selectAllColumns,
      resetVisibleColumns,
      isColumnVisible,
      applyFilterSilently,
      fetchFilesQuietly,
      downloadFile,
      handleGeographicClick,
      buildAccessionQuery,
      buildGenomeQuery,
      buildAnnotationQuery
    };
  }
}
</script>

<style scoped>
.home-view {
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

.search-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
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

.column-config-trigger {
  display: flex;
  align-items: center;
}

.column-config-button {
  border-color: #dbe5f3;
  color: #1a56db;
}

.column-selector-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.column-selector-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.column-checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 260px;
  overflow-y: auto;
}

.column-checkbox-item {
  margin-right: 0;
}

.column-selector-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 4px;
  border-top: 1px solid #eef2f7;
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

.table-container {
  position: relative;
}

.pagination-container {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

.data-link {
  color: #409EFF;
  text-decoration: none;
  cursor: pointer;
}

.data-link:hover {
  text-decoration: underline;
}

.data-empty {
  color: #909399;
}

.resource-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}


/* 地理位置链接样式 - 与其他数据链接保持一致 */
.geographic-link {
  display: flex;
  align-items: center;
  gap: 4px;
}

.geographic-icon {
  font-size: 14px;
  color: inherit; /* 继承父元素颜色，与data-link保持一致 */
}

.accession-cell {
  display: flex;
  align-items: center;
}

.accession-link {
  font-weight: 500;
}

/* 美化表格样式 */
:deep(.el-table) {
  --el-table-border-color: #e5e7eb;
  --el-table-header-bg-color: #f0f5ff;
  --el-table-row-hover-bg-color: #f9fafb;
}

:deep(.el-table th) {
  font-weight: 600;
  padding: 12px 0;
}

:deep(.el-table td) {
  padding: 12px 0;
}

:deep(.el-pagination.is-background .el-pager li:not(.is-disabled).is-active) {
  background-color: #1a56db;
}

/* 亚群标签基础样式 */
.sub-population {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  text-align: center;
  white-space: nowrap;
  border: none !important;
}

/* 不同亚群的颜色样式 - 7种不同颜色 */
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

/* SubPopulation 列头样式 */
.sub-population-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.filter-button {
  padding: 4px !important;
  margin-left: 8px;
  color: #606266;
}

.filter-button:hover {
  color: #409EFF;
}

/* 下拉框样式 */
.sub-population-dropdown {
  max-height: 300px;
  overflow-y: auto;
}

.dropdown-header {
  padding: 12px;
  border-bottom: 1px solid #e4e7ed;
}

.select-all-checkbox {
  font-weight: 500;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  padding: 8px 12px 12px;
  max-height: 200px;
  overflow-y: auto;
}

.checkbox-item {
  margin: 4px 0;
  display: flex;
  align-items: center;
}

.checkbox-item .sub-population {
  margin-left: 8px;
}

/* 筛选容器样式 */
.filter-container {
  display: inline-block;
}

/* 全局弹出框样式 */
:deep(.sub-population-popover) {
  padding: 0 !important;
  z-index: 9999 !important;
}

:deep(.sub-population-popover .el-popover__content) {
  padding: 0 !important;
}

/* 确保弹出框在最顶层 */
:deep(.el-popper.sub-population-popover) {
  z-index: 9999 !important;
}

:deep(.column-selector-popover) {
  padding: 14px !important;
}
</style> 

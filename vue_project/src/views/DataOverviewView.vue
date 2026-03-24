<template>
  <div class="home-view">
    <div class="page-header">
      <h2 class="title">{{ $t('page.dataOverview.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.dataOverview.refreshData')" placement="top">
          <el-button circle size="small" @click="fetchFiles">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>
    
    <!-- 搜索框 -->
    <div class="search-container">
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-select
          v-model="selectedOrganism"
          filterable
          remote
          :placeholder="$t('page.dataOverview.searchPlaceholder')"
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
    </div>
    
    <div class="data-card">
      <div v-if="loading" class="loading">
        <el-skeleton :rows="6" animated />
      </div>
      
      <div v-else class="table-container">
        <el-table
          ref="tableRef"
          :data="tableData"
          border
          highlight-current-row
          height="calc(100vh - 340px)"
          style="width: 100%"
          :header-cell-style="{ background: '#f0f5ff', color: '#1a56db', fontWeight: 'bold' }"
          table-layout="fixed"
          key="stable-table">
          
          <el-table-column prop="accession" :label="$t('page.dataOverview.accession')" width="180">
            <template #default="scope">
              <div class="accession-cell">
                <router-link
                  :to="{ path: '/accession-card', query: { organism: scope.row.accession } }"
                  class="accession-link">
                  {{ scope.row.accession }}
                </router-link>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="subPopulation" width="150">
            <template #header>
              <div class="sub-population-header">
                <span>{{ $t('page.dataOverview.subPopulation') }}</span>
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
                          {{ $t('page.dataOverview.selectAll') }}
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

          <el-table-column :label="$t('page.dataOverview.seqData')" min-width="200">
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

          <el-table-column label="Genome" min-width="150">
            <template #default="scope">
              <router-link
                v-if="scope.row.genome"
                :to="{ path: '/genome-card', query: { organism: scope.row.accession } }"
                class="data-link">
                genome.{{ scope.row.accession }}
              </router-link>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column :label="$t('page.dataOverview.annotation')" min-width="150">
            <template #default="scope">
              <a 
                v-if="scope.row.annotation" 
                href="https://www.baidu.com" 
                target="_blank"
                class="data-link">
                annotation.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="Transcriptome" min-width="150">
            <template #default="scope">
              <router-link 
                v-if="scope.row.hasTranscriptome" 
                :to="{ path: '/transcriptome-overview', query: { organism: scope.row.accession } }"
                class="data-link">
                Transcriptome.{{ scope.row.accession }}
              </router-link>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column :label="$t('page.dataOverview.codon')" min-width="150">
            <template #default="scope">
              <router-link
                v-if="scope.row.codon"
                :to="{ path: '/codon-card', query: { organism: scope.row.accession } }"
                class="data-link">
                codon.{{ scope.row.accession }}
              </router-link>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="Centromere" min-width="150">
            <template #default="scope">
              <a 
                v-if="scope.row.centromere" 
                href="https://www.baidu.com" 
                target="_blank"
                class="data-link">
                centromere.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="TEs" min-width="150">
            <template #default="scope">
              <a
                v-if="scope.row.TEs"
                href="https://www.baidu.com"
                target="_blank"
                class="data-link">
                TEs.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>

          <el-table-column label="CoreBlocks" min-width="150">
            <template #default="scope">
              <a
                v-if="scope.row.coreBlocks"
                href="https://www.baidu.com"
                target="_blank"
                class="data-link">
                coreblocks.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>

          <el-table-column label="SnoRNA" align="center">
            <el-table-column label="miRNA" min-width="150">
              <template #default="scope">
                <a 
                  v-if="scope.row.miRNA" 
                  href="https://www.baidu.com" 
                  target="_blank"
                  class="data-link">
                  miRNA.{{ scope.row.accession }}
                </a>
                <span v-else class="data-empty">-</span>
              </template>
            </el-table-column>
            
            <el-table-column label="tRNA" min-width="150">
              <template #default="scope">
                <a 
                  v-if="scope.row.tRNA" 
                  href="https://www.baidu.com" 
                  target="_blank"
                  class="data-link">
                  tRNA.{{ scope.row.accession }}
                </a>
                <span v-else class="data-empty">-</span>
              </template>
            </el-table-column>
            
            <el-table-column label="rRNA" min-width="150">
              <template #default="scope">
                <a 
                  v-if="scope.row.rRNA" 
                  href="https://www.baidu.com" 
                  target="_blank"
                  class="data-link">
                  rRNA.{{ scope.row.accession }}
                </a>
                <span v-else class="data-empty">-</span>
              </template>
            </el-table-column>
          </el-table-column>

          <el-table-column :label="$t('page.dataOverview.location')" min-width="150">
            <template #default="scope">
              <router-link
                v-if="scope.row.longitude !== null && scope.row.latitude !== null"
                :to="{ path: '/accession-map', query: { organism: scope.row.accession } }"
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
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { useI18n } from 'vue-i18n';
import { Search, Refresh, Filter, Loading, Location } from '@element-plus/icons-vue';

export default {
  name: 'DataOverviewView',
  components: {
    Search,
    Refresh,
    Filter,
    Loading,
    Location
  },
  setup() {
    const { t } = useI18n();
    const loading = ref(true);
    const tableData = ref([]);
    const selectedOrganism = ref('');
    const organismOptions = ref([]);
    const loadingOrganisms = ref(false);
    const allOrganisms = ref([]);
    const currentPage = ref(1);
    const pageSize = ref(20);
    const totalCount = ref(0);
    const dataVersion = ref(0);

    // 亚群筛选相关
    const allSubPopulations = ref([]);
    const selectedSubPopulations = ref([]);
    const loadingSubPopulations = ref(false);
    const showSubPopulationFilter = ref(false);
    const isAllSelected = ref(true);
    const tableRef = ref(null);
    const isFilteringOnly = ref(false);
    
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
        ElMessage.error(t('messages.getOrganismsFailed'));
      } finally {
        loadingOrganisms.value = false;
      }
    };

    // 获取所有亚群列表
    const fetchSubPopulations = async () => {
      try {
        loadingSubPopulations.value = true;
        const response = await axios.get('/files/genome-files/sub_populations/');
        allSubPopulations.value = response.data || [];
        // 默认全选
        selectedSubPopulations.value = [...allSubPopulations.value];
        isAllSelected.value = true;
      } catch (error) {
        console.error('获取亚群列表失败:', error);
        ElMessage.error(t('messages.getSubPopulationsFailed'));
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

    // 立即执行筛选的函数
    const applyFilter = () => {
      currentPage.value = 1;
      fetchFiles();
    };

    // 亚群筛选相关函数
    const toggleSubPopulationFilter = () => {
      showSubPopulationFilter.value = !showSubPopulationFilter.value;
    };

    const handleSelectAllChange = (checked) => {
      if (checked) {
        selectedSubPopulations.value = [...allSubPopulations.value];
      } else {
        selectedSubPopulations.value = [];
      }
      // 静默筛选，不重新渲染整个组件
      applyFilterSilently();
    };

    const handleSubPopulationSelectionChange = () => {
      // 更新全选状态
      isAllSelected.value = selectedSubPopulations.value.length === allSubPopulations.value.length;

      // 静默筛选，不重新渲染整个组件
      applyFilterSilently();
    };

    // 静默筛选函数
    const applyFilterSilently = async () => {
      isFilteringOnly.value = true;
      currentPage.value = 1;

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

        // 直接更新数据，不触发整个组件重新渲染
        tableData.value = data.results || [];
        totalCount.value = data.count || 0;

      } catch (error) {
        console.error('获取文件列表失败:', error);
        ElMessage.error(t('messages.getFileListFailed'));
      } finally {
        isFilteringOnly.value = false;
      }
    };
    
    // 获取文件列表（使用分页接口）
    const fetchFiles = async () => {
      try {
        // 只有在非筛选状态下才显示 loading
        if (!isFilteringOnly.value) {
          loading.value = true;
        }

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
          // 如果没有选择任何亚群，发送空筛选参数，后端应返回空结果
          params.sub_populations = 'NONE';
        }

        const response = await axios.get('/files/genome-files/paginated_overview/', { params });
        const data = response.data;

        tableData.value = data.results || [];
        totalCount.value = data.count || 0;

      } catch (error) {
        console.error('获取文件列表失败:', error);
        ElMessage.error(t('messages.getFileListFailed'));
      } finally {
        loading.value = false;
      }
    };
    

    
    // 点击外部关闭弹出框
    const handleClickOutside = (event) => {
      const popover = document.querySelector('.sub-population-popover');
      const button = event.target.closest('.filter-button');

      if (showSubPopulationFilter.value && !popover?.contains(event.target) && !button) {
        showSubPopulationFilter.value = false;
      }
    };

    onMounted(async () => {
      fetchOrganisms();
      await fetchSubPopulations();
      fetchFiles();

      // 添加全局点击事件监听
      document.addEventListener('click', handleClickOutside);
    });

    // 处理地理位置点击事件
    const handleGeographicClick = (accession) => {
      ElMessage.success(t('messages.jumpingToGeographicMap', { accession }));
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
      dataVersion,
      selectedOrganism,
      organismOptions,
      loadingOrganisms,
      allSubPopulations,
      selectedSubPopulations,
      loadingSubPopulations,
      showSubPopulationFilter,
      isAllSelected,
      isFilteringOnly,
      tableRef,
      searchOrganisms,
      handleOrganismChange,
      handleCurrentChange,
      fetchFiles,
      getSubPopulationClass,
      toggleSubPopulationFilter,
      handleSelectAllChange,
      handleSubPopulationSelectionChange,
      applyFilter,
      applyFilterSilently,
      handleGeographicClick
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

.data-text {
  color: #303133;
  font-weight: 500;
}

/* 亚群标签基础样式 */
.sub-population {
  display: inline-block !important;
  padding: 3px 10px !important;
  border-radius: 12px !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  text-align: center !important;
  white-space: nowrap !important;
  border: none !important;
  min-width: auto !important;
  width: auto !important;
  height: auto !important;
  line-height: normal !important;
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

.sub-population-filter {
  margin-left: 8px;
}

.filter-button {
  padding: 2px 4px !important;
  min-height: auto !important;
  color: #606266;
}

.filter-button:hover {
  color: #409EFF;
}

/* 弹出框样式 */
.sub-population-dropdown {
  padding: 0;
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

.accession-cell {
  display: flex;
  align-items: center;
}

.accession-link {
  color: #1a56db;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
}

.accession-link:hover {
  color: #0d47a1;
  text-decoration: underline;
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
</style> 
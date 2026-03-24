<template>
  <div class="transcriptome-view">
    <div class="page-header">
      <h2 class="title">{{ $t('page.transcriptomeOverview.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.transcriptomeOverview.refreshData')" placement="top">
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
          v-model="searchOrganism"
          filterable
          remote
          :placeholder="$t('page.transcriptomeOverview.searchPlaceholder')"
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
          :data="tableData"
          border
          highlight-current-row
          height="calc(100vh - 340px)"
          style="width: 100%"
          :header-cell-style="{ background: '#f0f5ff', color: '#1a56db', fontWeight: 'bold' }">
          
          <el-table-column prop="accession" label="Accession" width="180">
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



          <el-table-column label="all" min-width="150">
            <template #default="scope">
              <a 
                v-if="hasTranscriptomeType(scope.row.accession, 'all')" 
                href="https://www.baidu.com" 
                target="_blank"
                class="data-link">
                Transcriptome.all.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="leaf" min-width="150">
            <template #default="scope">
              <a 
                v-if="hasTranscriptomeType(scope.row.accession, 'leaf')" 
                href="https://www.baidu.com" 
                target="_blank"
                class="data-link">
                Transcriptome.leaf.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="panicles" min-width="150">
            <template #default="scope">
              <a 
                v-if="hasTranscriptomeType(scope.row.accession, 'panicles')" 
                href="https://www.baidu.com" 
                target="_blank"
                class="data-link">
                Transcriptome.panicles.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="shoot" min-width="150">
            <template #default="scope">
              <a 
                v-if="hasTranscriptomeType(scope.row.accession, 'shoot')" 
                href="https://www.baidu.com" 
                target="_blank"
                class="data-link">
                Transcriptome.shoot.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="stem" min-width="150">
            <template #default="scope">
              <a 
                v-if="hasTranscriptomeType(scope.row.accession, 'stem')" 
                href="https://www.baidu.com" 
                target="_blank"
                class="data-link">
                Transcriptome.stem.{{ scope.row.accession }}
              </a>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
          
          <el-table-column label="root" min-width="150">
            <template #default="scope">
              <a 
                v-if="hasTranscriptomeType(scope.row.accession, 'root')" 
                href="https://www.baidu.com" 
                target="_blank"
                class="data-link">
                Transcriptome.root.{{ scope.row.accession }}
              </a>
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
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Search, Refresh, Filter } from '@element-plus/icons-vue';

export default {
  name: 'TranscriptomeOverviewView',
  components: {
    Search,
    Refresh,
    Filter
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { t } = useI18n();
    const loading = ref(true);
    const tableData = ref([]);
    const organismOptions = ref([]);
    const loadingOrganisms = ref(false);
    const allOrganisms = ref([]);
    const searchOrganism = ref('');
    const currentPage = ref(1);
    const pageSize = ref(20);
    const totalCount = ref(0);
    const isFilteringOnly = ref(false);
    
    // 从URL查询参数中获取organism
    const selectedOrganism = computed(() => route.query.organism || null);
    
    // 处理页码变化
    const handleCurrentChange = (page) => {
      currentPage.value = page;
      fetchFiles(); // 重新获取当前页数据
    };
    
    // 获取有转录组数据的生物体列表
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
      searchOrganism.value = value;
      // 重置页码并重新获取数据
      currentPage.value = 1;
      fetchFiles();
    };
    
    // 静默获取文件列表（不显示loading，用于筛选）
    const fetchFilesQuietly = async () => {
      try {
        isFilteringOnly.value = true;
        const params = {
          page: currentPage.value,
          page_size: pageSize.value
        };

        // 如果有搜索条件，添加到参数中
        if (searchOrganism.value) {
          params.search = searchOrganism.value;
        }

        const response = await axios.get('/files/genome-files/paginated_transcriptome_overview/', { params });
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
        if (searchOrganism.value) {
          params.search = searchOrganism.value;
        }

        const response = await axios.get('/files/genome-files/paginated_transcriptome_overview/', { params });
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
    
    // 检查特定生物体是否有特定类型的转录组
    const hasTranscriptomeType = (organism, type) => {
      const organismData = tableData.value.find(item => item.accession === organism);
      return organismData && organismData.transcriptomeTypes.includes(type);
    };


    
    // 清除筛选
    const clearFilter = () => {
      searchOrganism.value = '';
      currentPage.value = 1;
      fetchFiles();
    };

    // 当selectedOrganism改变时更新searchOrganism
    watch(selectedOrganism, (newVal) => {
      if (newVal) {
        searchOrganism.value = newVal;
        currentPage.value = 1;
        fetchFiles();
      }
    }, { immediate: true });

    onMounted(async () => {
      // 先获取生物体列表
      await fetchOrganisms();
      // 然后获取数据
      fetchFiles();
    });
    
    return {
      loading,
      tableData,
      currentPage,
      pageSize,
      totalCount,
      selectedOrganism,
      searchOrganism,
      organismOptions,
      loadingOrganisms,
      searchOrganisms,
      handleOrganismChange,
      handleCurrentChange,
      fetchFiles,
      hasTranscriptomeType,
      clearFilter
    };
  }
}
</script>

<style scoped>
.transcriptome-view {
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

.accession-cell {
  display: flex;
  align-items: center;
}

.accession-text {
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

/* 亚群样式 */
.sub-population {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  text-align: center;
  min-width: 60px;
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
</style> 
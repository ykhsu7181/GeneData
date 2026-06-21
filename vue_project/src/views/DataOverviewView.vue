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
    
    <!-- 鎼滅储妗?-->
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
                  :to="{ path: '/accession-card', query: buildAccessionQuery(scope.row) }"
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
              <div class="resource-cell">
                <router-link
                  v-if="scope.row.genome"
                  :to="{ path: '/genome-card', query: buildGenomeQuery(scope.row) }"
                  class="data-link">
                  genome.{{ scope.row.accession }}
                </router-link>
                <span v-else class="data-empty">-</span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column :label="$t('page.dataOverview.annotation')" min-width="150">
            <template #default="scope">
              <div class="resource-cell">
                <router-link
                  v-if="scope.row.annotation"
                  :to="{ path: '/annotation-card', query: buildAnnotationQuery(scope.row) }"
                  class="data-link">
                  annotation.{{ scope.row.accession }}
                </router-link>
                <span v-else class="data-empty">-</span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column label="Transcriptome" min-width="150">
            <template #default="scope">
              <router-link 
                v-if="scope.row.hasTranscriptome" 
                :to="{ path: '/transcriptome-overview', query: { accession: scope.row.accession } }"
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
                :to="{ path: '/codon-card', query: { accession: scope.row.accession } }"
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
                :to="{ path: '/accession-map', query: { accession: scope.row.accession } }"
                class="data-link geographic-link"
                @click="handleGeographicClick(scope.row.accession)">
                <el-icon class="geographic-icon"><Location /></el-icon>
                location.{{ scope.row.accession }}
              </router-link>
              <span v-else class="data-empty">-</span>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 鍒嗛〉缁勪欢 -->
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
import { ref, onMounted, onUnmounted, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import { Search, Refresh, Filter, Location } from '@element-plus/icons-vue';

export default {
  name: 'DataOverviewView',
  components: {
    Search,
    Refresh,
    Filter,
    Location
  },
  setup() {
    const { t } = useI18n();
    const route = useRoute();
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

    // 浜氱兢绛涢€夌浉鍏?
    const allSubPopulations = ref([]);
    const selectedSubPopulations = ref([]);
    const loadingSubPopulations = ref(false);
    const showSubPopulationFilter = ref(false);
    const isAllSelected = ref(true);
    const tableRef = ref(null);
    const isFilteringOnly = ref(false);

    const syncRouteFilters = () => {
      const search = typeof route.query.search === 'string' ? route.query.search : '';
      selectedOrganism.value = search;

      const subPopulationQuery = route.query.sub_population || route.query.sub_populations;
      if (typeof subPopulationQuery === 'string' && subPopulationQuery.trim()) {
        const requested = subPopulationQuery
          .split(',')
          .map(item => item.trim())
          .filter(Boolean);
        selectedSubPopulations.value = requested;
        isAllSelected.value = requested.length === allSubPopulations.value.length;
      } else if (allSubPopulations.value.length) {
        selectedSubPopulations.value = [...allSubPopulations.value];
        isAllSelected.value = true;
      }
    };
    
    // 鐩存帴浣跨敤 tableData锛屽洜涓哄垎椤靛湪鍚庣澶勭悊
    
    // 澶勭悊椤电爜鍙樺寲
    const handleCurrentChange = (page) => {
      currentPage.value = page;
      fetchFiles(); // 閲嶆柊鑾峰彇褰撳墠椤垫暟鎹?
    };
    
    // 鑾峰彇鎵€鏈夌敓鐗╀綋鍒楄〃
    const fetchOrganisms = async () => {
      try {
        loadingOrganisms.value = true;
        const response = await axios.get('/files/query/organisms/');
        allOrganisms.value = response.data || [];
        organismOptions.value = allOrganisms.value;
      } catch (error) {
        console.error('鑾峰彇鐢熺墿浣撳垪琛ㄥけ璐?', error);
        ElMessage.error(t('messages.getOrganismsFailed'));
      } finally {
        loadingOrganisms.value = false;
      }
    };

    // 鑾峰彇鎵€鏈変簹缇ゅ垪琛?
    const fetchSubPopulations = async () => {
      try {
        loadingSubPopulations.value = true;
        const response = await axios.get('/files/query/sub-populations/');
        allSubPopulations.value = response.data || [];
        // 榛樿鍏ㄩ€?
        selectedSubPopulations.value = [...allSubPopulations.value];
        isAllSelected.value = true;
      } catch (error) {
        console.error('鑾峰彇浜氱兢鍒楄〃澶辫触:', error);
        ElMessage.error(t('messages.getSubPopulationsFailed'));
      } finally {
        loadingSubPopulations.value = false;
      }
    };
    
    // 鎼滅储鐢熺墿浣?
    const searchOrganisms = (query) => {
      if (query) {
        organismOptions.value = allOrganisms.value.filter(item => 
          item.toLowerCase().includes(query.toLowerCase())
        );
      } else {
        organismOptions.value = allOrganisms.value;
      }
    };
    
    // 鐢熺墿浣撻€夋嫨鍙樺寲
    const handleOrganismChange = (value) => {
      selectedOrganism.value = value;
      // 閲嶇疆椤电爜骞堕噸鏂拌幏鍙栨暟鎹?
      currentPage.value = 1;
      fetchFiles();
    };

    // 鑾峰彇浜氱兢鏍峰紡绫诲悕
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

    // 绔嬪嵆鎵ц绛涢€夌殑鍑芥暟
    const applyFilter = () => {
      currentPage.value = 1;
      fetchFiles();
    };

    // 浜氱兢绛涢€夌浉鍏冲嚱鏁?
    const toggleSubPopulationFilter = () => {
      showSubPopulationFilter.value = !showSubPopulationFilter.value;
    };

    const handleSelectAllChange = (checked) => {
      if (checked) {
        selectedSubPopulations.value = [...allSubPopulations.value];
      } else {
        selectedSubPopulations.value = [];
      }
      // 闈欓粯绛涢€夛紝涓嶉噸鏂版覆鏌撴暣涓粍浠?
      applyFilterSilently();
    };

    const handleSubPopulationSelectionChange = () => {
      // 鏇存柊鍏ㄩ€夌姸鎬?
      isAllSelected.value = selectedSubPopulations.value.length === allSubPopulations.value.length;

      // 闈欓粯绛涢€夛紝涓嶉噸鏂版覆鏌撴暣涓粍浠?
      applyFilterSilently();
    };

    // 闈欓粯绛涢€夊嚱鏁?
    const applyFilterSilently = async () => {
      isFilteringOnly.value = true;
      currentPage.value = 1;

      try {
        const params = {
          page: currentPage.value,
          page_size: pageSize.value
        };

        // 濡傛灉鏈夋悳绱㈡潯浠讹紝娣诲姞鍒板弬鏁颁腑
        if (selectedOrganism.value) {
          params.search = selectedOrganism.value;
        }

        // 濡傛灉鏈変簹缇ょ瓫閫夋潯浠讹紝娣诲姞鍒板弬鏁颁腑
        if (selectedSubPopulations.value.length > 0 && selectedSubPopulations.value.length < allSubPopulations.value.length) {
          params.sub_populations = selectedSubPopulations.value.join(',');
        } else if (selectedSubPopulations.value.length === 0) {
          params.sub_populations = 'NONE';
        }

        const response = await axios.get('/files/query/paginated-overview/', { params });
        const data = response.data;

        // 鐩存帴鏇存柊鏁版嵁锛屼笉瑙﹀彂鏁翠釜缁勪欢閲嶆柊娓叉煋
        tableData.value = data.results || [];
        totalCount.value = data.count || 0;

      } catch (error) {
        console.error('鑾峰彇鏂囦欢鍒楄〃澶辫触:', error);
        ElMessage.error(t('messages.getFileListFailed'));
      } finally {
        isFilteringOnly.value = false;
      }
    };
    
    // 鑾峰彇鏂囦欢鍒楄〃锛堜娇鐢ㄥ垎椤垫帴鍙ｏ級
    const fetchFiles = async () => {
      try {
        // 鍙湁鍦ㄩ潪绛涢€夌姸鎬佷笅鎵嶆樉绀?loading
        if (!isFilteringOnly.value) {
          loading.value = true;
        }

        const params = {
          page: currentPage.value,
          page_size: pageSize.value
        };

        // 濡傛灉鏈夋悳绱㈡潯浠讹紝娣诲姞鍒板弬鏁颁腑
        if (selectedOrganism.value) {
          params.search = selectedOrganism.value;
        }

        // 濡傛灉鏈変簹缇ょ瓫閫夋潯浠讹紝娣诲姞鍒板弬鏁颁腑
        if (selectedSubPopulations.value.length > 0 && selectedSubPopulations.value.length < allSubPopulations.value.length) {
          params.sub_populations = selectedSubPopulations.value.join(',');
        } else if (selectedSubPopulations.value.length === 0) {
          // 濡傛灉娌℃湁閫夋嫨浠讳綍浜氱兢锛屽彂閫佺┖绛涢€夊弬鏁帮紝鍚庣搴旇繑鍥炵┖缁撴灉
          params.sub_populations = 'NONE';
        }

        const response = await axios.get('/files/query/paginated-overview/', { params });
        const data = response.data;

        tableData.value = data.results || [];
        totalCount.value = data.count || 0;

      } catch (error) {
        console.error('鑾峰彇鏂囦欢鍒楄〃澶辫触:', error);
        ElMessage.error(t('messages.getFileListFailed'));
      } finally {
        loading.value = false;
      }
    };
    

    
    // 鐐瑰嚮澶栭儴鍏抽棴寮瑰嚭妗?
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
      syncRouteFilters();
      fetchFiles();

      // 娣诲姞鍏ㄥ眬鐐瑰嚮浜嬩欢鐩戝惉
      document.addEventListener('click', handleClickOutside);
    });

    watch(
      () => route.query,
      () => {
        syncRouteFilters();
        currentPage.value = 1;
        fetchFiles();
      }
    );

    // 澶勭悊鍦扮悊浣嶇疆鐐瑰嚮浜嬩欢
    const handleGeographicClick = (accession) => {
      ElMessage.success(t('messages.jumpingToGeographicMap', { accession }));
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

    onUnmounted(() => {
      // 娓呯悊浜嬩欢鐩戝惉
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

/* 浜氱兢鏍囩鍩虹鏍峰紡 */
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

/* 涓嶅悓浜氱兢鐨勯鑹叉牱寮?- 7绉嶄笉鍚岄鑹?*/
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

/* SubPopulation 鍒楀ご鏍峰紡 */
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

/* 寮瑰嚭妗嗘牱寮?*/
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

/* 绛涢€夊鍣ㄦ牱寮?*/
.filter-container {
  display: inline-block;
}

.accession-cell {
  display: flex;
  align-items: center;
}

.resource-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
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


/* 鍦扮悊浣嶇疆閾炬帴鏍峰紡 - 涓庡叾浠栨暟鎹摼鎺ヤ繚鎸佷竴鑷?*/
.geographic-link {
  display: flex;
  align-items: center;
  gap: 4px;
}

.geographic-icon {
  font-size: 14px;
  color: inherit; /* 缁ф壙鐖跺厓绱犻鑹诧紝涓巇ata-link淇濇寔涓€鑷?*/
}



/* 缇庡寲琛ㄦ牸鏍峰紡 */
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

/* 鍏ㄥ眬寮瑰嚭妗嗘牱寮?*/
:deep(.sub-population-popover) {
  padding: 0 !important;
  z-index: 9999 !important;
}

:deep(.sub-population-popover .el-popover__content) {
  padding: 0 !important;
}

/* 纭繚寮瑰嚭妗嗗湪鏈€椤跺眰 */
:deep(.el-popper.sub-population-popover) {
  z-index: 9999 !important;
}
</style> 


<template>
  <div class="core-variable-blocks-view">
    <!-- 复用数据一览表的标题样式 -->
    <div class="page-header">
      <h2 class="title">{{ $t('page.coreVariableBlocks.title') }}</h2>
      <div class="header-actions">
        <el-tooltip :content="$t('page.coreVariableBlocks.refreshData')" placement="top">
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
        <el-select
          v-model="selectedOrganism"
          filterable
          remote
          :placeholder="$t('page.coreVariableBlocks.searchPlaceholder')"
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

    <!-- 内容区域 -->
    <div class="data-card">
      <div v-if="loading" class="loading">
        <el-skeleton :rows="6" animated />
      </div>
      
      <div v-else-if="!selectedOrganism" class="empty-state">
        <el-empty :description="$t('page.coreVariableBlocks.selectOrganismPrompt')" />
      </div>
      
      <div v-else class="content-container">
        <div class="blocks-info">
          <h3>{{ selectedOrganism }} 核心和可变区块分析</h3>
          <p>这里将显示选中生物体的核心和可变区块数据...</p>

          <!-- 数据统计信息 -->
          <div class="data-stats">
            <p><strong>数据统计：</strong>共找到 {{ totalCount }} 条相关记录</p>
          </div>
          
          <!-- 可以添加具体的区块分析内容 -->
          <div class="analysis-sections">
            <div class="section">
              <h4>🧬 核心区块 (Core Blocks)</h4>
              <p>显示在所有或大多数基因组中保守的区域</p>
            </div>
            
            <div class="section">
              <h4>🔄 可变区块 (Variable Blocks)</h4>
              <p>显示在不同基因组间存在差异的区域</p>
            </div>
            
            <div class="section">
              <h4>📊 统计分析</h4>
              <p>核心区块和可变区块的统计信息和比较分析</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage } from 'element-plus';
import { Refresh, Search } from '@element-plus/icons-vue';
import axios from 'axios';

export default {
  name: 'CoreVariableBlocks',
  components: {
    Refresh,
    Search
  },
  setup() {
    const route = useRoute();
    const { t } = useI18n();
    const loading = ref(true);
    const loadingOrganisms = ref(false);
    const selectedOrganism = ref('');
    const allOrganisms = ref([]);
    const organismOptions = ref([]);
    const tableData = ref([]);
    const currentPage = ref(1);
    const pageSize = ref(20);
    const totalCount = ref(0);

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

    // 获取文件列表（使用分页接口）
    const fetchFiles = async () => {
      try {
        loading.value = true;

        const params = {
          page: currentPage.value,
          page_size: pageSize.value
        };

        // 如果有搜索条件，添加到参数中
        if (selectedOrganism.value) {
          params.search = selectedOrganism.value;
        }

        const response = await axios.get('/files/genome-files/paginated_overview/', { params });
        const data = response.data;

        tableData.value = data.results || [];
        totalCount.value = data.count || 0;

      } catch (error) {
        console.error('获取文件列表失败:', error);
        ElMessage.error('获取文件列表失败');
      } finally {
        loading.value = false;
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

    // 处理URL参数
    const handleRouteParams = () => {
      const organism = route.query.organism;
      if (organism && allOrganisms.value.includes(organism)) {
        selectedOrganism.value = organism;
        handleOrganismChange(organism);
      }
    };

    // 监听路由变化
    watch(() => route.query.organism, (newOrganism) => {
      if (newOrganism && allOrganisms.value.includes(newOrganism)) {
        selectedOrganism.value = newOrganism;
        handleOrganismChange(newOrganism);
      }
    });

    // 监听生物体列表加载完成，然后处理URL参数
    watch(allOrganisms, (newOrganisms) => {
      if (newOrganisms.length > 0) {
        handleRouteParams();
      }
    });

    onMounted(async () => {
      await fetchOrganisms();
      fetchFiles();
    });

    return {
      loading,
      loadingOrganisms,
      selectedOrganism,
      organismOptions,
      tableData,
      currentPage,
      pageSize,
      totalCount,
      fetchFiles,
      fetchOrganisms,
      searchOrganisms,
      handleOrganismChange,
      handleRouteParams
    };
  }
};
</script>

<style scoped>
.core-variable-blocks-view {
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

.empty-state {
  padding: 40px 20px;
  text-align: center;
}

.content-container {
  padding: 20px 0;
}

.blocks-info h3 {
  color: #1a56db;
  margin-bottom: 16px;
}

.blocks-info p {
  color: #606266;
  line-height: 1.6;
  margin-bottom: 24px;
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

.analysis-sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 24px;
}

.section {
  background: #f8fafc;
  border-radius: 8px;
  padding: 20px;
  border-left: 4px solid #1a56db;
}

.section h4 {
  color: #1a56db;
  margin-bottom: 12px;
  font-size: 16px;
}

.section p {
  color: #606266;
  font-size: 14px;
  line-height: 1.5;
  margin: 0;
}
</style>

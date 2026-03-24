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
    
    <!-- 搜索框 -->
    <div class="search-container">
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-select
          v-model="selectedOrganism"
          filterable
          remote
          :placeholder="$t('page.accessionCard.searchPlaceholder')"
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
      
      <div v-else class="content-container">
        <!-- AccessionCard内容部分 - 暂未实现 -->
        <div class="placeholder-content">
          <h3>{{ $t('page.accessionCard.developing') }}</h3>
          <p>{{ $t('page.accessionCard.comingSoon') }}</p>
          <p v-if="selectedOrganism">{{ $t('page.accessionCard.currentOrganism') }}: {{ selectedOrganism }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Search, Refresh } from '@element-plus/icons-vue';
import { useRoute } from 'vue-router';

export default {
  name: 'AccessionCard',
  components: {
    Search,
    Refresh
  },
  setup() {
    const route = useRoute();
    const loading = ref(false);
    const selectedOrganism = ref('');
    const organismOptions = ref([]);
    const loadingOrganisms = ref(false);
    
    // 获取生物体列表（按需加载，不预加载全部数据）
    const fetchOrganisms = async (query = '') => {
      try {
        loadingOrganisms.value = true;
        // 只在有搜索条件时才请求数据
        if (query) {
          const response = await axios.get(`/files/genome-files/organisms/?search=${encodeURIComponent(query)}`);
          organismOptions.value = response.data || [];
        } else {
          organismOptions.value = [];
        }
      } catch (error) {
        console.error('获取生物体列表失败:', error);
        ElMessage.error('获取生物体列表失败');
      } finally {
        loadingOrganisms.value = false;
      }
    };
    
    // 搜索生物体（远程搜索）
    const searchOrganisms = (query) => {
      if (query && query.length >= 2) {
        fetchOrganisms(query);
      } else {
        organismOptions.value = [];
      }
    };
    
    // 生物体选择变化
    const handleOrganismChange = async (value) => {
      selectedOrganism.value = value;
      if (value) {
        console.log(`选择的生物体: ${value}`);
        // TODO: 这里将来会加载生物体详细信息
      }
    };
    
    // 刷新页面（不预加载数据）
    const refreshPage = () => {
      // 清空当前选择和搜索结果
      selectedOrganism.value = '';
      organismOptions.value = [];
      loading.value = false;
    };

    // 处理URL参数
    const handleRouteParams = () => {
      const organism = route.query.organism;
      if (organism) {
        selectedOrganism.value = organism;
        handleOrganismChange(organism);
      }
    };

    // 监听路由变化
    watch(() => route.query.organism, (newOrganism) => {
      if (newOrganism) {
        selectedOrganism.value = newOrganism;
        handleOrganismChange(newOrganism);
      }
    });
    
    onMounted(() => {
      // 处理URL参数，但不预加载全部数据
      handleRouteParams();
      loading.value = false;
    });
    
    return {
      loading,
      selectedOrganism,
      organismOptions,
      loadingOrganisms,
      searchOrganisms,
      handleOrganismChange,
      refreshPage,
      handleRouteParams
    };
  }
}
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
  max-width: 400px;
}

.search-icon {
  color: #606266;
  margin-right: 8px;
  flex-shrink: 0;
}

.search-select {
  flex-grow: 1;
  min-width: 200px;
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

.content-container {
  position: relative;
}

.placeholder-content {
  padding: 40px;
  text-align: center;
  color: #909399;
}

.placeholder-content h3 {
  font-size: 20px;
  margin-bottom: 16px;
  color: #1a56db;
}

.placeholder-content p {
  margin-bottom: 8px;
  font-size: 14px;
}
</style>

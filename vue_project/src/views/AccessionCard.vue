<template>
  <div class="accession-search-page">
    <div class="page-heading">
      <div>
        <div class="page-kicker">ACCESSION</div>
        <h1>{{ $t('page.accessionCard.title') }}</h1>
      </div>
      <el-tooltip :content="$t('common.refresh')" placement="top">
        <el-button circle class="refresh-button" :loading="loadingOrganisms" @click="refreshOptions">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <div class="search-container">
      <div class="search-wrapper">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-select
          v-model="selectedAccession"
          filterable
          remote
          clearable
          class="search-select"
          :placeholder="$t('page.accessionCard.searchPlaceholder')"
          :remote-method="searchOrganisms"
          :loading="loadingOrganisms"
          @change="handleAccessionChange"
          @visible-change="handleSearchVisibleChange"
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

    <section class="empty-card">
      <el-empty description="请选择一个 accession 查看详情" :image-size="150" />
    </section>
  </div>
</template>

<script>
import { onMounted, ref } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Refresh, Search } from '@element-plus/icons-vue';
import { useRouter } from 'vue-router';

const RECENT_ACCESSIONS_KEY = 'recent_accessions';

export default {
  name: 'AccessionCard',
  components: {
    Refresh,
    Search
  },
  setup() {
    const router = useRouter();
    const loadingOrganisms = ref(false);
    const selectedAccession = ref('');
    const organismOptions = ref([]);
    const recentAccessions = ref([]);

    const loadRecentAccessions = () => {
      try {
        const stored = JSON.parse(localStorage.getItem(RECENT_ACCESSIONS_KEY) || '[]');
        recentAccessions.value = Array.isArray(stored) ? stored.filter(Boolean) : [];
      } catch (error) {
        recentAccessions.value = [];
      }
    };

    const saveRecentAccession = (accession) => {
      const next = [
        accession,
        ...recentAccessions.value.filter((item) => item !== accession)
      ].slice(0, 8);
      recentAccessions.value = next;
      localStorage.setItem(RECENT_ACCESSIONS_KEY, JSON.stringify(next));
    };

    const fetchOrganisms = async (query = '') => {
      try {
        loadingOrganisms.value = true;
        const endpoint = query
          ? `/files/query/organisms/?search=${encodeURIComponent(query)}`
          : '/files/query/organisms/';
        const response = await axios.get(endpoint);
        const remoteOptions = Array.isArray(response.data) ? response.data : [];
        organismOptions.value = Array.from(
          new Set([...recentAccessions.value, ...remoteOptions])
        );
      } catch (error) {
        console.error('获取 accession 列表失败:', error);
        organismOptions.value = [...recentAccessions.value];
        ElMessage.error('获取 accession 列表失败');
      } finally {
        loadingOrganisms.value = false;
      }
    };

    const searchOrganisms = (query) => {
      const keyword = String(query || '').trim();
      if (keyword.length >= 2) {
        fetchOrganisms(keyword);
        return;
      }
      fetchOrganisms('');
    };

    const handleSearchVisibleChange = (visible) => {
      if (visible) {
        fetchOrganisms('');
      }
    };

    const handleAccessionChange = async (value) => {
      const accession = String(value || '').trim();
      selectedAccession.value = accession;
      if (!accession) {
        return;
      }

      saveRecentAccession(accession);
      await router.push({
        name: 'accession-detail',
        query: { accession }
      });
    };

    const refreshOptions = () => {
      fetchOrganisms('');
    };

    onMounted(() => {
      loadRecentAccessions();
      organismOptions.value = [...recentAccessions.value];
    });

    return {
      handleAccessionChange,
      handleSearchVisibleChange,
      loadingOrganisms,
      organismOptions,
      refreshOptions,
      searchOrganisms,
      selectedAccession
    };
  }
};
</script>

<style scoped>
.accession-search-page {
  min-height: calc(100vh - 160px);
  color: #132449;
}

.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 18px;
}

.page-kicker {
  color: #1760e8;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.page-heading h1 {
  margin: 5px 0 0;
  color: #1453d1;
  font-size: 25px;
  line-height: 1.2;
}

.refresh-button {
  border-color: #d6e2f4;
  color: #1760e8;
}

.search-container {
  width: min(480px, 100%);
  margin-bottom: 18px;
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(27, 54, 94, 0.08);
}

.search-icon {
  position: absolute;
  left: 14px;
  z-index: 2;
  color: #718096;
  pointer-events: none;
}

.search-select {
  width: 100%;
}

.search-select :deep(.el-select__wrapper) {
  min-height: 42px;
  padding-left: 40px;
  border-radius: 10px;
  box-shadow: inset 0 0 0 1px #e1e8f3;
}

.empty-card {
  display: grid;
  min-height: 420px;
  place-items: center;
  border: 1px solid #e4eaf3;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(35, 68, 116, 0.05);
}

.empty-card :deep(.el-empty__description p) {
  color: #7b8799;
}
</style>

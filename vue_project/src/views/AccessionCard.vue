<template>
  <div class="accession-workbench">
    <section class="accession-search-panel">
      <div class="search-grid">
        <div class="search-wrapper">
          <el-icon class="search-icon"><Search /></el-icon>
          <el-select
            v-model="selectedAccession"
            filterable
            remote
            clearable
            class="search-select"
            placeholder="搜索 Accession / 品种 / 亚群，例如 IR64"
            :remote-method="searchAccessions"
            :loading="loadingAccessions"
            @change="handleAccessionChange"
            @visible-change="handleSearchVisibleChange"
          >
            <el-option
              v-for="item in accessionOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </div>
        <el-button class="search-button" type="primary" :disabled="!selectedAccession" @click="submitSelectedAccession">
          搜索
        </el-button>
        <el-select v-model="speciesFilter" class="filter-select" placeholder="物种">
          <el-option label="物种 全部" value="" />
          <el-option label="水稻 Oryza sativa" value="ORYZA_SATIVA" />
        </el-select>
        <el-select v-model="subPopulationFilter" class="filter-select" placeholder="亚群">
          <el-option label="亚群 全部" value="" />
          <el-option v-for="item in subPopulationOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="locationFilter" class="filter-select" placeholder="地理位置">
          <el-option label="地理位置 全部" value="" />
          <el-option label="中国" value="中国" />
          <el-option label="Unknown" value="Unknown" />
        </el-select>
        <el-button class="refresh-button" :loading="loadingAccessions" @click="refreshOptions">
          刷新
        </el-button>
      </div>

      <div class="quick-examples">
        <span>示例：</span>
        <button
          v-for="item in exampleAccessions"
          :key="item"
          type="button"
          class="example-chip"
          @click="openAccession(item)"
        >
          {{ item }}
        </button>
        <span class="quick-hint">未选择时保留空状态，选择后在同页展开详情。</span>
      </div>
    </section>

    <AccessionDetailTableView v-if="routeAccession" embedded />

    <section v-else class="empty-card">
      <el-empty description="请选择一个 accession 查看详情" :image-size="150" />
    </section>
  </div>
</template>

<script>
import { computed, onMounted, ref, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Search } from '@element-plus/icons-vue';
import { useRoute, useRouter } from 'vue-router';
import AccessionDetailTableView from './AccessionDetailTableView.vue';

const RECENT_ACCESSIONS_KEY = 'recent_accessions';

const normalizeQueryValue = (value) => {
  if (Array.isArray(value)) {
    return value[0] ? String(value[0]).trim() : '';
  }
  return value ? String(value).trim() : '';
};

export default {
  name: 'AccessionCard',
  components: {
    AccessionDetailTableView,
    Search
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const loadingAccessions = ref(false);
    const selectedAccession = ref('');
    const accessionOptions = ref([]);
    const recentAccessions = ref([]);
    const speciesFilter = ref('');
    const subPopulationFilter = ref('');
    const locationFilter = ref('');
    const subPopulationOptions = ['XI', 'GJ', 'cA', 'cB', 'cE', 'WILD'];
    const exampleAccessions = ['IR64', 'C7', '02428'];

    const routeAccession = computed(() => (
      normalizeQueryValue(route.query.accession) || normalizeQueryValue(route.query.organism)
    ));

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

    const mergeOptions = (remoteOptions = []) => {
      accessionOptions.value = Array.from(
        new Set([...recentAccessions.value, ...exampleAccessions, ...remoteOptions].filter(Boolean))
      );
    };

    const fetchAccessions = async (query = '') => {
      try {
        loadingAccessions.value = true;
        const endpoint = query
          ? `/files/query/organisms/?search=${encodeURIComponent(query)}`
          : '/files/query/organisms/';
        const response = await axios.get(endpoint);
        const remoteOptions = Array.isArray(response.data) ? response.data : [];
        mergeOptions(remoteOptions);
      } catch (error) {
        console.error('获取 accession 列表失败:', error);
        mergeOptions([]);
        ElMessage.error('获取 accession 列表失败');
      } finally {
        loadingAccessions.value = false;
      }
    };

    const searchAccessions = (query) => {
      const keyword = String(query || '').trim();
      fetchAccessions(keyword.length >= 2 ? keyword : '');
    };

    const handleSearchVisibleChange = (visible) => {
      if (visible) {
        fetchAccessions('');
      }
    };

    const openAccession = async (accession) => {
      const normalizedAccession = String(accession || '').trim();
      if (!normalizedAccession) {
        return;
      }

      selectedAccession.value = normalizedAccession;
      saveRecentAccession(normalizedAccession);
      await router.push({
        name: 'accession-card',
        query: {
          ...route.query,
          accession: normalizedAccession
        }
      });
    };

    const handleAccessionChange = async (value) => {
      if (value) {
        await openAccession(value);
        return;
      }

      const nextQuery = { ...route.query };
      delete nextQuery.accession;
      delete nextQuery.organism;
      await router.push({
        name: 'accession-card',
        query: nextQuery
      });
    };

    const submitSelectedAccession = async () => {
      await openAccession(selectedAccession.value);
    };

    const refreshOptions = () => {
      fetchAccessions('');
    };

    watch(
      routeAccession,
      (accession) => {
        selectedAccession.value = accession || '';
        if (accession) {
          saveRecentAccession(accession);
          mergeOptions([]);
        }
      },
      { immediate: true }
    );

    onMounted(() => {
      loadRecentAccessions();
      mergeOptions([]);
    });

    return {
      exampleAccessions,
      handleAccessionChange,
      handleSearchVisibleChange,
      loadingAccessions,
      locationFilter,
      openAccession,
      accessionOptions,
      refreshOptions,
      routeAccession,
      searchAccessions,
      selectedAccession,
      speciesFilter,
      subPopulationFilter,
      subPopulationOptions,
      submitSelectedAccession
    };
  }
};
</script>

<style scoped>
.accession-workbench {
  min-height: calc(100vh - 160px);
  color: #132449;
}

.accession-search-panel {
  margin-bottom: 22px;
  padding: 20px;
  border: 1px solid #d9e6f6;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 12px 32px rgba(35, 68, 116, 0.07);
}

.search-grid {
  display: grid;
  grid-template-columns: minmax(320px, 1.4fr) 118px 168px 168px 168px 110px;
  gap: 14px;
  align-items: center;
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 0;
  border-radius: 12px;
  background: #ffffff;
}

.search-icon {
  position: absolute;
  left: 15px;
  z-index: 2;
  color: #718096;
  pointer-events: none;
}

.search-select {
  width: 100%;
}

.search-select :deep(.el-select__wrapper) {
  min-height: 50px;
  padding-left: 42px;
  border-radius: 12px;
  box-shadow: inset 0 0 0 1px #d7e3f3;
}

.filter-select {
  width: 100%;
}

.filter-select :deep(.el-select__wrapper) {
  min-height: 50px;
  border-radius: 12px;
  box-shadow: inset 0 0 0 1px #d7e3f3;
}

.search-button,
.refresh-button {
  min-height: 50px;
  border-radius: 12px;
  font-weight: 800;
}

.quick-examples {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  color: #667996;
  font-size: 13px;
  font-weight: 700;
}

.example-chip {
  border: 1px solid #c9dcfb;
  border-radius: 999px;
  padding: 6px 13px;
  background: #eef6ff;
  color: #1760e8;
  font-weight: 800;
  cursor: pointer;
}

.example-chip:hover {
  border-color: #8db6ff;
  background: #e3efff;
}

.quick-hint {
  color: #8a97aa;
}

.empty-card {
  display: grid;
  min-height: 420px;
  place-items: center;
  border: 1px solid #e4eaf3;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(35, 68, 116, 0.05);
}

.empty-card :deep(.el-empty__description p) {
  color: #7b8799;
}

@media (max-width: 1280px) {
  .search-grid {
    grid-template-columns: 1fr 110px 150px 150px;
  }
}
</style>

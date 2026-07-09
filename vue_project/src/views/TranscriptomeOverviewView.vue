<template>
  <div class="transcriptome-view">
    <div class="page-header">
      <div>
        <h2 class="title">转录组表</h2>
      </div>
    </div>

    <section class="filter-card">
      <div class="search-box">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="搜索物种 / Accession / 品种"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
      </div>
      <el-select v-model="filters.species_id" clearable placeholder="物种：全部" @change="handleFilterChange">
        <el-option
          v-for="item in filterOptions.species"
          :key="item.id"
          :label="item.label"
          :value="String(item.id)"
        />
      </el-select>
      <el-select v-model="filters.accession_id" clearable placeholder="Accession：全部" @change="handleFilterChange">
        <el-option
          v-for="item in filteredAccessionOptions"
          :key="item.id"
          :label="item.label"
          :value="String(item.id)"
        />
      </el-select>
      <el-select v-model="filters.assembly_id" clearable placeholder="参考基因组版本：全部" @change="handleFilterChange">
        <el-option
          v-for="item in filteredAssemblyOptions"
          :key="item.id"
          :label="item.label"
          :value="String(item.id)"
        />
      </el-select>
      <el-select v-model="filters.sample_type" clearable placeholder="样本类型：全部" @change="handleFilterChange">
        <el-option
          v-for="item in sampleTypeOptions"
          :key="item"
          :label="item"
          :value="item"
        />
      </el-select>
      <el-button class="refresh-button" @click="refreshList">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </section>

    <section class="table-card">
      <div class="table-title-row">
        <div>
          <h3>转录组数据列表</h3>
          <p>Transcriptome Data List</p>
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="tableData"
        border
        class="transcriptome-table"
        :header-cell-style="tableHeaderStyle"
        empty-text="暂无转录组数据"
      >
        <el-table-column label="物种" min-width="230">
          <template #default="scope">
            <div class="species-cell">
              <span class="species-icon">⌘</span>
              <div>
                <strong>{{ displayValue(scope.row.species_name) }}</strong>
                <em>{{ displayValue(scope.row.latin_name) }}</em>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="品种" min-width="150">
          <template #default="scope">
            <router-link
              v-if="scope.row.accession && scope.row.accession !== '-'"
              class="accession-link"
              :to="{ path: '/accession-card', query: { accession: scope.row.accession } }"
            >
              {{ scope.row.accession }}
            </router-link>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="参考基因组版本" min-width="190">
          <template #default="scope">
            <span class="assembly-chip">{{ displayValue(scope.row.assembly_name) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="样本类型" min-width="140">
          <template #default="scope">
            <span v-if="scope.row.sample_type && scope.row.sample_type !== '-'" :class="['sample-tag', sampleTypeClass(scope.row.sample_type)]">
              {{ scope.row.sample_type }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="数据大小" min-width="140">
          <template #default="scope">
            <span class="size-text">{{ displayValue(scope.row.total_size_display) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" min-width="190" fixed="right">
          <template #default="scope">
            <div class="action-buttons">
              <el-button size="small" plain @click="viewDetail(scope.row)">查看详情</el-button>
              <el-button size="small" plain type="primary" @click="openFilesDrawer(scope.row)">查看文件</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </section>

    <el-drawer
      v-model="fileDrawerVisible"
      :title="drawerTitle"
      size="560px"
      class="transcriptome-file-drawer"
    >
      <div v-loading="drawerLoading" class="drawer-content">
        <el-table :data="drawerFiles" border :header-cell-style="drawerHeaderStyle" empty-text="暂无文件">
          <el-table-column label="文件名" min-width="170">
            <template #default="scope">
              <div class="file-name">{{ displayValue(scope.row.file_name) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="文件角色" min-width="130">
            <template #default="scope">
              <span class="role-chip">{{ displayValue(scope.row.file_role_display || scope.row.file_role) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="文件类型" width="90">
            <template #default="scope">{{ displayValue(scope.row.file_type) }}</template>
          </el-table-column>
          <el-table-column label="文件大小" width="110">
            <template #default="scope">{{ displayValue(scope.row.file_size_display) }}</template>
          </el-table-column>
          <el-table-column label="MD5" min-width="130">
            <template #default="scope">
              <span class="md5-text">{{ displayValue(scope.row.md5) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="scope">
              <div class="drawer-actions">
                <a class="download-link" :href="datafileDownloadUrl(scope.row)" target="_blank">下载</a>
                <button v-if="scope.row.file_path" class="copy-button" type="button" @click="copyPath(scope.row.file_path)">复制路径</button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { Refresh, Search } from '@element-plus/icons-vue';

const DEFAULT_FILTERS = {
  keyword: '',
  species_id: '',
  accession_id: '',
  assembly_id: '',
  sample_type: ''
};

export default {
  name: 'TranscriptomeOverviewView',
  components: {
    Refresh,
    Search
  },
  setup() {
    const router = useRouter();
    const loading = ref(false);
    const drawerLoading = ref(false);
    const fileDrawerVisible = ref(false);
    const drawerTitle = ref('Transcriptome 文件列表');
    const drawerFiles = ref([]);
    const tableData = ref([]);
    const filters = reactive({ ...DEFAULT_FILTERS });
    const pagination = reactive({ page: 1, page_size: 20, total: 0 });
    const filterOptions = reactive({ species: [], accessions: [], assemblies: [], sample_types: [] });

    const tableHeaderStyle = { background: '#f0f6fd', color: '#244263', fontWeight: 900 };
    const drawerHeaderStyle = { background: '#f0f6fd', color: '#244263', fontWeight: 900 };

    const filteredAccessionOptions = computed(() => {
      if (!filters.species_id) return filterOptions.accessions;
      return filterOptions.accessions.filter(item => String(item.species_id || '') === String(filters.species_id));
    });

    const filteredAssemblyOptions = computed(() => {
      if (!filters.accession_id) return filterOptions.assemblies;
      return filterOptions.assemblies.filter(item => String(item.accession_id || '') === String(filters.accession_id));
    });

    const sampleTypeOptions = computed(() => filterOptions.sample_types.length ? filterOptions.sample_types : ['all', 'leaf', 'root', 'stem', 'panicles', 'shoot']);

    const buildParams = () => ({
      keyword: filters.keyword || undefined,
      species_id: filters.species_id || undefined,
      accession_id: filters.accession_id || undefined,
      assembly_id: filters.assembly_id || undefined,
      sample_type: filters.sample_type || undefined,
      page: pagination.page,
      page_size: pagination.page_size
    });

    const applyFilterOptions = (payload) => {
      const options = payload.filters || {};
      filterOptions.species = options.species || [];
      filterOptions.accessions = options.accessions || [];
      filterOptions.assemblies = options.assemblies || [];
      filterOptions.sample_types = options.sample_types || [];
    };

    const fetchList = async () => {
      loading.value = true;
      try {
        const response = await axios.get('/files/query/transcriptome-list/', { params: buildParams() });
        const payload = response.data || {};
        tableData.value = payload.results || [];
        pagination.total = payload.pagination?.total || 0;
        pagination.page = payload.pagination?.page || pagination.page;
        pagination.page_size = payload.pagination?.page_size || pagination.page_size;
        applyFilterOptions(payload);
      } catch (error) {
        console.error('获取转录组列表失败:', error);
        ElMessage.error('获取转录组列表失败');
      } finally {
        loading.value = false;
      }
    };

    const resetPageAndFetch = () => {
      pagination.page = 1;
      fetchList();
    };

    const handleSearch = () => resetPageAndFetch();
    const handleFilterChange = () => resetPageAndFetch();
    const refreshList = () => fetchList();
    const handleCurrentChange = (page) => {
      pagination.page = page;
      fetchList();
    };
    const handleSizeChange = (pageSize) => {
      pagination.page_size = pageSize;
      pagination.page = 1;
      fetchList();
    };

    const viewDetail = (row) => {
      if (!row.accession || row.accession === '-') return;
      router.push({ path: '/accession-card', query: { accession: row.accession } });
    };

    const openFilesDrawer = async (row) => {
      fileDrawerVisible.value = true;
      drawerLoading.value = true;
      drawerTitle.value = `${row.accession || '-'} / ${row.sample_type || '-'} / Transcriptome 文件列表`;
      drawerFiles.value = [];
      try {
        const response = await axios.get('/files/query/transcriptome-files/', {
          params: {
            accession_id: row.accession_id || undefined,
            assembly_id: row.assembly_id || undefined,
            sample_type: row.sample_type && row.sample_type !== '-' ? row.sample_type : undefined
          }
        });
        const payload = response.data || {};
        drawerTitle.value = payload.title || drawerTitle.value;
        drawerFiles.value = payload.files || [];
      } catch (error) {
        console.error('获取转录组文件失败:', error);
        ElMessage.error('获取转录组文件失败');
      } finally {
        drawerLoading.value = false;
      }
    };

    const datafileDownloadUrl = (file) => file.download_url || `/gd/api/files/data-files/${file.file_id}/download/`;

    const copyPath = async (path) => {
      try {
        await navigator.clipboard.writeText(path);
        ElMessage.success('路径已复制');
      } catch (error) {
        ElMessage.error('复制失败');
      }
    };

    const displayValue = (value) => value || '-';

    const sampleTypeClass = (sampleType) => {
      const normalized = String(sampleType || '').toLowerCase();
      return {
        leaf: 'tag-leaf',
        root: 'tag-root',
        stem: 'tag-stem',
        panicles: 'tag-panicles',
        shoot: 'tag-shoot',
        all: 'tag-all'
      }[normalized] || 'tag-other';
    };

    onMounted(fetchList);

    return {
      loading,
      drawerLoading,
      fileDrawerVisible,
      drawerTitle,
      drawerFiles,
      tableData,
      filters,
      pagination,
      filterOptions,
      filteredAccessionOptions,
      filteredAssemblyOptions,
      sampleTypeOptions,
      tableHeaderStyle,
      drawerHeaderStyle,
      handleSearch,
      handleFilterChange,
      refreshList,
      handleCurrentChange,
      handleSizeChange,
      viewDetail,
      openFilesDrawer,
      datafileDownloadUrl,
      copyPath,
      displayValue,
      sampleTypeClass
    };
  }
};
</script>

<style scoped>
.transcriptome-view {
  min-height: calc(100vh - 64px);
  padding: 0;
  color: #0c2347;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
}

.title {
  margin: 0;
  color: #145bd2;
  font-size: 28px;
  line-height: 1.2;
  font-weight: 900;
}

.filter-card {
  display: grid;
  grid-template-columns: minmax(260px, 1.35fr) repeat(4, minmax(150px, 0.75fr)) 104px;
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid #dbe7f5;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 14px 36px rgba(36, 68, 111, 0.08);
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 12px;
  border: 1px solid #dbe7f5;
  border-radius: 8px;
  background: #fff;
}

.search-icon {
  color: #71839c;
}

.search-box :deep(.el-input__wrapper) {
  box-shadow: none;
  padding: 0;
}

.refresh-button {
  height: 42px;
  font-weight: 800;
}

.table-card {
  overflow: hidden;
  border: 1px solid #dbe7f5;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 14px 36px rgba(36, 68, 111, 0.08);
}

.table-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid #dbe7f5;
}

.table-title-row h3 {
  margin: 0;
  color: #14345e;
  font-size: 18px;
  font-weight: 900;
}

.table-title-row p {
  margin: 4px 0 0;
  color: #8a9bb0;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 800;
}

.transcriptome-table {
  width: 100%;
}

.transcriptome-table :deep(.el-table__cell) {
  padding: 14px 0;
}

.species-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.species-icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #e8f9ef;
  color: #08a86f;
  font-size: 22px;
  font-weight: 900;
}

.species-cell strong {
  display: block;
  color: #08264b;
  font-size: 16px;
  font-weight: 900;
}

.species-cell em {
  display: block;
  margin-top: 3px;
  color: #53647b;
  font-size: 13px;
  font-weight: 800;
}

.accession-link {
  color: #1768f2;
  text-decoration: none;
  font-weight: 900;
}

.assembly-chip,
.role-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid #d5e3f5;
  border-radius: 7px;
  background: #f5f9ff;
  color: #304967;
  font-weight: 800;
}

.sample-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 26px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13px;
  font-weight: 900;
}

.tag-leaf { background: #e8f8ef; color: #0d8b56; border-color: #bcebd4; }
.tag-root { background: #f0ebff; color: #6e4bdc; border-color: #d9ccff; }
.tag-stem { background: #fff1dc; color: #c06800; border-color: #ffd9a1; }
.tag-panicles { background: #fff0e8; color: #d95d22; border-color: #ffcdb9; }
.tag-shoot { background: #eaf3ff; color: #1768f2; border-color: #c7dcff; }
.tag-all { background: #eef2f7; color: #64748b; border-color: #d9e2ec; }
.tag-other { background: #f4f6f9; color: #60738e; border-color: #dfe6ef; }

.size-text {
  color: #112a50;
  font-weight: 900;
}

.action-buttons,
.drawer-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  padding: 16px 18px;
  border-top: 1px solid #dbe7f5;
}

.drawer-content {
  min-height: 300px;
}

.file-name {
  color: #0d2e57;
  font-weight: 900;
  word-break: break-all;
}

.md5-text {
  display: inline-block;
  max-width: 160px;
  overflow: hidden;
  color: #72839a;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.download-link,
.copy-button {
  color: #1768f2;
  font-weight: 900;
  text-decoration: none;
}

.copy-button {
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

@media (max-width: 1320px) {
  .filter-card {
    grid-template-columns: 1fr 1fr;
  }
}
</style>

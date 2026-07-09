<template>
  <div class="data-overview-modern">
    <header class="overview-header">
      <div>
        <p class="breadcrumb">首页 / 数据资源</p>
        <h1>数据一览表</h1>
      </div>
      <button class="refresh-button" type="button" @click="fetchOverview">刷新</button>
    </header>

    <section class="filter-panel">
      <div class="search-box">
        <span class="search-icon">⌕</span>
        <input
          v-model="searchKeyword"
          type="text"
          placeholder="搜索 Accession / 物种 / 数据集 / 文件名"
          @keyup.enter="applyFilters"
        />
        <button type="button" @click="applyFilters">搜索</button>
      </div>

      <label class="filter-item">
        <span>物种</span>
        <select v-model="selectedSpecies" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in filters.species" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span>亚群</span>
        <select v-model="selectedSubPopulation" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in filters.sub_populations" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span>数据类型</span>
        <select v-model="selectedCategory" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in dataCategories" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span>文件角色</span>
        <select v-model="selectedFileRole" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in filters.file_roles" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span>地理位置</span>
        <select v-model="selectedLocation" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in filters.locations" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <button class="plain-button" type="button" @click="resetFilters">重置</button>
      <button class="plain-button more" type="button">更多条件</button>
    </section>

    <section class="summary-grid">
      <article v-for="card in summaryCards" :key="card.key" class="summary-card">
        <div :class="['summary-icon', card.theme]">{{ card.icon }}</div>
        <div>
          <div class="summary-label">{{ card.label }}</div>
          <div class="summary-value">{{ card.value }}<span v-if="card.unit" class="summary-unit">{{ card.unit }}</span></div>
        </div>
      </article>
    </section>

    <section class="view-switcher">
      <div class="tabs">
        <button :class="{ active: activeView === 'matrix' }" type="button" @click="activeView = 'matrix'">矩阵视图</button>
        <button :class="{ active: activeView === 'detail' }" type="button" @click="activeView = 'detail'">明细视图</button>
      </div>
      <button class="export-button" type="button">导出当前结果</button>
    </section>

    <section v-if="loading" class="loading-card">正在加载数据一览表...</section>

    <section v-else-if="activeView === 'matrix'" class="table-card">
      <div class="table-scroll">
        <table class="matrix-table">
          <thead>
            <tr>
              <th rowspan="2">Accession</th>
              <th colspan="3">基本信息</th>
              <th :colspan="dataCategories.length">文件统计（点击数量查看文件）</th>
              <th rowspan="2">地理位置</th>
            </tr>
            <tr>
              <th>物种</th>
              <th>亚群</th>
              <th>样本数</th>
              <th v-for="category in dataCategories" :key="category.key">
                {{ category.label }}<br />
                <span>{{ category.en_label }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in matrixRows" :key="row.accession_id">
              <td><router-link class="accession-link" :to="{ path: '/accession-card', query: { accession: row.accession } }">{{ row.accession }}</router-link></td>
              <td>{{ row.species_name || '-' }}</td>
              <td><span class="sub-population">{{ row.sub_population || 'Unknown' }}</span></td>
              <td>{{ row.sample_count }}</td>
              <td v-for="category in dataCategories" :key="`${row.accession_id}-${category.key}`">
                <button
                  v-if="cellStatus(row, category.key) === 'available'"
                  class="matrix-cell-button"
                  type="button"
                  @click="openFileDrawer(row, category.key)"
                >
                  {{ cellDisplay(row, category.key) }}
                </button>
                <span v-else-if="cellStatus(row, category.key) === 'coming_soon'" class="building-state">建设中</span>
                <span v-else class="empty-state">-</span>
              </td>
              <td>{{ row.location_display || '-' }}</td>
            </tr>
            <tr v-if="!matrixRows.length">
              <td class="empty-table" :colspan="dataCategories.length + 5">暂无符合条件的数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-else class="table-card detail-card">
      <div class="table-scroll">
        <table class="detail-table">
          <thead>
            <tr>
              <th>物种</th>
              <th>Accession</th>
              <th>数据类型</th>
              <th>数据集 (Dataset)</th>
              <th>组装版本 (Assembly)</th>
              <th>注释版本 (Annotation)</th>
              <th>文件数</th>
              <th>数据量</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in detailRows" :key="`${row.accession_id}-${row.category}-${row.dataset_name}`">
              <td>{{ row.species_name || '-' }}</td>
              <td><router-link class="accession-link" :to="{ path: '/accession-card', query: { accession: row.accession } }">{{ row.accession }}</router-link></td>
              <td>{{ row.category_display }}</td>
              <td>{{ row.dataset_name }}</td>
              <td>{{ row.assembly_name }}</td>
              <td>{{ row.annotation_name }}</td>
              <td>{{ row.file_count || '-' }}</td>
              <td>{{ row.total_size_display || '-' }}</td>
              <td>{{ shortDate(row.updated_at) }}</td>
              <td>
                <button
                  v-if="row.status === 'available'"
                  class="file-button"
                  type="button"
                  @click="openFileDrawer(row, row.category)"
                >
                  查看文件
                </button>
                <span v-else class="building-state">建设中</span>
              </td>
            </tr>
            <tr v-if="!detailRows.length">
              <td class="empty-table" colspan="10">暂无明细数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <footer class="pagination-bar">
      <span>共 {{ totalCount }} 条</span>
      <select v-model.number="pageSize" @change="changePageSize">
        <option :value="20">20条/页</option>
        <option :value="50">50条/页</option>
        <option :value="100">100条/页</option>
      </select>
      <button type="button" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
      <strong>{{ currentPage }}</strong>
      <button type="button" :disabled="!hasNextPage" @click="changePage(currentPage + 1)">下一页</button>
    </footer>

    <div v-if="drawerOpen" class="drawer-mask" @click="closeDrawer"></div>
    <aside :class="['file-drawer', { open: drawerOpen }]">
      <header class="drawer-header">
        <div>
          <h2>{{ drawerPayload.title || '文件列表' }}</h2>
          <p>DataFile 下载入口</p>
        </div>
        <button type="button" @click="closeDrawer">×</button>
      </header>

      <section class="relation-overview">
        <p class="section-kicker">关系概览</p>
        <div class="relation-flow">
          <span>Accession {{ drawerPayload.relation_overview?.accession || '-' }}</span>
          <span>→</span>
          <span>{{ drawerPayload.relation_overview?.assembly || '-' }}</span>
          <span>→</span>
          <span>{{ drawerPayload.relation_overview?.annotation || 'DataFile' }}</span>
        </div>
      </section>

      <section class="drawer-table-wrap">
        <table>
          <thead>
            <tr>
              <th>文件名</th>
              <th>文件角色</th>
              <th>类型</th>
              <th>大小</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in drawerPayload.files" :key="file.file_id">
              <td>{{ file.file_name }}</td>
              <td>{{ file.file_role_display }}</td>
              <td>{{ file.file_type || '-' }}</td>
              <td>{{ file.file_size_display || '-' }}</td>
              <td><a class="download-link" :href="file.download_url">下载</a></td>
            </tr>
            <tr v-if="!drawerPayload.files?.length">
              <td class="empty-table" colspan="5">暂无文件</td>
            </tr>
          </tbody>
        </table>
      </section>
    </aside>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const DEFAULT_CATEGORIES = [
  { key: 'raw_data', label: '原始数据', en_label: 'Raw Data' },
  { key: 'genome', label: '基因组', en_label: 'Genome' },
  { key: 'annotation', label: '注释', en_label: 'Annotation' },
  { key: 'transcriptome', label: '转录组', en_label: 'Transcriptome' },
  { key: 'population', label: '群体遗传', en_label: 'Population' },
  { key: 'codon', label: '密码子', en_label: 'Codon' },
  { key: 'centromere', label: '着丝粒', en_label: 'Centromere' },
  { key: 'tes', label: '转座子', en_label: 'TEs' },
  { key: 'coreblocks', label: '核心可变区块', en_label: 'CoreBlocks' },
  { key: 'ncrna', label: 'ncRNA', en_label: 'ncRNA' }
]

export default {
  name: 'DataOverviewView',
  setup() {
    const loading = ref(false)
    const activeView = ref('matrix')
    const searchKeyword = ref('')
    const selectedSpecies = ref('')
    const selectedSubPopulation = ref('')
    const selectedCategory = ref('')
    const selectedFileRole = ref('')
    const selectedLocation = ref('')
    const currentPage = ref(1)
    const pageSize = ref(20)
    const totalCount = ref(0)
    const summary = ref({})
    const filters = ref({ species: [], sub_populations: [], locations: [], data_categories: [], file_roles: [] })
    const matrixRows = ref([])
    const detailRows = ref([])
    const drawerOpen = ref(false)
    const drawerPayload = ref({ files: [], relation_overview: {} })

    const dataCategories = computed(() => {
      const categories = filters.value.data_categories?.length ? filters.value.data_categories : DEFAULT_CATEGORIES
      if (!selectedCategory.value) return categories
      return categories.filter(category => category.key === selectedCategory.value)
    })

    const summaryCards = computed(() => [
      { key: 'accession', label: '材料(Accession)', value: summary.value.accession_count || 0, icon: '苗', theme: 'green' },
      { key: 'dataset', label: '数据集(Dataset)', value: summary.value.dataset_count || 0, icon: '集', theme: 'purple' },
      { key: 'datafile', label: '文件(DataFile)', value: summary.value.datafile_count || 0, icon: '文', theme: 'blue' },
      { key: 'total_size', label: '总数据量', value: summary.value.total_size_display || '-', icon: '量', theme: 'orange' },
      { key: 'geo', label: '地理位置', value: summary.value.geo_location_count || 0, unit: '个点位', icon: '地', theme: 'cyan' },
      { key: 'updated', label: '更新时间', value: summary.value.latest_update || '-', icon: '时', theme: 'pink' }
    ])

    const hasNextPage = computed(() => currentPage.value * pageSize.value < totalCount.value)

    const requestParams = () => {
      const params = { page: currentPage.value, page_size: pageSize.value }
      if (searchKeyword.value.trim()) params.search = searchKeyword.value.trim()
      if (selectedSpecies.value) params.species = selectedSpecies.value
      if (selectedSubPopulation.value) params.sub_populations = selectedSubPopulation.value
      if (selectedCategory.value) params.category = selectedCategory.value
      if (selectedFileRole.value) params.file_role = selectedFileRole.value
      if (selectedLocation.value) params.location = selectedLocation.value
      return params
    }

    const fetchOverview = async () => {
      loading.value = true
      try {
        const response = await axios.get('/files/query/data-overview/', { params: requestParams() })
        const payload = response.data || {}
        summary.value = payload.summary || {}
        filters.value = payload.filters || filters.value
        matrixRows.value = payload.matrix_rows || []
        detailRows.value = payload.detail_rows || []
        totalCount.value = payload.count || 0
      } catch (error) {
        console.error('获取数据一览表失败:', error)
        ElMessage.error('获取数据一览表失败')
      } finally {
        loading.value = false
      }
    }

    const applyFilters = () => {
      currentPage.value = 1
      fetchOverview()
    }

    const resetFilters = () => {
      searchKeyword.value = ''
      selectedSpecies.value = ''
      selectedSubPopulation.value = ''
      selectedCategory.value = ''
      selectedFileRole.value = ''
      selectedLocation.value = ''
      currentPage.value = 1
      fetchOverview()
    }

    const changePage = (page) => {
      currentPage.value = page
      fetchOverview()
    }

    const changePageSize = () => {
      currentPage.value = 1
      fetchOverview()
    }

    const cell = (row, categoryKey) => row.cells?.[categoryKey] || {}
    const cellStatus = (row, categoryKey) => cell(row, categoryKey).status || 'empty'
    const cellDisplay = (row, categoryKey) => cell(row, categoryKey).display || '-'

    const openFileDrawer = async (row, category) => {
      const accession = row.accession
      try {
        const response = await axios.get('/files/query/data-overview-files/', { params: { accession, category } })
        drawerPayload.value = response.data || { files: [], relation_overview: {} }
        drawerOpen.value = true
      } catch (error) {
        console.error('获取文件列表失败:', error)
        ElMessage.error('获取文件列表失败')
      }
    }

    const closeDrawer = () => {
      drawerOpen.value = false
    }

    const shortDate = (value) => {
      if (!value) return '-'
      return String(value).slice(0, 10)
    }

    onMounted(fetchOverview)

    return {
      loading,
      activeView,
      searchKeyword,
      selectedSpecies,
      selectedSubPopulation,
      selectedCategory,
      selectedFileRole,
      selectedLocation,
      currentPage,
      pageSize,
      totalCount,
      summaryCards,
      filters,
      dataCategories,
      matrixRows,
      detailRows,
      drawerOpen,
      drawerPayload,
      hasNextPage,
      fetchOverview,
      applyFilters,
      resetFilters,
      changePage,
      changePageSize,
      cellStatus,
      cellDisplay,
      openFileDrawer,
      closeDrawer,
      shortDate
    }
  }
}
</script>

<style scoped>
.data-overview-modern {
  min-height: 100vh;
  padding: 18px 22px 36px;
  background: #f7faff;
  color: #162844;
}

.overview-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 16px;
}

.breadcrumb {
  margin: 0 0 8px;
  color: #6f7f96;
  font-size: 13px;
  font-weight: 700;
}

.overview-header h1 {
  margin: 0;
  font-size: 30px;
  letter-spacing: 0.02em;
}

.refresh-button,
.plain-button,
.export-button,
.file-button {
  border: 1px solid #cfe0f5;
  border-radius: 10px;
  background: #fff;
  color: #31516f;
  font-weight: 800;
  cursor: pointer;
}

.refresh-button,
.export-button {
  height: 40px;
  padding: 0 16px;
}

.filter-panel {
  display: grid;
  grid-template-columns: minmax(340px, 1.35fr) repeat(5, minmax(126px, .55fr)) 90px 116px;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 1px solid #e1eaf5;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 14px 36px rgba(31, 79, 136, 0.08);
}

.search-box {
  display: flex;
  align-items: center;
  overflow: hidden;
  height: 46px;
  border: 1px solid #dce7f4;
  border-radius: 11px;
  background: #fff;
}

.search-icon {
  padding-left: 14px;
  color: #7b889b;
  font-size: 20px;
}

.search-box input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  outline: 0;
  padding: 0 12px;
  color: #172944;
}

.search-box button {
  width: 88px;
  height: 100%;
  border: 0;
  color: #fff;
  background: #1f6fee;
  font-weight: 900;
}

.filter-item {
  display: grid;
  grid-template-columns: auto minmax(86px, 1fr);
  align-items: center;
  gap: 8px;
  height: 46px;
  padding: 0 12px;
  border: 1px solid #dce7f4;
  border-radius: 11px;
  background: #fff;
  color: #384d68;
  font-size: 13px;
  font-weight: 800;
}

.filter-item select,
.pagination-bar select {
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #253a58;
  font-weight: 700;
}

.plain-button {
  height: 46px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0 14px;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 78px;
  padding: 13px 14px;
  border: 1px solid #e1e8f3;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(35, 68, 116, .06);
}

.summary-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  border-radius: 12px;
  background: #edf4ff;
  color: #1760e8;
  font-size: 20px;
  font-weight: 800;
}

.summary-icon.green,
.summary-icon.purple,
.summary-icon.blue,
.summary-icon.orange,
.summary-icon.cyan,
.summary-icon.pink {
  background: #edf4ff;
  color: #1760e8;
}

.summary-label {
  color: #718096;
  font-size: 12px;
}

.summary-value {
  margin-top: 4px;
  color: #153a7a;
  font-size: 21px;
  font-weight: 800;
}

.summary-unit {
  margin-left: 4px;
  color: #7a8798;
  font-size: 12px;
  font-weight: 800;
}

.view-switcher {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 10px 0 12px;
  border-bottom: 1px solid #dce7f4;
}

.tabs {
  display: flex;
  gap: 28px;
}

.tabs button {
  padding: 14px 2px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: #6e7d91;
  font-size: 15px;
  font-weight: 950;
  cursor: pointer;
}

.tabs button.active {
  color: #1f6fee;
  border-bottom-color: #1f6fee;
}

.loading-card,
.table-card {
  border: 1px solid #dce7f4;
  border-radius: 15px;
  background: #fff;
  box-shadow: 0 14px 34px rgba(31, 79, 136, 0.08);
}

.loading-card {
  padding: 64px;
  text-align: center;
  color: #6e7d91;
}

.table-scroll {
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

.matrix-table {
  min-width: 1480px;
}

.detail-table {
  min-width: 1120px;
}

th,
td {
  padding: 13px 12px;
  border-right: 1px solid #e7eef7;
  border-bottom: 1px solid #e7eef7;
  text-align: center;
  white-space: nowrap;
  font-size: 13px;
}

th {
  color: #40536c;
  background: linear-gradient(180deg, #f8fbff 0%, #edf5ff 100%);
  font-weight: 950;
}

th span {
  color: #68788d;
  font-size: 11px;
}

.matrix-table td:first-child,
.matrix-table th:first-child {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #fff;
  text-align: left;
  font-weight: 950;
}

.matrix-table th:first-child {
  background: #f1f7ff;
}

.accession-link,
.matrix-cell-button,
.download-link {
  color: #1f6fee;
  font-weight: 950;
  text-decoration: none;
}

.matrix-cell-button {
  border: 0;
  background: transparent;
  color: #18a567;
  cursor: pointer;
}

.file-button {
  height: 30px;
  padding: 0 12px;
  color: #1f6fee;
}

.sub-population {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  color: #167f4d;
  background: #e8f8ef;
  font-weight: 900;
}

.empty-state,
.empty-table {
  color: #9aa7b8;
  font-weight: 800;
}

.building-state {
  color: #a86614;
  font-weight: 900;
}

.detail-card {
  min-height: 320px;
}

.pagination-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  color: #52637a;
  font-weight: 800;
}

.pagination-bar button,
.pagination-bar select {
  height: 32px;
  padding: 0 10px;
  border: 1px solid #d6e3f2;
  border-radius: 8px;
  background: #fff;
}

.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 30;
  background: rgba(10, 25, 45, 0.18);
}

.file-drawer {
  position: fixed;
  top: 82px;
  right: 24px;
  bottom: 30px;
  z-index: 31;
  display: none;
  width: 450px;
  overflow: hidden;
  border: 1px solid #dce7f4;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 28px 80px rgba(22, 48, 86, 0.24);
}

.file-drawer.open {
  display: block;
}

.drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid #e7eef7;
  background: linear-gradient(135deg, #f7fbff 0%, #fff 100%);
}

.drawer-header h2 {
  margin: 0;
  color: #123a7a;
  font-size: 18px;
}

.drawer-header p {
  margin: 8px 0 0;
  color: #6f7f95;
  font-size: 13px;
}

.drawer-header button {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: #eef4fb;
  color: #38536f;
  font-size: 18px;
  cursor: pointer;
}

.relation-overview {
  margin: 16px 18px;
  padding: 14px;
  border: 1px dashed #bfd3ee;
  border-radius: 14px;
  background: #f8fbff;
}

.section-kicker {
  margin: 0 0 10px;
  color: #4d6684;
  font-size: 12px;
  font-weight: 950;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.relation-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: #24466f;
  font-size: 12px;
  font-weight: 900;
}

.relation-flow span:nth-child(odd) {
  padding: 7px 9px;
  border: 1px solid #d6e4f4;
  border-radius: 9px;
  background: #fff;
}

.drawer-table-wrap {
  max-height: calc(100% - 178px);
  overflow: auto;
  padding: 0 18px 18px;
}

.drawer-table-wrap table {
  min-width: 0;
}

.drawer-table-wrap th,
.drawer-table-wrap td {
  padding: 10px 8px;
  text-align: left;
  font-size: 12px;
}
</style>

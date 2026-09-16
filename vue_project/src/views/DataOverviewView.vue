<template>
  <div class="data-overview-modern">
    <header class="overview-header">
      <div>
        <p class="breadcrumb">{{ $t('page.dataOverview.breadcrumb') }}</p>
        <h1>{{ $t('page.dataOverview.title') }}</h1>
      </div>
      <button class="refresh-button" type="button" @click="fetchOverview">{{ $t('common.refresh') }}</button>
    </header>

    <section class="filter-panel">
      <div class="search-box">
        <span class="search-icon">⌕</span>
        <input
          v-model="searchKeyword"
          type="text"
          :placeholder="$t('page.dataOverview.searchPrompt')"
          @keyup.enter="applyFilters"
        />
        <button type="button" @click="applyFilters">{{ $t('common.search') }}</button>
      </div>

      <label class="filter-item">
        <span>{{ $t('page.dataOverview.filters.species') }}</span>
        <select v-model="selectedSpecies" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in filters.species" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span>{{ $t('page.dataOverview.filters.subPopulation') }}</span>
        <select v-model="selectedSubPopulation" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in filters.sub_populations" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span>{{ $t('page.dataOverview.filters.dataType') }}</span>
        <select v-model="selectedCategory" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in dataCategories" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span>{{ $t('page.dataOverview.filters.fileRole') }}</span>
        <select v-model="selectedFileRole" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in filters.file_roles" :key="item.key" :value="item.key">{{ fileRoleLabel(item.key, item.label) }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span>{{ $t('page.dataOverview.filters.location') }}</span>
        <select v-model="selectedLocation" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in filters.locations" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <button class="plain-button" type="button" @click="resetFilters">{{ $t('common.reset') }}</button>
      <button class="plain-button more" type="button">{{ $t('common.moreFilters') }}</button>
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
        <button :class="{ active: activeView === 'matrix' }" type="button" @click="activeView = 'matrix'">{{ $t('page.dataOverview.matrixView') }}</button>
        <button :class="{ active: activeView === 'detail' }" type="button" @click="activeView = 'detail'">{{ $t('page.dataOverview.detailView') }}</button>
      </div>
      <button class="export-button" type="button">{{ $t('common.exportCurrent') }}</button>
    </section>

    <section v-if="loading" class="loading-card">{{ $t('page.dataOverview.loadingOverview') }}</section>

    <section v-else-if="activeView === 'matrix'" class="table-card">
      <div class="table-scroll">
        <table class="matrix-table">
          <thead>
            <tr>
              <th rowspan="2">Accession</th>
              <th colspan="3">{{ $t('page.dataOverview.basicInformation') }}</th>
              <th :colspan="dataCategories.length">{{ $t('page.dataOverview.fileStatistics') }}</th>
              <th rowspan="2">{{ $t('common.location') }}</th>
            </tr>
            <tr>
              <th>{{ $t('common.species') }}</th>
              <th>{{ $t('common.subPopulation') }}</th>
              <th>{{ $t('page.dataOverview.sampleCount') }}</th>
              <th v-for="category in dataCategories" :key="category.key">
                {{ category.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in matrixRows" :key="row.accession_id">
              <td><router-link class="accession-link" :to="{ path: '/accession-card', query: { accession: row.accession } }">{{ row.accession }}</router-link></td>
              <td>{{ row.species_name || '-' }}</td>
              <td><span class="sub-population">{{ row.sub_population || $t('common.unknown') }}</span></td>
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
                <span v-else-if="cellStatus(row, category.key) === 'coming_soon'" class="building-state">{{ $t('page.dataOverview.comingSoon') }}</span>
                <span v-else class="empty-state">-</span>
              </td>
              <td>{{ row.location_display || '-' }}</td>
            </tr>
            <tr v-if="!matrixRows.length">
              <td class="empty-table" :colspan="dataCategories.length + 5">{{ $t('page.dataOverview.noMatches') }}</td>
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
              <th>{{ $t('common.species') }}</th>
              <th>Accession</th>
              <th>{{ $t('common.dataType') }}</th>
              <th>{{ $t('page.dataOverview.columns.dataset') }}</th>
              <th>{{ $t('page.dataOverview.columns.assembly') }}</th>
              <th>{{ $t('page.dataOverview.columns.annotation') }}</th>
              <th>{{ $t('page.dataOverview.columns.fileCount') }}</th>
              <th>{{ $t('page.dataOverview.columns.dataSize') }}</th>
              <th>{{ $t('page.dataOverview.columns.updatedAt') }}</th>
              <th>{{ $t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in detailRows" :key="`${row.accession_id}-${row.category}-${row.dataset_name}`">
              <td>{{ row.species_name || '-' }}</td>
              <td><router-link class="accession-link" :to="{ path: '/accession-card', query: { accession: row.accession } }">{{ row.accession }}</router-link></td>
              <td>{{ categoryLabel(row.category) }}</td>
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
                  {{ $t('page.accessionDetail.viewFiles') }}
                </button>
                <span v-else class="building-state">{{ $t('page.dataOverview.comingSoon') }}</span>
              </td>
            </tr>
            <tr v-if="!detailRows.length">
              <td class="empty-table" colspan="10">{{ $t('page.dataOverview.noDetails') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <footer class="pagination-bar">
      <span>{{ $t('common.totalCount', { count: totalCount }) }}</span>
      <select v-model.number="pageSize" @change="changePageSize">
        <option :value="20">{{ $t('common.pageSize', { size: 20 }) }}</option>
        <option :value="50">{{ $t('common.pageSize', { size: 50 }) }}</option>
        <option :value="100">{{ $t('common.pageSize', { size: 100 }) }}</option>
      </select>
      <button type="button" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">{{ $t('common.previous') }}</button>
      <strong>{{ currentPage }}</strong>
      <button type="button" :disabled="!hasNextPage" @click="changePage(currentPage + 1)">{{ $t('common.next') }}</button>
    </footer>

    <div v-if="drawerOpen" class="drawer-mask" @click="closeDrawer"></div>
    <aside :class="['file-drawer', { open: drawerOpen }]">
      <header class="drawer-header">
        <div>
          <h2>{{ drawerTitle }}</h2>
          <p>{{ $t('page.dataOverview.datafileEntry') }}</p>
        </div>
        <button type="button" @click="closeDrawer">×</button>
      </header>

      <section class="relation-overview">
        <p class="section-kicker">{{ $t('page.dataOverview.relationship') }}</p>
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
              <th>{{ $t('common.fileName') }}</th>
              <th>{{ $t('common.fileRole') }}</th>
              <th>{{ $t('page.accessionDetail.columns.type') }}</th>
              <th>{{ $t('page.accessionDetail.columns.size') }}</th>
              <th>{{ $t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in drawerPayload.files" :key="file.file_id">
              <td>{{ file.file_name }}</td>
              <td>{{ fileRoleLabel(file.file_role, file.file_role_display) }}</td>
              <td>{{ file.file_type || '-' }}</td>
              <td>{{ file.file_size_display || '-' }}</td>
              <td><a class="download-link" :href="file.download_url">{{ $t('common.download') }}</a></td>
            </tr>
            <tr v-if="!drawerPayload.files?.length">
              <td class="empty-table" colspan="5">{{ $t('page.dataOverview.noFiles') }}</td>
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
import { useI18n } from 'vue-i18n'

const DEFAULT_CATEGORIES = [
  { key: 'raw_data' },
  { key: 'genome' },
  { key: 'annotation' },
  { key: 'transcriptome' },
  { key: 'population' },
  { key: 'codon' },
  { key: 'centromere' },
  { key: 'tes' },
  { key: 'coreblocks' },
  { key: 'ncrna' }
]

export default {
  name: 'DataOverviewView',
  setup() {
    const { locale, t, te } = useI18n()
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
    const drawerCategory = ref('')

    const categoryLabel = (category) => {
      const key = category?.key || category
      const path = `page.dataOverview.categories.${key}`
      if (te(path)) return t(path)
      if (typeof category === 'object') {
        return locale.value === 'en' ? category.en_label || category.label || key : category.label || category.en_label || key
      }
      return key || '-'
    }

    const fileRoleLabel = (role, fallback = '') => {
      const path = `page.rawData.fileRoles.${role}`
      if (te(path)) return t(path)
      return locale.value === 'en' ? role : fallback || role
    }

    const dataCategories = computed(() => {
      const categories = filters.value.data_categories?.length ? filters.value.data_categories : DEFAULT_CATEGORIES
      const visibleCategories = selectedCategory.value
        ? categories.filter(category => category.key === selectedCategory.value)
        : categories
      return visibleCategories.map(category => ({ ...category, label: categoryLabel(category) }))
    })

    const summaryCards = computed(() => [
      { key: 'accession', label: t('page.dataOverview.summary.accessions'), value: summary.value.accession_count || 0, icon: '◉', theme: 'green' },
      { key: 'dataset', label: t('page.dataOverview.summary.datasets'), value: summary.value.dataset_count || 0, icon: '▰', theme: 'purple' },
      { key: 'datafile', label: t('page.dataOverview.summary.files'), value: summary.value.datafile_count || 0, icon: '▤', theme: 'blue' },
      { key: 'total_size', label: t('page.dataOverview.summary.totalSize'), value: summary.value.total_size_display || '-', icon: 'Σ', theme: 'orange' },
      { key: 'geo', label: t('page.dataOverview.summary.locations'), value: summary.value.geo_location_count || 0, unit: t('page.dataOverview.summary.locationUnit'), icon: '⌖', theme: 'cyan' },
      { key: 'updated', label: t('page.dataOverview.summary.updatedAt'), value: summary.value.latest_update || '-', icon: '◷', theme: 'pink' }
    ])

    const drawerTitle = computed(() => {
      const accession = drawerPayload.value.relation_overview?.accession
      return [accession, categoryLabel(drawerCategory.value), t('page.dataOverview.fileList')].filter(Boolean).join(' / ')
    })

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
        ElMessage.error(t('messages.dataOverviewLoadFailed'))
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
      drawerCategory.value = category
      try {
        const response = await axios.get('/files/query/data-overview-files/', { params: { accession, category } })
        drawerPayload.value = response.data || { files: [], relation_overview: {} }
        drawerOpen.value = true
      } catch (error) {
        console.error('获取文件列表失败:', error)
        ElMessage.error(t('messages.getFileListFailed'))
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
      categoryLabel,
      fileRoleLabel,
      matrixRows,
      detailRows,
      drawerOpen,
      drawerPayload,
      drawerTitle,
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

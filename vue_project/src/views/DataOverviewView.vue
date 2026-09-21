<template>
  <main class="data-overview-page">
    <header class="page-heading">
      <p>{{ $t('page.dataOverview.breadcrumb') }}</p>
      <h1>{{ $t('page.dataOverview.title') }}</h1>
      <span>{{ $t('page.dataOverview.subtitle') }}</span>
    </header>

    <section class="filter-panel" :aria-label="$t('page.dataOverview.filters.label')">
      <div class="search-control">
        <el-input v-model="draft.search" clearable :aria-label="$t('page.dataOverview.searchPrompt')" :placeholder="$t('page.dataOverview.searchPrompt')" @keyup.enter="applyFilters">
          <template #prefix><el-icon aria-hidden="true"><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="applyFilters">{{ $t('common.search') }}</el-button>
      </div>
      <label class="filter-field"><span>{{ $t('page.dataOverview.filters.dataType') }}</span><el-select v-model="draft.category" :aria-label="$t('page.dataOverview.filters.dataType')" clearable><el-option :label="$t('common.all')" value="" /><el-option v-for="item in categories" :key="item.key" :label="categoryLabel(item)" :value="item.key" /></el-select></label>
      <label class="filter-field"><span>{{ $t('page.dataOverview.filters.species') }}</span><el-select v-model="draft.species" :aria-label="$t('page.dataOverview.filters.species')" clearable filterable><el-option :label="$t('common.all')" value="" /><el-option v-for="item in filters.species" :key="item.key" :label="speciesOptionLabel(item)" :value="item.key" /></el-select></label>
      <label class="filter-field"><span>{{ $t('page.dataOverview.accession') }}</span><el-select v-model="draft.accession" :aria-label="$t('page.dataOverview.accession')" clearable filterable><el-option :label="$t('common.all')" value="" /><el-option v-for="item in filters.accessions" :key="item.key" :label="item.label" :value="item.key" /></el-select></label>
      <label class="filter-field"><span>{{ $t('page.dataOverview.columns.dataset') }}</span><el-select v-model="draft.dataset" :aria-label="$t('page.dataOverview.columns.dataset')" clearable filterable><el-option :label="$t('common.all')" value="" /><el-option v-for="item in filters.datasets" :key="item.key" :label="item.label" :value="item.key" /></el-select></label>
      <el-button class="reset-button" @click="resetFilters"><el-icon><RefreshLeft /></el-icon>{{ $t('common.reset') }}</el-button>
    </section>

    <DataOverviewStats :summary="summary" />

    <section class="file-table-card">
      <header class="table-heading">
        <h2>{{ $t('page.dataOverview.fileTable') }} <small>({{ $t('common.totalCount', { count: totalCount }) }})</small></h2>
        <div class="table-tools">
          <span>{{ $t('page.dataOverview.optionalColumns') }}</span>
          <DataOverviewColumnSettings v-model="selectedColumns" :columns="columnOptions" />
        </div>
      </header>

      <el-alert v-if="loadError" :title="$t('messages.dataOverviewLoadFailed')" type="error" show-icon :closable="false">
        <template #default><el-button size="small" @click="fetchOverview">{{ $t('common.retry') }}</el-button></template>
      </el-alert>

      <div v-loading="loading" class="table-scroll" :aria-busy="loading" aria-live="polite">
        <table class="file-table">
          <caption class="sr-only">{{ $t('page.dataOverview.fileTable') }}</caption>
          <thead><tr><th v-for="column in visibleColumns" :key="column.key">{{ column.label }}</th><th>{{ $t('common.actions') }}</th></tr></thead>
          <tbody>
            <tr v-for="row in rows" :key="row.file_id">
              <td v-for="column in visibleColumns" :key="column.key" :class="`cell-${column.key}`">
                <span v-if="column.key === 'category'" :class="['category-tag', `category-${row.category}`]">{{ categoryLabel(row.category) }}</span>
                <span v-else-if="column.key === 'file_name'" class="file-name" :title="row.file_name">{{ row.file_name || '-' }}</span>
                <em v-else-if="column.key === 'species_name'">{{ row.species_name || '-' }}</em>
                <router-link v-else-if="column.key === 'accession' && row.accession && row.accession !== 'Multiple'" class="accession-link" :to="{ path: '/accession-card', query: { accession: row.accession } }">{{ row.accession }}</router-link>
                <span v-else-if="column.key === 'description'" class="truncate" :title="row.description">{{ row.description || '-' }}</span>
                <code v-else-if="column.key === 'md5'" class="truncate" :title="row.md5">{{ row.md5 || '-' }}</code>
                <span v-else>{{ row[column.key] || '-' }}</span>
              </td>
              <td class="actions-cell"><button type="button" :aria-label="$t('page.dataOverview.detail.openFor', { file: row.file_name })" @click="openDetail(row.file_id)">{{ $t('common.details') }}</button><span aria-hidden="true">|</span><a :href="row.download_url" :aria-label="$t('page.dataOverview.detail.downloadFor', { file: row.file_name })">{{ $t('common.download') }}</a></td>
            </tr>
            <tr v-if="!loading && !rows.length"><td :colspan="visibleColumns.length + 1" class="empty-cell">{{ $t('page.dataOverview.noMatches') }}</td></tr>
          </tbody>
        </table>
      </div>

      <footer class="pagination-bar">
        <span>{{ $t('common.totalCount', { count: totalCount }) }}</span>
        <div>
          <span>{{ $t('page.dataOverview.itemsPerPage') }}</span>
          <el-select v-model="pageSize" class="page-size" @change="changePageSize"><el-option :value="20" label="20" /><el-option :value="50" label="50" /><el-option :value="100" label="100" /></el-select>
          <el-button :disabled="currentPage <= 1" :aria-label="$t('common.previous')" @click="changePage(currentPage - 1)"><el-icon><ArrowLeft /></el-icon></el-button>
          <strong>{{ currentPage }}</strong>
          <el-button :disabled="currentPage >= pageCount" :aria-label="$t('common.next')" @click="changePage(currentPage + 1)"><el-icon><ArrowRight /></el-icon></el-button>
        </div>
      </footer>
    </section>

    <DataFileDetailDrawer :model-value="drawerOpen" :loading="detailLoading" :error="detailError" :detail="detail" :category-label="categoryLabel" @close="closeDetail" @retry="loadDetail" />
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, RefreshLeft, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import DataFileDetailDrawer from '@/components/data-overview/DataFileDetailDrawer.vue'
import DataOverviewColumnSettings from '@/components/data-overview/DataOverviewColumnSettings.vue'
import DataOverviewStats from '@/components/data-overview/DataOverviewStats.vue'
import { fetchDataFileDetail, fetchDataOverview } from '@/services/dataOverview'

const STORAGE_KEY = 'genedata:data-overview-columns:v1'
const DEFAULT_COLUMNS = ['category', 'file_name', 'species_name', 'accession', 'file_type', 'file_size_display']
const OPTIONAL_COLUMNS = ['dataset_name', 'data_source', 'md5', 'description']

const { locale, t, te } = useI18n()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const loadError = ref(false)
const rows = ref([])
const summary = ref({})
const filters = ref({ data_categories: [], species: [], accessions: [], datasets: [] })
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const drawerOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref(false)
const detail = ref(null)
const detailFileId = ref(null)
const draft = reactive({ search: '', category: '', species: '', accession: '', dataset: '' })
const applied = reactive({ search: '', category: '', species: '', accession: '', dataset: '' })
let overviewController = null
let detailController = null
let overviewRequestId = 0
let detailRequestId = 0

const loadStoredColumns = () => {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY))
    return Array.isArray(stored) ? [...new Set([...DEFAULT_COLUMNS, ...stored.filter(key => OPTIONAL_COLUMNS.includes(key))])] : DEFAULT_COLUMNS
  } catch (_) { return DEFAULT_COLUMNS }
}
const selectedColumns = ref(loadStoredColumns())
watch(selectedColumns, value => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(value)) } catch (_) { /* preference storage is optional */ }
}, { deep: true })

const categoryLabel = category => {
  const key = category?.key || category
  const path = `page.dataOverview.categories.${key}`
  if (te(path)) return t(path)
  if (typeof category === 'object') return locale.value === 'en' ? category.en_label || category.label : category.label || category.en_label
  return key || '-'
}
const speciesOptionLabel = item => item.latin_name && item.latin_name !== item.label ? `${item.label} (${item.latin_name})` : item.label
const categories = computed(() => filters.value.data_categories || [])
const columnOptions = computed(() => [
  { key: 'category', label: t('common.dataType'), required: true },
  { key: 'file_name', label: t('common.fileName'), required: true },
  { key: 'species_name', label: t('common.species'), required: true },
  { key: 'accession', label: t('page.dataOverview.accession'), required: true },
  { key: 'file_type', label: t('common.fileType'), required: true },
  { key: 'file_size_display', label: t('common.fileSize'), required: true },
  { key: 'dataset_name', label: t('page.dataOverview.columns.dataset') },
  { key: 'data_source', label: t('page.dataOverview.columns.dataSource') },
  { key: 'md5', label: 'MD5' },
  { key: 'description', label: t('page.dataOverview.columns.description') }
])
const visibleColumns = computed(() => columnOptions.value.filter(column => selectedColumns.value.includes(column.key)))
const pageCount = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))

const requestParams = () => ({
  page: currentPage.value,
  page_size: pageSize.value,
  ...Object.fromEntries(Object.entries(applied).filter(([, value]) => value))
})
const queryValue = value => Array.isArray(value) ? value[0] : value
const positiveInteger = (value, fallback) => {
  const parsed = Number.parseInt(queryValue(value), 10)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}
const routeQuery = () => {
  const query = Object.fromEntries(Object.entries(applied).filter(([, value]) => value))
  if (currentPage.value > 1) query.page = String(currentPage.value)
  if (pageSize.value !== 20) query.page_size = String(pageSize.value)
  return query
}
const sameQuery = (left, right) => {
  const normalize = query => Object.fromEntries(Object.entries(query).map(([key, value]) => [key, String(queryValue(value) ?? '')]).filter(([, value]) => value))
  return JSON.stringify(Object.entries(normalize(left)).sort()) === JSON.stringify(Object.entries(normalize(right)).sort())
}
const navigateToState = async (replace = false) => {
  const query = routeQuery()
  if (sameQuery(route.query, query)) return fetchOverview()
  await router[replace ? 'replace' : 'push']({ path: route.path, query })
}
const fetchOverview = async () => {
  overviewController?.abort()
  overviewController = new AbortController()
  const requestId = ++overviewRequestId
  loading.value = true
  loadError.value = false
  try {
    const { data } = await fetchDataOverview(requestParams(), { signal: overviewController.signal })
    if (requestId !== overviewRequestId) return
    rows.value = data.results || []
    summary.value = data.summary || {}
    filters.value = data.filters || filters.value
    totalCount.value = data.count || 0
    const lastPage = Math.max(1, Math.ceil(totalCount.value / pageSize.value))
    if (currentPage.value > lastPage) {
      currentPage.value = lastPage
      await navigateToState(true)
    }
  } catch (error) {
    if (error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError') return
    if (requestId !== overviewRequestId) return
    loadError.value = true
    console.error('Failed to load Data Overview:', error)
    ElMessage.error(t('messages.dataOverviewLoadFailed'))
  } finally { if (requestId === overviewRequestId) loading.value = false }
}
const applyFilters = () => {
  Object.assign(applied, Object.fromEntries(Object.entries(draft).map(([key, value]) => [key, String(value || '').trim()])))
  currentPage.value = 1
  navigateToState()
}
const resetFilters = () => {
  Object.keys(draft).forEach(key => { draft[key] = ''; applied[key] = '' })
  currentPage.value = 1
  navigateToState()
}
const changePage = page => { currentPage.value = page; navigateToState() }
const changePageSize = () => { currentPage.value = 1; navigateToState() }
const openDetail = async fileId => {
  detailFileId.value = fileId
  drawerOpen.value = true
  loadDetail()
}
const loadDetail = async () => {
  if (!detailFileId.value) return
  detailController?.abort()
  detailController = new AbortController()
  const requestId = ++detailRequestId
  detailLoading.value = true
  detailError.value = false
  detail.value = null
  try {
    const response = await fetchDataFileDetail(detailFileId.value, { signal: detailController.signal })
    if (requestId === detailRequestId) detail.value = response.data
  } catch (error) {
    if (error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError') return
    if (requestId !== detailRequestId) return
    detailError.value = true
    console.error('Failed to load DataFile detail:', error)
    ElMessage.error(t('page.dataOverview.detail.loadFailed'))
  } finally { if (requestId === detailRequestId) detailLoading.value = false }
}
const closeDetail = () => {
  detailController?.abort()
  detailRequestId += 1
  detailLoading.value = false
  drawerOpen.value = false
}

watch(() => route.query, async query => {
  for (const key of Object.keys(applied)) {
    const value = String(queryValue(query[key]) || '').trim()
    draft[key] = value
    applied[key] = value
  }
  currentPage.value = positiveInteger(query.page, 1)
  const requestedPageSize = positiveInteger(query.page_size, 20)
  pageSize.value = [20, 50, 100].includes(requestedPageSize) ? requestedPageSize : 20
  if (!sameQuery(query, routeQuery())) {
    await router.replace({ path: route.path, query: routeQuery() })
    return
  }
  fetchOverview()
}, { immediate: true })

onBeforeUnmount(() => {
  overviewController?.abort()
  detailController?.abort()
  overviewRequestId += 1
  detailRequestId += 1
})
</script>

<style scoped>
.data-overview-page{min-height:calc(100vh - 72px);padding:24px clamp(18px,5.8vw,116px) 44px;background:linear-gradient(120deg,#f5faff 0%,#edf5ff 52%,#f8fbff 100%);color:#102c55}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.page-heading{margin-bottom:18px}.page-heading p{margin:0 0 9px;color:#486b98;font-size:14px}.page-heading h1{margin:0;color:#082f70;font-size:32px;line-height:1.15}.page-heading span{display:block;margin-top:8px;color:#567292;font-size:14px}.filter-panel{display:grid;grid-template-columns:minmax(330px,1.7fr) repeat(4,minmax(142px,.65fr)) 94px;gap:12px;align-items:end;padding:18px;border:1px solid #d9e6f5;border-radius:15px;background:#fff;box-shadow:0 10px 30px rgba(35,83,139,.06)}.search-control{display:grid;grid-template-columns:minmax(0,1fr) 106px}.search-control :deep(.el-input__wrapper){height:44px;border-radius:8px 0 0 8px;box-shadow:0 0 0 1px #cbdcf1 inset}.search-control>.el-button{height:44px;border-radius:0 8px 8px 0;background:linear-gradient(135deg,#3098f5,#0871e7);font-weight:700}.filter-field{min-width:0}.filter-field>span{display:block;margin-bottom:6px;color:#173b6a;font-size:12px;font-weight:700}.filter-field :deep(.el-select){width:100%}.filter-field :deep(.el-select__wrapper){min-height:44px}.reset-button{height:44px}.file-table-card{overflow:hidden;border:1px solid #d8e5f4;border-radius:14px;background:#fff;box-shadow:0 10px 30px rgba(35,83,139,.07)}.table-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:14px 18px}.table-heading h2{margin:0;color:#123a72;font-size:17px}.table-heading h2 small{font-size:13px;font-weight:500}.table-tools{display:flex;align-items:center;gap:14px;color:#587398;font-size:12px}.table-scroll{min-height:260px;overflow:auto;padding:0 16px}.file-table{width:100%;min-width:980px;border-collapse:collapse;border:1px solid #dae6f3}.file-table th,.file-table td{padding:11px 13px;border-right:1px solid #e1eaf4;border-bottom:1px solid #e1eaf4;text-align:left;font-size:13px}.file-table th{background:#edf5ff;color:#163c72;font-weight:800;white-space:nowrap}.file-table tbody tr:hover{background:#f8fbff}.file-name,.truncate{display:block;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.file-name{color:#173b70;font-weight:600}.cell-species_name em{color:#385c88}.accession-link,.actions-cell a,.actions-cell button{color:#0874e8;font-weight:700;text-decoration:none}.actions-cell{white-space:nowrap}.actions-cell button{padding:0;border:0;background:transparent;cursor:pointer}.actions-cell span{margin:0 10px;color:#aac0dc}.category-tag{display:inline-flex;padding:3px 9px;border-radius:6px;background:#e4f1ff;color:#0874e8;font-weight:700;white-space:nowrap}.category-annotation{background:#e8f8ee;color:#15935a}.category-raw_data{background:#fff0df;color:#d56d0b}.category-transcriptome{background:#f0eaff;color:#7546d8}.category-population{background:#ffe9ed;color:#d43d5b}.empty-cell{height:180px!important;text-align:center!important;color:#7a8da8}.pagination-bar{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;color:#58708e;font-size:13px}.pagination-bar>div{display:flex;align-items:center;gap:9px}.page-size{width:78px}.pagination-bar strong{display:grid;place-items:center;width:34px;height:34px;border-radius:7px;background:#1279ed;color:#fff}.file-table code{color:#536a87;font-size:12px}@media(max-width:1280px){.filter-panel{grid-template-columns:repeat(3,minmax(0,1fr))}.search-control{grid-column:span 2}.reset-button{width:100%}}@media(max-width:760px){.data-overview-page{padding:18px 12px 32px}.page-heading h1{font-size:27px}.filter-panel{grid-template-columns:1fr}.search-control{grid-column:auto}.table-heading,.pagination-bar{align-items:flex-start;flex-direction:column}.table-tools{width:100%;justify-content:space-between}}
</style>

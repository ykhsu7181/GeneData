<template>
  <main class="public-files-page">
    <header class="page-heading">
      <nav class="breadcrumb" :aria-label="labels.breadcrumb">
        <RouterLink to="/dashboard">{{ labels.home }}</RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ labels.title }}</span>
      </nav>
      <div class="heading-row">
        <div>
          <h1>{{ labels.title }}</h1>
          <p>{{ labels.intro }}</p>
        </div>
        <a class="manifest-button" :href="filteredManifestUrl">
          <el-icon><Download /></el-icon>{{ labels.manifest }}
        </a>
      </div>
    </header>

    <section class="filter-panel" :aria-label="labels.filters">
      <el-input v-model="draft.name_contains" clearable :placeholder="labels.fileName" @keyup.enter="applyFilters">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-input v-model="draft.accession" clearable placeholder="Accession" @keyup.enter="applyFilters" />
      <el-input v-model="draft.assembly" clearable placeholder="Assembly" @keyup.enter="applyFilters" />
      <el-input v-model="draft.role" clearable :placeholder="labels.role" @keyup.enter="applyFilters" />
      <el-input v-model="draft.format" clearable :placeholder="labels.format" @keyup.enter="applyFilters" />
      <el-input v-model="draft.dataset" clearable placeholder="Dataset" @keyup.enter="applyFilters" />
      <el-button type="primary" @click="applyFilters"><el-icon><Search /></el-icon>{{ labels.search }}</el-button>
      <el-button @click="resetFilters"><el-icon><RefreshLeft /></el-icon>{{ labels.reset }}</el-button>
    </section>

    <el-alert class="download-note" type="info" :title="labels.downloadNote" show-icon :closable="false" />

    <section class="catalog-card">
      <header class="catalog-heading">
        <div>
          <h2>{{ labels.list }} <small>{{ totalCount }} {{ labels.items }}</small></h2>
          <p v-if="selectedRows.length" class="selection-summary">
            {{ labels.selected.replace('{count}', selectedDownloadCount).replace('{size}', formatBytes(selectedSize)) }}
          </p>
        </div>
        <div class="batch-actions">
          <el-checkbox v-model="includeCompanions" :disabled="!selectedRows.length">{{ labels.includeIndexes }}</el-checkbox>
          <el-button :disabled="!selectedRows.length" @click="clearSelection">{{ labels.clearSelection }}</el-button>
          <el-button :disabled="!selectedRows.length" @click="openBatchApiScript">
            {{ labels.streamFiles }}
          </el-button>
          <el-button type="primary" :disabled="!selectedRows.length" @click="openCacheScript">
            {{ labels.getFiles }}
          </el-button>
        </div>
      </header>

      <el-alert v-if="loadError" :title="labels.loadFailed" type="error" show-icon :closable="false">
        <template #default><el-button size="small" @click="loadFiles">{{ labels.retry }}</el-button></template>
      </el-alert>

      <el-table
        ref="catalogTable"
        v-loading="loading"
        :data="rows"
        border
        stripe
        row-key="file_code"
        class="catalog-table"
        :empty-text="labels.empty"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" fixed="left" reserve-selection />
        <el-table-column prop="file_code" :label="labels.fileCode" width="132" fixed="left" />
        <el-table-column prop="file_name" :label="labels.fileName" min-width="270" show-overflow-tooltip />
        <el-table-column prop="accession" label="Accession" width="135">
          <template #default="{ row }">{{ displayValues(row.accessions, row.accession) }}</template>
        </el-table-column>
        <el-table-column prop="assembly" label="Assembly" width="165">
          <template #default="{ row }">{{ displayValues(row.assemblies, row.assembly) }}</template>
        </el-table-column>
        <el-table-column prop="role" :label="labels.role" width="155" show-overflow-tooltip />
        <el-table-column prop="format" :label="labels.format" width="100" />
        <el-table-column prop="size" :label="labels.size" width="120">
          <template #default="{ row }">{{ formatBytes(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="sha256" label="SHA-256" min-width="210">
          <template #default="{ row }">
            <button class="checksum-button" type="button" :title="row.sha256" @click="copyText(row.sha256, 'SHA-256')">
              {{ shortChecksum(row.sha256) }}
            </button>
          </template>
        </el-table-column>
        <el-table-column :label="labels.actions" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.file_code)">{{ labels.details }}</el-button>
            <el-button link type="primary" @click="copyDownloadCommand(row)">{{ labels.copyCommand }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <footer class="pagination-bar">
        <span>{{ totalCount }} {{ labels.items }}</span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="totalCount"
          layout="sizes, prev, pager, next"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </footer>
    </section>

    <el-drawer v-model="drawerOpen" :title="labels.details" size="min(620px, 94vw)">
      <div v-loading="detailLoading" class="detail-content">
        <el-alert v-if="detailError" :title="labels.loadFailed" type="error" show-icon />
        <dl v-else-if="detail" class="detail-grid">
          <div><dt>{{ labels.fileCode }}</dt><dd>{{ detail.file_code }}</dd></div>
          <div><dt>{{ labels.fileName }}</dt><dd>{{ detail.file_name }}</dd></div>
          <div><dt>{{ labels.role }}</dt><dd>{{ detail.role || '-' }}</dd></div>
          <div><dt>{{ labels.format }}</dt><dd>{{ detail.format || '-' }}</dd></div>
          <div><dt>{{ labels.size }}</dt><dd>{{ formatBytes(detail.size) }}</dd></div>
          <div><dt>Dataset</dt><dd>{{ detail.dataset || '-' }}</dd></div>
          <div class="wide"><dt>SHA-256</dt><dd class="checksum">{{ detail.sha256 }}</dd></div>
          <div class="wide"><dt>Content Version</dt><dd>{{ detail.content_version || '-' }}</dd></div>
          <div class="wide"><dt>{{ labels.apiUrl }}</dt><dd>{{ absoluteUrl(`/gd/api/v1/files/${detail.file_code}/`) }}</dd></div>
        </dl>
        <footer v-if="detail" class="drawer-actions">
          <el-button @click="copyText(detail.sha256, 'SHA-256')">{{ labels.copySha }}</el-button>
          <el-button type="primary" @click="copyDownloadCommand(detail)">{{ labels.copyCommand }}</el-button>
        </footer>
      </div>
    </el-drawer>

    <el-dialog v-model="batchDialogOpen" :title="scriptDialogTitle" width="min(860px, 94vw)">
      <el-alert :title="scriptDialogIntro" type="info" show-icon :closable="false" />
      <p class="batch-dialog-summary">
        {{ scriptDialogSummary.replace('{count}', selectedDownloadCount) }}
      </p>
      <el-input v-model="batchScript" type="textarea" :rows="18" readonly class="batch-script" />
      <template #footer>
        <el-button @click="batchDialogOpen = false">{{ labels.close }}</el-button>
        <el-button type="primary" @click="copyText(batchScript, labels.copyScript)">{{ labels.copyScript }}</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Download, RefreshLeft, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { fetchPublicFileDetail, fetchPublicFiles, publicFileManifestUrl } from '@/services/publicFileCatalog'
import {
  buildFilteredManifestUrl,
  buildPublicFileBatchScript,
  buildPublicFileCacheScript,
  expandDownloadFiles,
} from '@/utils/publicFileBatch.mjs'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const labels = computed(() => Object.fromEntries([
  'title', 'intro', 'breadcrumb', 'manifest', 'filters', 'fileName', 'role', 'format',
  'size', 'list', 'items', 'downloadNote', 'fileCode', 'copyCommand', 'empty',
  'loadFailed', 'copySha', 'apiUrl', 'copied', 'copyFailed', 'selected',
  'includeIndexes', 'clearSelection', 'getFiles', 'streamFiles',
  'cacheTitle', 'cacheIntro', 'downloadFiles', 'batchTitle', 'batchIntro',
  'batchFiles', 'copyScript', 'generationFailed'
].map(key => [key, t(`page.publicFileCatalog.${key}`)]).concat([
  ['home', t('nav.home')], ['search', t('common.search')], ['reset', t('common.reset')],
  ['actions', t('common.actions')], ['details', t('common.details')], ['retry', t('common.retry')],
  ['close', t('common.close')]
])))

const filterKeys = ['name_contains', 'accession', 'assembly', 'role', 'format', 'dataset']
const draft = reactive(Object.fromEntries(filterKeys.map(key => [key, ''])))
const applied = reactive(Object.fromEntries(filterKeys.map(key => [key, ''])))
const rows = ref([])
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const loadError = ref(false)
const drawerOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref(false)
const detail = ref(null)
const catalogTable = ref(null)
const selectedRows = ref([])
const includeCompanions = ref(true)
const batchDialogOpen = ref(false)
const batchScript = ref('')
const scriptMode = ref('cache')
let listController = null
let detailController = null

const filteredManifestUrl = computed(() => buildFilteredManifestUrl(
  publicFileManifestUrl,
  Object.fromEntries(filterKeys.map(key => [key, applied[key]])),
  window.location.origin,
))
const selectedFiles = computed(() => expandDownloadFiles(selectedRows.value, {
  includeCompanions: includeCompanions.value,
}))
const selectedDownloadCount = computed(() => selectedFiles.value.length)
const selectedSize = computed(() => selectedFiles.value.reduce((total, item) => total + item.size, 0))
const scriptDialogLabels = computed(() => ({
  cache: { title: labels.value.cacheTitle, intro: labels.value.cacheIntro, summary: labels.value.downloadFiles },
  batch: { title: labels.value.batchTitle, intro: labels.value.batchIntro, summary: labels.value.batchFiles },
})[scriptMode.value])
const scriptDialogTitle = computed(() => scriptDialogLabels.value.title)
const scriptDialogIntro = computed(() => scriptDialogLabels.value.intro)
const scriptDialogSummary = computed(() => scriptDialogLabels.value.summary)

const queryValue = value => Array.isArray(value) ? value[0] : value
const routeQuery = () => {
  const query = Object.fromEntries(filterKeys.map(key => [key, applied[key]]).filter(([, value]) => value))
  if (currentPage.value > 1) query.page = String(currentPage.value)
  if (pageSize.value !== 20) query.page_size = String(pageSize.value)
  return query
}
const normalizeQuery = query => Object.entries(query).map(([key, value]) => [key, String(queryValue(value) || '')]).filter(([, value]) => value).sort()
const sameQuery = (left, right) => JSON.stringify(normalizeQuery(left)) === JSON.stringify(normalizeQuery(right))
const navigate = async () => {
  const query = routeQuery()
  if (sameQuery(route.query, query)) return loadFiles()
  await router.push({ path: route.path, query })
}
const requestParams = () => ({
  page: currentPage.value,
  page_size: pageSize.value,
  ...Object.fromEntries(filterKeys.map(key => [key, applied[key]]).filter(([, value]) => value))
})
const loadFiles = async () => {
  listController?.abort()
  listController = new AbortController()
  loading.value = true
  loadError.value = false
  try {
    const { data } = await fetchPublicFiles(requestParams(), { signal: listController.signal })
    rows.value = data.results || []
    totalCount.value = data.count || 0
  } catch (error) {
    if (error?.code !== 'ERR_CANCELED' && error?.name !== 'CanceledError') loadError.value = true
  } finally {
    loading.value = false
  }
}
const applyFilters = () => {
  filterKeys.forEach(key => { applied[key] = String(draft[key] || '').trim() })
  currentPage.value = 1
  navigate()
}
const resetFilters = () => {
  filterKeys.forEach(key => { draft[key] = ''; applied[key] = '' })
  currentPage.value = 1
  navigate()
}
const changePage = () => navigate()
const changePageSize = () => { currentPage.value = 1; navigate() }
const handleSelectionChange = selection => { selectedRows.value = selection }
const clearSelection = () => {
  catalogTable.value?.clearSelection()
  selectedRows.value = []
}
const openScriptDialog = (mode, builder) => {
  try {
    batchScript.value = builder(selectedRows.value, {
      baseUrl: window.location.origin,
      includeCompanions: includeCompanions.value,
    })
  } catch (_) {
    ElMessage.error(labels.value.generationFailed)
    return
  }
  if (!batchScript.value) return
  scriptMode.value = mode
  batchDialogOpen.value = true
}
const openCacheScript = () => openScriptDialog('cache', buildPublicFileCacheScript)
const openBatchApiScript = () => openScriptDialog('batch', buildPublicFileBatchScript)
const openDetail = async fileCode => {
  detailController?.abort()
  detailController = new AbortController()
  drawerOpen.value = true
  detailLoading.value = true
  detailError.value = false
  detail.value = null
  try {
    const response = await fetchPublicFileDetail(fileCode, { signal: detailController.signal })
    detail.value = response.data
  } catch (error) {
    if (error?.code !== 'ERR_CANCELED' && error?.name !== 'CanceledError') detailError.value = true
  } finally {
    detailLoading.value = false
  }
}
const absoluteUrl = path => new URL(path, window.location.origin).toString()
const copyText = async (value, name) => {
  if (!value) return
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success(`${name}: ${labels.value.copied}`)
  } catch (_) {
    ElMessage.error(labels.value.copyFailed)
  }
}
const copyDownloadCommand = row => {
  const contentUrl = row.content_url || `/gd/api/v1/files/${row.file_code}/content/`
  copyText(`curl -fL -OJ -H "Authorization: Bearer $GENEDATA_TOKEN" "${absoluteUrl(contentUrl)}"`, labels.value.copyCommand)
}
const displayValues = (values, fallback) => values?.length ? values.join(', ') : fallback || '-'
const shortChecksum = value => value ? `${value.slice(0, 12)}…${value.slice(-8)}` : '-'
const formatBytes = value => {
  const size = Number(value)
  if (!Number.isFinite(size)) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let amount = size
  let unit = 0
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit += 1 }
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

watch(() => route.query, query => {
  filterKeys.forEach(key => {
    const value = String(queryValue(query[key]) || '').trim()
    draft[key] = value
    applied[key] = value
  })
  currentPage.value = Math.max(1, Number.parseInt(queryValue(query.page), 10) || 1)
  const requestedSize = Number.parseInt(queryValue(query.page_size), 10) || 20
  pageSize.value = [20, 50, 100].includes(requestedSize) ? requestedSize : 20
  loadFiles()
}, { immediate: true })

onBeforeUnmount(() => {
  listController?.abort()
  detailController?.abort()
})
</script>

<style scoped>
.public-files-page{min-height:calc(100vh - 160px);color:#102c55}.breadcrumb{display:flex;gap:8px;align-items:center;margin-bottom:8px;color:#4b6693;font-size:13px}.breadcrumb a{color:#31558f;text-decoration:none}.heading-row{display:flex;align-items:flex-start;justify-content:space-between;gap:24px}.page-heading h1{margin:0;color:#0a2b73;font-size:30px}.page-heading p{margin:8px 0 0;color:#607896}.manifest-button{display:inline-flex;align-items:center;gap:7px;padding:11px 16px;border-radius:9px;background:#0874e8;color:#fff;font-weight:700;text-decoration:none;white-space:nowrap}.filter-panel{display:grid;grid-template-columns:2fr repeat(5,minmax(125px,1fr)) auto auto;gap:10px;margin:18px 0;padding:16px;border:1px solid #d9e6f5;border-radius:14px;background:#fff}.download-note{margin-bottom:16px}.catalog-card{overflow:hidden;border:1px solid #d8e5f4;border-radius:14px;background:#fff;box-shadow:0 10px 30px rgba(35,83,139,.07)}.catalog-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 18px}.catalog-heading h2{margin:0;color:#123a72;font-size:18px}.catalog-heading small{margin-left:8px;color:#647996;font-size:13px;font-weight:500}.selection-summary{margin:5px 0 0;color:#516b8d;font-size:13px}.batch-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.catalog-table{width:100%}.checksum-button{padding:0;border:0;background:transparent;color:#315b91;font-family:monospace;cursor:pointer}.pagination-bar{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;color:#58708e}.detail-content{min-height:220px}.detail-grid{display:grid;grid-template-columns:1fr 1fr;margin:0;border:1px solid #e1e9f4;border-radius:10px;overflow:hidden}.detail-grid>div{display:grid;grid-template-columns:110px 1fr;min-height:46px;padding:0 12px;align-items:center;border-right:1px solid #e7edf5;border-bottom:1px solid #e7edf5}.detail-grid .wide{grid-column:1/-1}.detail-grid dt{color:#6b7c95;font-size:12px}.detail-grid dd{min-width:0;margin:0;overflow-wrap:anywhere}.checksum{font-family:monospace}.drawer-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.batch-dialog-summary{margin:14px 0 8px;color:#425f83}.batch-script :deep(textarea){font-family:Consolas,"Liberation Mono",monospace;font-size:12px;line-height:1.55}@media(max-width:1400px){.filter-panel{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:760px){.heading-row,.catalog-heading,.pagination-bar{align-items:stretch;flex-direction:column}.batch-actions{align-items:stretch}.manifest-button{justify-content:center}.filter-panel{grid-template-columns:1fr}.detail-grid{grid-template-columns:1fr}.detail-grid .wide{grid-column:auto}}
</style>

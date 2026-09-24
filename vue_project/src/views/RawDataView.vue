<template>
  <div class="raw-data-page">
    <header class="raw-header">
      <div>
        <p class="breadcrumb">{{ $t('page.rawData.breadcrumb') }}</p>
        <h1>{{ $t('page.rawData.title') }}</h1>
        <p class="subtitle">{{ $t('page.rawData.subtitle') }}</p>
      </div>
    </header>

    <section class="filter-panel">
      <label class="search-box">
        <span>⌕</span>
        <input
          v-model="keyword"
          type="text"
          :placeholder="$t('page.rawData.searchPlaceholder')"
          @keyup.enter="applyFilters"
        />
      </label>
      <button type="button" class="primary-btn" @click="applyFilters">{{ $t('common.search') }}</button>

      <label class="select-box">
        <span>{{ $t('common.species') }}</span>
        <select v-model="selectedSpecies" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="species in filters.species" :key="species.key" :value="species.key">
            {{ species.label }}
          </option>
        </select>
      </label>

      <label class="select-box">
        <span>{{ $t('common.dataType') }}</span>
        <select v-model="selectedType" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in filters.raw_data_types" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <label class="select-box">
        <span>{{ $t('page.rawData.sequencingPlatform') }}</span>
        <select v-model="selectedPlatform" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in filters.sequencing_platforms" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <label class="select-box">
        <span>{{ $t('page.rawData.cluster') }}</span>
        <select v-model="selectedCluster" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in filters.clusters" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <label class="select-box">
        <span>{{ $t('page.rawData.fileStatus') }}</span>
        <select v-model="selectedStatus" @change="applyFilters">
          <option value="">{{ $t('common.all') }}</option>
          <option v-for="item in filters.check_statuses" :key="item" :value="item">{{ statusLabel(item) }}</option>
        </select>
      </label>

      <button type="button" class="light-btn" @click="resetFilters">{{ $t('common.reset') }}</button>
      <button type="button" class="light-btn">{{ $t('common.moreFilters') }} ⌁</button>
    </section>

    <section class="summary-grid">
      <article v-for="card in summaryCards" :key="card.key" class="summary-card">
        <span :class="['summary-icon', card.theme]">{{ card.icon }}</span>
        <span class="summary-text">
          <b>{{ card.label }}</b>
          <strong>{{ card.value }}</strong>
          <em>{{ card.unit }}</em>
        </span>
      </article>
    </section>

    <section :class="['content-grid', { 'drawer-open': drawerOpen }]">
      <article class="table-card">
        <div class="table-header">
          <h2>{{ $t('page.rawData.fileList') }} <span>i</span></h2>
          <button type="button" class="light-btn">⇩ {{ $t('common.exportCurrent') }}</button>
        </div>

        <div class="table-wrap">
          <table>
            <colgroup>
              <col class="col-accession" />
              <col class="col-sample" />
              <col class="col-species" />
              <col class="col-type" />
              <col class="col-platform" />
              <col class="col-file-name" />
              <col class="col-role" />
              <col class="col-size" />
              <col class="col-status" />
              <col class="col-date" />
              <col class="col-action" />
            </colgroup>
            <thead>
              <tr>
                <th>Accession</th>
                <th>Sample ID</th>
                <th>{{ $t('common.species') }}</th>
                <th>{{ $t('common.dataType') }}</th>
                <th>{{ $t('page.rawData.sequencingPlatform') }}</th>
                <th>{{ $t('common.fileName') }}</th>
                <th>{{ $t('common.fileRole') }}</th>
                <th>{{ $t('common.fileSize') }}</th>
                <th>{{ $t('page.rawData.columns.status') }}</th>
                <th>{{ $t('page.rawData.columns.updatedAt') }}</th>
                <th>{{ $t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.file_id"
                :class="{ selected: selectedRow?.file_id === row.file_id }"
                @click="openDrawer(row)"
              >
                <td><span class="link-text">{{ row.accession || '-' }}</span></td>
                <td><span class="text-ellipsis" :title="row.sample_id">{{ row.sample_id || '-' }}</span></td>
                <td class="species-cell">
                  {{ row.species_name || '-' }}
                  <small><em>{{ row.latin_name || '-' }}</em></small>
                </td>
                <td><span class="type-tag">{{ row.raw_data_type || '-' }}</span></td>
                <td><span class="text-ellipsis" :title="row.sequencing_platform">{{ row.sequencing_platform || '-' }}</span></td>
                <td class="file-name-cell">
                  <span class="text-ellipsis" :title="row.file_name">{{ row.file_name || '-' }}</span>
                  <small :title="row.file_path">{{ middleEllipsis(row.file_path, 30) }}</small>
                </td>
                <td><span class="role-tag" :title="row.file_role">{{ fileRoleLabel(row.file_role) }}</span></td>
                <td>{{ row.file_size_display || '-' }}</td>
                <td><span :class="['status-pill', statusClass(row.check_status)]">{{ statusLabel(row.check_status) }}</span></td>
                <td>{{ row.updated_at || '-' }}</td>
                <td>
                  <div class="row-actions">
                    <button type="button" @click.stop="openDrawer(row)">{{ $t('common.details') }}</button>
                  </div>
                </td>
              </tr>
              <tr v-if="!loading && !rows.length">
                <td colspan="11" class="empty-cell">{{ $t('page.rawData.empty') }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="pager">
          <span>{{ $t('common.totalCount', { count: pagination.total || 0 }) }}</span>
          <select v-model.number="pageSize" @change="changePageSize">
            <option :value="20">{{ $t('common.pageSize', { size: 20 }) }}</option>
            <option :value="50">{{ $t('common.pageSize', { size: 50 }) }}</option>
            <option :value="100">{{ $t('common.pageSize', { size: 100 }) }}</option>
          </select>
          <button type="button" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">‹</button>
          <b>{{ currentPage }}</b>
          <button type="button" :disabled="!hasNextPage" @click="changePage(currentPage + 1)">›</button>
        </footer>
      </article>

      <aside v-if="drawerOpen" class="detail-drawer">
        <header>
          <h2>{{ $t('page.rawData.detailsTitle') }}</h2>
          <button type="button" @click="closeDrawer">×</button>
        </header>
        <div v-if="selectedRow" class="drawer-body">
          <section>
            <h3>{{ $t('common.basicInformation') }}</h3>
            <dl>
              <dt>Accession</dt><dd>{{ selectedRow.accession || '-' }}</dd>
              <dt>Sample ID</dt><dd>{{ selectedRow.sample_id || '-' }}</dd>
              <dt>{{ $t('common.species') }}</dt>
              <dd><SpeciesName :common-name="selectedRow.species_name" :scientific-name="selectedRow.latin_name" /></dd>
              <dt>{{ $t('common.dataType') }}</dt><dd>{{ selectedRow.raw_data_type || '-' }}</dd>
              <dt>{{ $t('page.rawData.sequencingPlatform') }}</dt><dd>{{ selectedRow.sequencing_platform || '-' }}</dd>
              <dt>{{ $t('common.fileRole') }}</dt><dd>{{ fileRoleLabel(selectedRow.file_role) }}</dd>
              <dt>{{ $t('page.rawData.cluster') }}</dt><dd>{{ selectedRow.cluster_name || '-' }}</dd>
              <dt>{{ $t('common.fileSize') }}</dt><dd>{{ selectedRow.file_size_display || '-' }}</dd>
              <dt>{{ $t('page.rawData.columns.status') }}</dt><dd><span :class="['status-pill', statusClass(selectedRow.check_status)]">{{ statusLabel(selectedRow.check_status) }}</span></dd>
              <dt>{{ $t('page.rawData.registeredAt') }}</dt><dd>{{ selectedRow.created_at || '-' }}</dd>
              <dt>{{ $t('page.rawData.remarks') }}</dt><dd>{{ selectedRow.remark || '-' }}</dd>
            </dl>
          </section>

          <section>
            <h3>{{ $t('page.rawData.filePath') }}</h3>
            <div class="copy-box">{{ selectedRow.file_path || '-' }}</div>
            <button type="button" class="copy-btn" @click="copyText(selectedRow.file_path, 'page.rawData.path')">{{ $t('page.rawData.copyPath') }}</button>
          </section>

          <section>
            <h3>{{ $t('page.rawData.checksum') }}</h3>
            <div class="copy-box">{{ selectedRow.md5 || '-' }}</div>
            <button type="button" class="copy-btn" @click="copyText(selectedRow.md5, 'page.rawData.checksum')">{{ $t('page.rawData.copyChecksum') }}</button>
          </section>

          <p class="drawer-tip">{{ $t('page.rawData.usageTip') }}</p>
        </div>
        <div v-else class="drawer-empty">{{ $t('page.rawData.drawerEmpty') }}</div>
      </aside>
    </section>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import SpeciesName from '@/components/common/SpeciesName.vue'

const statusMap = {
  verified: { key: 'verified', className: 'verified' },
  pending: { key: 'pending', className: 'pending' },
  unchecked: { key: 'unchecked', className: 'unchecked' },
  missing: { key: 'missing', className: 'missing' },
  已校验: { key: 'verified', className: 'verified' },
  待确认: { key: 'pending', className: 'pending' },
  未校验: { key: 'unchecked', className: 'unchecked' },
  文件缺失: { key: 'missing', className: 'missing' }
}

const fileRoleMap = {
  raw_reads_R1: 'page.rawData.fileRoles.raw_reads_R1',
  raw_reads_R2: 'page.rawData.fileRoles.raw_reads_R2',
  rnaseq_raw_R1: 'page.rawData.fileRoles.rnaseq_raw_R1',
  rnaseq_raw_R2: 'page.rawData.fileRoles.rnaseq_raw_R2',
  hifi_reads: 'page.rawData.fileRoles.hifi_reads',
  ont_reads: 'page.rawData.fileRoles.ont_reads',
  pacbio_reads: 'page.rawData.fileRoles.pacbio_reads',
  illumina_reads: 'page.rawData.fileRoles.illumina_reads',
  fastq: 'page.rawData.fileRoles.fastq',
  bam: 'page.rawData.fileRoles.bam',
  cram: 'page.rawData.fileRoles.cram',
  vcf: 'page.rawData.fileRoles.vcf',
  genome_fasta: 'page.rawData.fileRoles.genome_fasta',
  genome_index: 'page.rawData.fileRoles.genome_index',
  annotation_gff3: 'page.rawData.fileRoles.annotation_gff3',
  annotation_gtf: 'page.rawData.fileRoles.annotation_gtf',
  TEs: 'page.rawData.fileRoles.TEs',
  annotation: 'page.rawData.fileRoles.annotation'
}

export default {
  name: 'RawDataView',
  components: { SpeciesName },
  setup() {
    const { t, te } = useI18n()
    const loading = ref(false)
    const keyword = ref('')
    const selectedSpecies = ref('')
    const selectedType = ref('')
    const selectedPlatform = ref('')
    const selectedCluster = ref('')
    const selectedStatus = ref('')
    const filters = ref({ species: [], raw_data_types: [], sequencing_platforms: [], clusters: [], check_statuses: [] })
    const summary = ref({})
    const rows = ref([])
    const pagination = ref({ total: 0, page: 1, page_size: 20 })
    const currentPage = ref(1)
    const pageSize = ref(20)
    const drawerOpen = ref(false)
    const selectedRow = ref(null)

    const summaryCards = computed(() => [
      { key: 'accession', label: t('page.rawData.summary.accessions'), value: summary.value.accession_count || 0, unit: t('page.rawData.summary.validAccessions'), icon: '◉', theme: 'green' },
      { key: 'sample', label: t('page.rawData.summary.samples'), value: summary.value.sample_count || 0, unit: t('page.rawData.summary.sampleRecords'), icon: '◇', theme: 'blue' },
      { key: 'file', label: t('page.rawData.summary.files'), value: summary.value.raw_file_count || summary.value.datafile_count || 0, unit: t('page.rawData.summary.uniqueDataFiles'), icon: '▤', theme: 'purple' },
      { key: 'size', label: t('page.rawData.summary.totalSize'), value: summary.value.total_size_display || '-', unit: t('page.rawData.summary.uniqueTotal'), icon: 'Σ', theme: 'orange' },
      { key: 'cluster', label: t('page.rawData.summary.clusters'), value: summary.value.cluster_count || 0, unit: t('page.rawData.summary.storageClusters'), icon: '⬡', theme: 'cyan' },
      { key: 'update', label: t('page.rawData.summary.latestUpdate'), value: summary.value.latest_update || '-', unit: t('page.rawData.summary.updateTime'), icon: '◷', theme: 'pink' }
    ])

    const hasNextPage = computed(() => currentPage.value * pageSize.value < (pagination.value.total || 0))

    const requestParams = () => {
      const params = { page: currentPage.value, page_size: pageSize.value }
      if (keyword.value.trim()) params.keyword = keyword.value.trim()
      if (selectedSpecies.value) params.species_id = selectedSpecies.value
      if (selectedType.value) params.raw_data_type = selectedType.value
      if (selectedPlatform.value) params.sequencing_platform = selectedPlatform.value
      if (selectedCluster.value) params.cluster = selectedCluster.value
      if (selectedStatus.value) params.check_status = selectedStatus.value
      return params
    }

    const fetchRawData = async () => {
      loading.value = true
      try {
        const response = await axios.get('/files/query/raw-data/', { params: requestParams() })
        const payload = response.data || {}
        summary.value = payload.summary || {}
        filters.value = payload.filters || filters.value
        rows.value = payload.results || []
        pagination.value = payload.pagination || { total: 0, page: 1, page_size: pageSize.value }
        if (selectedRow.value) {
          const refreshedRow = rows.value.find(row => row.file_id === selectedRow.value.file_id)
          if (refreshedRow) {
            selectedRow.value = refreshedRow
          } else {
            drawerOpen.value = false
            selectedRow.value = null
          }
        }
      } catch (error) {
        console.error('获取原始数据失败:', error)
        ElMessage.error(t('messages.rawDataLoadFailed'))
      } finally {
        loading.value = false
      }
    }

    const applyFilters = () => {
      currentPage.value = 1
      fetchRawData()
    }

    const resetFilters = () => {
      keyword.value = ''
      selectedSpecies.value = ''
      selectedType.value = ''
      selectedPlatform.value = ''
      selectedCluster.value = ''
      selectedStatus.value = ''
      currentPage.value = 1
      fetchRawData()
    }

    const changePage = (page) => {
      currentPage.value = page
      fetchRawData()
    }

    const changePageSize = () => {
      currentPage.value = 1
      fetchRawData()
    }

    const openDrawer = (row) => {
      selectedRow.value = row
      drawerOpen.value = true
    }

    const closeDrawer = () => {
      drawerOpen.value = false
      selectedRow.value = null
    }

    const copyText = async (text, label) => {
      const localizedLabel = t(label)
      if (!text || text === '-') {
        ElMessage.warning(t('messages.valueEmpty', { label: localizedLabel }))
        return
      }
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success(t('messages.copied', { label: localizedLabel }))
      } catch {
        ElMessage.error(t('messages.copyFailed', { label: localizedLabel }))
      }
    }

    const middleEllipsis = (value, maxLength = 34) => {
      if (!value || value === '-') return '-'
      const text = String(value)
      if (text.length <= maxLength) return text
      const edge = Math.max(6, Math.floor((maxLength - 3) / 2))
      return `${text.slice(0, edge)}...${text.slice(-edge)}`
    }

    const statusLabel = (status) => {
      const key = statusMap[status]?.key
      return key ? t(`status.${key}`) : status || '-'
    }
    const statusClass = (status) => statusMap[status]?.className || 'unchecked'
    const fileRoleLabel = (role) => {
      if (!role || role === '-') return '-'
      const key = fileRoleMap[role]
      return key && te(key) ? t(key) : role
    }

    onMounted(fetchRawData)

    return {
      loading,
      keyword,
      selectedSpecies,
      selectedType,
      selectedPlatform,
      selectedCluster,
      selectedStatus,
      filters,
      rows,
      pagination,
      currentPage,
      pageSize,
      drawerOpen,
      selectedRow,
      summaryCards,
      hasNextPage,
      applyFilters,
      resetFilters,
      changePage,
      changePageSize,
      openDrawer,
      closeDrawer,
      copyText,
      middleEllipsis,
      statusLabel,
      statusClass,
      fileRoleLabel,
      statusMap
    }
  }
}
</script>

<style scoped>
.raw-data-page {
  min-height: 100vh;
  padding: 18px 22px 34px;
  background: #f7faff;
  color: #162844;
}

.raw-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 18px;
}

.breadcrumb {
  margin: 0 0 8px;
  color: #6f7f96;
  font-size: 13px;
  font-weight: 700;
}

.raw-header h1 {
  margin: 0;
  color: #10294f;
  font-size: 26px;
  font-weight: 900;
}

.subtitle {
  margin: 8px 0 0;
  color: #5e7088;
  font-size: 14px;
  font-weight: 700;
}

.filter-panel {
  display: grid;
  grid-template-columns: minmax(280px, 1.3fr) 86px repeat(5, minmax(120px, 0.7fr)) 82px 108px;
  gap: 10px;
  padding: 12px;
  margin-bottom: 16px;
  border: 1px solid #dce7f5;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 10px 28px rgba(23, 53, 91, 0.06);
}

.search-box,
.select-box {
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  border: 1px solid #dce7f5;
  border-radius: 9px;
  background: #fff;
}

.search-box input,
.select-box select {
  width: 100%;
  border: none;
  outline: none;
  color: #233c61;
  background: transparent;
  font-weight: 700;
}

.search-box input::placeholder {
  color: #91a0b4;
}

.select-box span {
  white-space: nowrap;
  color: #233c61;
  font-size: 13px;
  font-weight: 900;
}

.primary-btn,
.light-btn,
.row-actions button,
.copy-btn {
  border: 1px solid #c9dcf4;
  border-radius: 9px;
  background: #f8fbff;
  color: #1d5fc8;
  font-weight: 900;
  cursor: pointer;
}

.primary-btn {
  background: #1f6fe5;
  color: #fff;
  border-color: #1f6fe5;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.summary-card {
  min-height: 100px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid #dce7f5;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 28px rgba(23, 53, 91, 0.07);
}

.summary-icon {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  font-size: 21px;
  font-weight: 900;
}

.summary-icon.green { background: #46bd5f; }
.summary-icon.blue { background: #3195e4; }
.summary-icon.purple { background: #7e60e6; }
.summary-icon.orange { background: #ff9f2f; }
.summary-icon.cyan { background: #29bac4; }
.summary-icon.pink { background: #ef5a91; }

.summary-text b,
.summary-text strong,
.summary-text em {
  display: block;
}

.summary-text b {
  color: #52677f;
  font-size: 14px;
}

.summary-text strong {
  margin-top: 4px;
  color: #10294f;
  font-size: 25px;
  line-height: 1.1;
}

.summary-text em {
  margin-top: 4px;
  color: #7b8ca3;
  font-size: 12px;
  font-style: normal;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.content-grid.drawer-open {
  grid-template-columns: minmax(0, 1fr) 390px;
}

.table-card,
.detail-drawer {
  border: 1px solid #dce7f5;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(23, 53, 91, 0.07);
  overflow: hidden;
}

.table-header {
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid #e4edf8;
}

.table-header h2 {
  margin: 0;
  color: #173a69;
  font-size: 17px;
  font-weight: 900;
}

.table-header h2 span {
  display: inline-grid;
  place-items: center;
  width: 16px;
  height: 16px;
  margin-left: 4px;
  border: 1px solid #a8bad0;
  border-radius: 50%;
  color: #7890aa;
  font-size: 11px;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 1160px;
  border-collapse: collapse;
  table-layout: fixed;
}

.col-accession { width: 9%; }
.col-sample { width: 10%; }
.col-species { width: 11%; }
.col-type { width: 8%; }
.col-platform { width: 9%; }
.col-file-name { width: 18%; }
.col-role { width: 11%; }
.col-size { width: 8%; }
.col-status { width: 8%; }
.col-date { width: 10%; }
.col-action { width: 7%; }

th,
td {
  height: 54px;
  padding: 0 8px;
  border-right: 1px solid #e2ebf6;
  border-bottom: 1px solid #e2ebf6;
  text-align: center;
  font-size: 12px;
}

th {
  background: #f0f6fd;
  color: #294561;
  font-weight: 900;
}

td {
  color: #173052;
  font-weight: 700;
}

tr.selected td,
tbody tr:hover td {
  background: #f7fbff;
}

.link-text {
  color: #1f6fe5;
  font-weight: 900;
}

.species-cell small {
  display: block;
  color: #687c95;
}

.text-ellipsis,
.file-name-cell small {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-name-cell {
  text-align: left;
}

.file-name-cell .text-ellipsis {
  color: #173052;
  font-weight: 900;
}

.file-name-cell small {
  margin-top: 4px;
  color: #6f8198;
  font-size: 11px;
  font-weight: 700;
}

.type-tag {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 8px;
  color: #1e63c8;
  background: #eaf3ff;
  font-weight: 900;
}

.role-tag {
  display: inline-flex;
  max-width: 100%;
  padding: 4px 8px;
  border-radius: 8px;
  color: #174c9b;
  background: #f0f6ff;
  font-weight: 900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-button {
  max-width: 140px;
  border: none;
  background: transparent;
  color: #1f6fe5;
  font-weight: 800;
  cursor: pointer;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.status-pill::before {
  content: "";
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.status-pill.verified { color: #0d9a5d; background: #e8f8ef; }
.status-pill.pending { color: #c87400; background: #fff2df; }
.status-pill.unchecked { color: #64748b; background: #eef2f7; }
.status-pill.missing { color: #d9364f; background: #ffe9ed; }

.row-actions {
  display: flex;
  justify-content: center;
  gap: 6px;
}

.row-actions button {
  height: 28px;
  padding: 0 8px;
  font-size: 12px;
}

.empty-cell {
  height: 180px;
  color: #7a8da3;
}

.pager {
  min-height: 58px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  color: #5f728b;
  font-weight: 800;
}

.pager select,
.pager button,
.pager b {
  min-width: 34px;
  height: 32px;
  display: grid;
  place-items: center;
  border: 1px solid #d6e3f3;
  border-radius: 7px;
  background: #fff;
  color: #1b3c68;
}

.pager b {
  color: #fff;
  background: #1f6fe5;
  border-color: #1f6fe5;
}

.detail-drawer {
  position: sticky;
  top: 18px;
  min-height: 680px;
}

.detail-drawer header {
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid #e4edf8;
}

.detail-drawer h2 {
  margin: 0;
  font-size: 18px;
  color: #173a69;
}

.detail-drawer header button {
  border: none;
  background: transparent;
  color: #61758d;
  font-size: 23px;
  cursor: pointer;
}

.drawer-body {
  padding: 16px;
}

.drawer-body section {
  margin-bottom: 18px;
}

.drawer-body h3 {
  margin: 0 0 12px;
  color: #173a69;
  font-size: 15px;
}

dl {
  display: grid;
  grid-template-columns: 94px 1fr;
  gap: 9px 12px;
  margin: 0;
  font-size: 13px;
}

dt {
  color: #5f728b;
  font-weight: 900;
}

dd {
  margin: 0;
  color: #193b64;
  font-weight: 700;
}

.copy-box {
  padding: 12px;
  border: 1px solid #dce7f5;
  border-radius: 10px;
  background: #f8fbff;
  color: #173a69;
  font-size: 13px;
  line-height: 1.55;
  word-break: break-all;
}

.copy-btn {
  height: 30px;
  margin-top: 9px;
  padding: 0 11px;
}

.drawer-tip {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #d5e6fa;
  background: #edf5ff;
  color: #4f6680;
  font-size: 13px;
  line-height: 1.6;
}

.drawer-empty {
  padding: 80px 18px;
  color: #7a8da3;
  text-align: center;
  font-weight: 800;
}
</style>

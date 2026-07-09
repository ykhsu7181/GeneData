<template>
  <div class="raw-data-page">
    <header class="raw-header">
      <div>
        <p class="breadcrumb">首页 / 数据资源 / 原始数据</p>
        <h1>原始数据 Raw Data</h1>
        <p class="subtitle">集中展示原始测序数据在各集群中的存放路径、文件信息与校验状态。</p>
      </div>
    </header>

    <section class="filter-panel">
      <label class="search-box">
        <span>⌕</span>
        <input
          v-model="keyword"
          type="text"
          placeholder="搜索 Accession / Sample / 文件名 / 路径 / MD5"
          @keyup.enter="applyFilters"
        />
      </label>
      <button type="button" class="primary-btn" @click="applyFilters">搜索</button>

      <label class="select-box">
        <span>物种</span>
        <select v-model="selectedSpecies" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="species in filters.species" :key="species.key" :value="species.key">
            {{ species.label }}
          </option>
        </select>
      </label>

      <label class="select-box">
        <span>数据类型</span>
        <select v-model="selectedType" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in filters.raw_data_types" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <label class="select-box">
        <span>测序平台</span>
        <select v-model="selectedPlatform" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in filters.sequencing_platforms" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <label class="select-box">
        <span>所在集群</span>
        <select v-model="selectedCluster" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in filters.clusters" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>

      <label class="select-box">
        <span>文件状态</span>
        <select v-model="selectedStatus" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="item in filters.check_statuses" :key="item" :value="item">{{ statusLabel(item) }}</option>
        </select>
      </label>

      <button type="button" class="light-btn" @click="resetFilters">重置</button>
      <button type="button" class="light-btn">更多条件 ⌁</button>
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

    <section class="content-grid">
      <article class="table-card">
        <div class="table-header">
          <h2>原始数据文件列表 <span>i</span></h2>
          <button type="button" class="light-btn">⇩ 导出当前结果</button>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Accession</th>
                <th>Sample ID</th>
                <th>物种</th>
                <th>数据类型</th>
                <th>测序平台</th>
                <th>文件名</th>
                <th>文件角色</th>
                <th>所在集群</th>
                <th>文件路径</th>
                <th>文件大小</th>
                <th>MD5</th>
                <th>校验状态</th>
                <th>更新时间</th>
                <th>操作</th>
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
                <td>{{ row.sample_id || '-' }}</td>
                <td class="species-cell">
                  {{ row.species_name || '-' }}
                  <small>{{ row.latin_name || '-' }}</small>
                </td>
                <td><span class="type-tag">{{ row.raw_data_type || '-' }}</span></td>
                <td>{{ row.sequencing_platform || '-' }}</td>
                <td>{{ row.file_name || '-' }}</td>
                <td>{{ row.file_role || '-' }}</td>
                <td>{{ row.cluster_name || '-' }}</td>
                <td>
                  <button type="button" class="path-button" :title="row.file_path" @click.stop="copyText(row.file_path, '路径')">
                    {{ middleEllipsis(row.file_path) }}
                  </button>
                </td>
                <td>{{ row.file_size_display || '-' }}</td>
                <td>
                  <button type="button" class="path-button" :title="row.md5" @click.stop="copyText(row.md5, 'MD5')">
                    {{ row.md5_display || '-' }}
                  </button>
                </td>
                <td><span :class="['status-pill', statusClass(row.check_status)]">{{ statusLabel(row.check_status) }}</span></td>
                <td>{{ row.updated_at || '-' }}</td>
                <td>
                  <div class="row-actions">
                    <button type="button" @click.stop="copyText(row.file_path, '路径')">路径</button>
                    <button type="button" @click.stop="openDrawer(row)">详情</button>
                  </div>
                </td>
              </tr>
              <tr v-if="!loading && !rows.length">
                <td colspan="14" class="empty-cell">暂无原始数据文件登记</td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="pager">
          <span>共 {{ pagination.total || 0 }} 条</span>
          <select v-model.number="pageSize" @change="changePageSize">
            <option :value="20">20条/页</option>
            <option :value="50">50条/页</option>
            <option :value="100">100条/页</option>
          </select>
          <button type="button" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">‹</button>
          <b>{{ currentPage }}</b>
          <button type="button" :disabled="!hasNextPage" @click="changePage(currentPage + 1)">›</button>
        </footer>
      </article>

      <aside :class="['detail-drawer', { open: drawerOpen }]">
        <header>
          <h2>原始数据详情</h2>
          <button type="button" @click="closeDrawer">×</button>
        </header>
        <div v-if="selectedRow" class="drawer-body">
          <section>
            <h3>基本信息</h3>
            <dl>
              <dt>Accession</dt><dd>{{ selectedRow.accession || '-' }}</dd>
              <dt>Sample ID</dt><dd>{{ selectedRow.sample_id || '-' }}</dd>
              <dt>物种</dt><dd>{{ selectedRow.species_name || '-' }}（{{ selectedRow.latin_name || '-' }}）</dd>
              <dt>数据类型</dt><dd>{{ selectedRow.raw_data_type || '-' }}</dd>
              <dt>测序平台</dt><dd>{{ selectedRow.sequencing_platform || '-' }}</dd>
              <dt>文件角色</dt><dd>{{ selectedRow.file_role || '-' }}</dd>
              <dt>所在集群</dt><dd>{{ selectedRow.cluster_name || '-' }}</dd>
              <dt>文件大小</dt><dd>{{ selectedRow.file_size_display || '-' }}</dd>
              <dt>校验状态</dt><dd><span :class="['status-pill', statusClass(selectedRow.check_status)]">{{ statusLabel(selectedRow.check_status) }}</span></dd>
              <dt>登记时间</dt><dd>{{ selectedRow.created_at || '-' }}</dd>
              <dt>备注</dt><dd>{{ selectedRow.remark || '-' }}</dd>
            </dl>
          </section>

          <section>
            <h3>文件路径</h3>
            <div class="copy-box">{{ selectedRow.file_path || '-' }}</div>
            <button type="button" class="copy-btn" @click="copyText(selectedRow.file_path, '路径')">复制路径</button>
          </section>

          <section>
            <h3>MD5 校验值</h3>
            <div class="copy-box">{{ selectedRow.md5 || '-' }}</div>
            <button type="button" class="copy-btn" @click="copyText(selectedRow.md5, 'MD5')">复制 MD5</button>
          </section>

          <p class="drawer-tip">提示：原始数据文件体积较大，请在对应集群环境中使用。本页不提供 Web 下载入口。</p>
        </div>
        <div v-else class="drawer-empty">点击某一行查看路径详情</div>
      </aside>
    </section>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const statusMap = {
  verified: { label: '已校验', className: 'verified' },
  pending: { label: '待确认', className: 'pending' },
  unchecked: { label: '未校验', className: 'unchecked' },
  missing: { label: '文件缺失', className: 'missing' },
  已校验: { label: '已校验', className: 'verified' },
  待确认: { label: '待确认', className: 'pending' },
  未校验: { label: '未校验', className: 'unchecked' },
  文件缺失: { label: '文件缺失', className: 'missing' }
}

export default {
  name: 'RawDataView',
  setup() {
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
      { key: 'accession', label: '材料数', value: summary.value.accession_count || 0, unit: '有效 Accession', icon: '苗', theme: 'green' },
      { key: 'sample', label: '样本数', value: summary.value.sample_count || 0, unit: '样本登记', icon: '样', theme: 'blue' },
      { key: 'file', label: '原始文件数', value: summary.value.raw_file_count || summary.value.datafile_count || 0, unit: 'DataFile 去重', icon: '文', theme: 'purple' },
      { key: 'size', label: '总数据量', value: summary.value.total_size_display || '-', unit: '去重求和', icon: '量', theme: 'orange' },
      { key: 'cluster', label: '集群数', value: summary.value.cluster_count || 0, unit: '存储集群', icon: '集', theme: 'cyan' },
      { key: 'update', label: '最近更新', value: summary.value.latest_update || '-', unit: '数据更新时间', icon: '时', theme: 'pink' }
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
        if (!selectedRow.value && rows.value.length) {
          selectedRow.value = rows.value[0]
        }
      } catch (error) {
        console.error('获取原始数据失败:', error)
        ElMessage.error('获取原始数据失败')
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
    }

    const copyText = async (text, label) => {
      if (!text || text === '-') {
        ElMessage.warning(`${label}为空`)
        return
      }
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success(`已复制${label}`)
      } catch (error) {
        ElMessage.error(`复制${label}失败`)
      }
    }

    const middleEllipsis = (value) => {
      if (!value || value === '-') return '-'
      const text = String(value)
      if (text.length <= 34) return text
      return `${text.slice(0, 16)}...${text.slice(-16)}`
    }

    const statusLabel = (status) => statusMap[status]?.label || status || '-'
    const statusClass = (status) => statusMap[status]?.className || 'unchecked'

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
  grid-template-columns: minmax(0, 1fr) 390px;
  gap: 16px;
  align-items: start;
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
  min-width: 1460px;
  border-collapse: collapse;
  table-layout: fixed;
}

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

.type-tag {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 8px;
  color: #1e63c8;
  background: #eaf3ff;
  font-weight: 900;
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

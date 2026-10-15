<template>
  <main class="assembly-portal" aria-labelledby="assembly-title">
    <section class="portal-hero">
      <nav class="breadcrumb" :aria-label="$t('page.assembly.breadcrumbLabel')">
        <RouterLink to="/dashboard">{{ $t('nav.home') }}</RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ $t('page.assembly.title') }}</span>
      </nav>
      <h1 id="assembly-title">{{ $t('page.assembly.title') }}</h1>
    </section>

    <section class="search-card" role="search" :aria-label="$t('page.assembly.searchTitle')">
      <div class="search-row">
        <el-input
          v-model="searchInput"
          class="search-input"
          :placeholder="$t('page.assembly.searchPlaceholder')"
          :aria-label="$t('page.assembly.searchTitle')"
          clearable
          size="large"
          @keyup.enter="submitSearch"
          @clear="clearSearch"
        >
          <template #prefix>
            <el-icon class="search-prefix-icon" aria-hidden="true"><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" size="large" :loading="loading" @click="submitSearch">
          {{ $t('common.search') }}
        </el-button>
      </div>
    </section>

    <div class="content-grid">
      <section
        class="list-card"
        aria-labelledby="assembly-list-title"
        :aria-busy="String(loading)"
        aria-live="polite"
      >
        <div class="card-header">
          <h2 id="assembly-list-title">
            <el-icon aria-hidden="true"><Collection /></el-icon>
            {{ $t('page.assembly.listTitle') }}
          </h2>
          <div class="list-header-actions">
            <span class="total">{{ $t('page.assembly.totalAssemblies', { count: total }) }}</span>
            <el-popover placement="bottom-end" :width="280" trigger="click">
              <template #reference>
                <el-button
                  class="more-columns-button"
                  text
                  :aria-label="$t('page.assembly.chooseColumns')"
                  aria-haspopup="dialog"
                >
                  {{ $t('page.assembly.moreColumns') }}
                  <el-icon aria-hidden="true"><ArrowDown /></el-icon>
                </el-button>
              </template>
              <div class="column-picker" role="group" :aria-label="$t('page.assembly.chooseColumns')">
                <el-checkbox-group v-model="selectedColumns">
                  <el-checkbox
                    v-for="column in columnOptions"
                    :key="column.key"
                    :value="column.key"
                    :disabled="column.required"
                  >
                    {{ $t(column.labelKey) }}
                  </el-checkbox>
                </el-checkbox-group>
                <el-button class="reset-widths-button" size="small" @click="restoreColumnWidths">
                  {{ $t('page.assembly.resetColumnWidths') }}
                </el-button>
              </div>
            </el-popover>
          </div>
        </div>

        <el-alert
          v-if="error"
          class="state-alert"
          type="error"
          :closable="false"
          show-icon
        >
          <template #title>
            <span>{{ $t('page.assembly.loadFailed') }}</span>
            <button type="button" class="inline-action" @click="fetchAssemblies">
              {{ $t('common.retry') }}
            </button>
          </template>
        </el-alert>

        <el-table
          v-loading="loading"
          :data="assemblies"
          class="assembly-table"
          :empty-text="emptyText"
          :aria-label="$t('page.assembly.listTitle')"
          border
          @header-dragend="handleHeaderDragEnd"
          @row-click="openAssembly"
        >
          <el-table-column prop="accession" :label="$t('page.assembly.columns.accession')" :width="columnWidth('accession')">
            <template #default="{ row }">
              <button
                type="button"
                class="link-button"
                :aria-label="$t('page.assembly.openAccession', { accession: displayValue(row.accession) })"
                @click.stop="openAccession(row)"
              >
                {{ displayValue(row.accession) }}
              </button>
            </template>
          </el-table-column>
          <el-table-column prop="assembly" :label="$t('page.assembly.columns.assembly')" :width="columnWidth('assembly')">
            <template #default="{ row }">
              <button
                type="button"
                class="link-button"
                :aria-label="$t('page.assembly.openAssembly', { assembly: displayValue(row.assembly) })"
                @click.stop="openAssembly(row)"
              >
                {{ displayValue(row.assembly) }}
              </button>
            </template>
          </el-table-column>
          <el-table-column
            v-if="selectedColumns.includes('species')"
            prop="species"
            :label="$t('page.assembly.columns.species')"
            :width="columnWidth('species')"
          >
            <template #default="{ row }">
              <em>{{ displayValue(row.species) }}</em>
            </template>
          </el-table-column>
          <el-table-column
            v-if="selectedColumns.includes('assembly_level')"
            prop="assembly_level"
            :label="$t('page.assembly.columns.level')"
            :width="columnWidth('assembly_level')"
          >
            <template #default="{ row }">
              {{ formatLevel(row.assembly_level) }}
            </template>
          </el-table-column>
          <el-table-column
            v-if="selectedColumns.includes('assembly_accession')"
            prop="assembly_accession"
            :label="$t('page.assembly.columns.assemblyAccession')"
            :width="columnWidth('assembly_accession')"
          >
            <template #default="{ row }">
              <button
                v-if="row.assembly_accession"
                type="button"
                class="link-button subtle"
                :aria-label="$t('page.assembly.openAssembly', { assembly: row.assembly_accession })"
                @click.stop="openAssembly(row)"
              >
                {{ row.assembly_accession }}
              </button>
              <span v-else>{{ emptyMark }}</span>
            </template>
          </el-table-column>
          <el-table-column
            v-for="column in visibleStatisticColumns"
            :key="column.key"
            :prop="column.key"
            :label="$t(column.labelKey)"
            :width="columnWidth(column.key)"
          >
            <template #default="{ row }">
              {{ formatStatistic(row[column.key], column.key) }}
            </template>
          </el-table-column>
          <template #empty>
            <div class="table-empty" role="status">
              <p>{{ emptyText }}</p>
              <button
                v-if="routeSearch"
                type="button"
                class="inline-action clear-search-action"
                @click="clearSearch"
              >
                {{ $t('page.assembly.clearSearch') }}
              </button>
            </div>
          </template>
        </el-table>

        <div class="table-footer">
          <p>
            {{ $t('page.assembly.showingRange', { start: rangeStart, end: rangeEnd, total }) }}
          </p>
          <el-pagination
            background
            layout="prev, pager, next"
            :current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            :pager-count="5"
            :disabled="loading"
            :aria-label="$t('page.assembly.paginationLabel')"
            @current-change="changePage"
          />
        </div>
      </section>

      <aside class="recent-card" aria-labelledby="recent-assemblies-title">
        <div class="card-header">
          <h2 id="recent-assemblies-title">
            <el-icon aria-hidden="true"><Clock /></el-icon>
            {{ $t('page.assembly.recent') }}
          </h2>
          <button
            type="button"
            class="view-all"
            :disabled="!recentAssemblies.length"
            :aria-label="$t('page.assembly.viewAllRecent')"
            @click="openRecentDrawer($event.currentTarget)"
          >
            {{ $t('common.viewAll') }} →
          </button>
        </div>
        <div v-if="recentPanelItems.length" class="recent-list">
          <button
            v-for="item in recentPanelItems"
            :key="item.id"
            type="button"
            class="recent-row"
            :aria-label="$t('page.assembly.openAssembly', { assembly: displayValue(item.assembly) })"
            @click="openAssembly(item)"
          >
            <strong>{{ displayValue(item.accession) }}</strong>
            <span>{{ displayValue(item.assembly) }}</span>
            <time :datetime="item.viewed_at || undefined">{{ relativeTime(item.viewed_at) }}</time>
          </button>
        </div>
        <p v-else class="empty-recent">{{ $t('page.assembly.noRecent') }}</p>
      </aside>
    </div>

    <AssemblyRecentDrawer
      v-model="recentDrawerOpen"
      :items="recentAssemblies"
      @closed="restoreDrawerFocus"
      @select="openAssembly"
      @remove="removeRecent"
      @clear="clearRecent"
    />
  </main>
</template>

<script>
import { computed, onMounted, ref, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { ArrowDown, Clock, Collection, Search } from '@element-plus/icons-vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import AssemblyRecentDrawer from '@/components/assembly/AssemblyRecentDrawer.vue';
import {
  clearRecentAssemblies,
  getRecentAssemblies,
  recordRecentAssembly,
  removeRecentAssembly
} from '@/services/assemblyPreferences.js';
import {
  loadColumnWidths,
  resetColumnWidths,
  resizeColumn,
  saveColumnWidths
} from '@/services/tableColumnWidths.mjs';

const RECENT_PANEL_LIMIT = 5;
const DEFAULT_PAGE_SIZE = 20;
const ASSEMBLY_COLUMNS_STORAGE_KEY = 'genedata:assembly-columns:v2';
const ASSEMBLY_COLUMN_WIDTHS_STORAGE_KEY = 'genedata:assembly-column-widths:v1';
const emptyMark = '—';
const requiredColumnKeys = ['accession', 'assembly'];
const statisticColumnOptions = [
  { key: 'genome_size', labelKey: 'page.assembly.columns.genomeSize', minWidth: 140 },
  { key: 'chromosome_count', labelKey: 'page.assembly.columns.chromosomeCount', minWidth: 150 },
  { key: 'contig_count', labelKey: 'page.assembly.columns.contigCount', minWidth: 125 },
  { key: 'n50', labelKey: 'page.assembly.columns.n50', minWidth: 125 },
  { key: 'gc_content', labelKey: 'page.assembly.columns.gcContent', minWidth: 125 }
];
const columnOptions = [
  { key: 'accession', labelKey: 'page.assembly.columns.accession', required: true },
  { key: 'assembly', labelKey: 'page.assembly.columns.assembly', required: true },
  { key: 'species', labelKey: 'page.assembly.columns.species' },
  { key: 'assembly_level', labelKey: 'page.assembly.columns.level' },
  { key: 'assembly_accession', labelKey: 'page.assembly.columns.assemblyAccession' },
  ...statisticColumnOptions
];
const defaultColumnWidths = {
  accession: 130,
  assembly: 220,
  species: 180,
  assembly_level: 130,
  assembly_accession: 190,
  genome_size: 150,
  chromosome_count: 165,
  contig_count: 135,
  n50: 135,
  gc_content: 135
};
const validColumnKeys = new Set(columnOptions.map(column => column.key));

const loadSelectedColumns = () => {
  try {
    const stored = JSON.parse(localStorage.getItem(ASSEMBLY_COLUMNS_STORAGE_KEY));
    if (!Array.isArray(stored)) return [...requiredColumnKeys, 'species', 'assembly_level'];
    return [...new Set([
      ...requiredColumnKeys,
      ...stored.filter(key => validColumnKeys.has(key) && !requiredColumnKeys.includes(key))
    ])];
  } catch (_) {
    return [...requiredColumnKeys, 'species', 'assembly_level'];
  }
};

const firstQueryValue = (value) => (Array.isArray(value) ? value[0] : value);

const normalizeText = (value) => {
  const normalized = value === null || value === undefined ? '' : String(value).trim();
  return normalized;
};

export default {
  name: 'AssemblyPortalView',
  components: {
    AssemblyRecentDrawer,
    ArrowDown,
    Clock,
    Collection,
    Search
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { t, locale } = useI18n();
    const assemblies = ref([]);
    const loading = ref(false);
    const error = ref(false);
    const searchInput = ref('');
    const total = ref(0);
    const currentPage = ref(1);
    const pageSize = ref(DEFAULT_PAGE_SIZE);
    const recentAssemblies = ref([]);
    const recentDrawerOpen = ref(false);
    const selectedColumns = ref(loadSelectedColumns());
    const columnWidths = ref(loadColumnWidths(
      ASSEMBLY_COLUMN_WIDTHS_STORAGE_KEY,
      defaultColumnWidths
    ));
    let requestToken = 0;
    let drawerTrigger = null;

    const routeSearch = computed(() => normalizeText(firstQueryValue(route.query.search || route.query.q)));
    const routePage = computed(() => {
      const page = Number(firstQueryValue(route.query.page) || 1);
      return Number.isInteger(page) && page > 0 ? page : 1;
    });

    const emptyText = computed(() => (
      error.value ? t('page.assembly.loadFailed') : t('page.assembly.noResults')
    ));
    const recentPanelItems = computed(() => recentAssemblies.value.slice(0, RECENT_PANEL_LIMIT));
    const visibleStatisticColumns = computed(() => statisticColumnOptions.filter(
      (column) => selectedColumns.value.includes(column.key)
    ));

    const columnWidth = key => columnWidths.value[key] || defaultColumnWidths[key] || 120;
    const handleHeaderDragEnd = (newWidth, oldWidth, column) => {
      const key = column?.property;
      if (!key || !(key in defaultColumnWidths)) return;
      columnWidths.value = resizeColumn(columnWidths.value, key, newWidth, defaultColumnWidths);
      saveColumnWidths(ASSEMBLY_COLUMN_WIDTHS_STORAGE_KEY, columnWidths.value);
    };
    const restoreColumnWidths = () => {
      columnWidths.value = resetColumnWidths(defaultColumnWidths);
      saveColumnWidths(ASSEMBLY_COLUMN_WIDTHS_STORAGE_KEY, columnWidths.value);
    };

    const rangeStart = computed(() => (total.value ? ((currentPage.value - 1) * pageSize.value) + 1 : 0));
    const rangeEnd = computed(() => Math.min(currentPage.value * pageSize.value, total.value));

    const displayValue = (value) => normalizeText(value) || emptyMark;

    const formatBasePairs = (value) => {
      if (value === null || value === undefined || value === '') return emptyMark;
      const number = Number(value);
      if (!Number.isFinite(number) || number < 0) return emptyMark;
      const units = [
        { threshold: 1e9, divisor: 1e9, suffix: 'Gb' },
        { threshold: 1e6, divisor: 1e6, suffix: 'Mb' },
        { threshold: 1e3, divisor: 1e3, suffix: 'kb' }
      ];
      const unit = units.find((item) => number >= item.threshold);
      if (!unit) return `${new Intl.NumberFormat(locale.value).format(number)} bp`;
      return `${new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 }).format(number / unit.divisor)} ${unit.suffix}`;
    };

    const formatStatistic = (value, key) => {
      if (key === 'genome_size' || key === 'n50') return formatBasePairs(value);
      if (value === null || value === undefined || value === '') return emptyMark;
      const number = Number(value);
      if (!Number.isFinite(number)) return emptyMark;
      if (key === 'gc_content') {
        return `${new Intl.NumberFormat(locale.value, { maximumFractionDigits: 3 }).format(number)}%`;
      }
      return new Intl.NumberFormat(locale.value).format(number);
    };

    const formatLevel = (value) => {
      const normalized = normalizeText(value);
      if (!normalized) return emptyMark;
      const lower = normalized.toLowerCase();
      const known = {
        chromosome: 'Chromosome',
        scaffold: 'Scaffold',
        contig: 'Contig'
      };
      return known[lower] || normalized;
    };

    const syncFromRoute = () => {
      searchInput.value = routeSearch.value;
      currentPage.value = routePage.value;
    };

    const buildPortalQuery = (search, page = 1) => {
      const query = {};
      const normalizedSearch = normalizeText(search);
      if (normalizedSearch) query.search = normalizedSearch;
      if (page > 1) query.page = String(page);
      return query;
    };

    const normalizeRouteQuery = () => {
      const query = buildPortalQuery(routeSearch.value, routePage.value);
      const rawSearch = normalizeText(firstQueryValue(route.query.search));
      const rawAliasSearch = normalizeText(firstQueryValue(route.query.q));
      const rawPage = normalizeText(firstQueryValue(route.query.page));
      const nextPage = query.page || '';
      const needsReplace = (
        rawAliasSearch
        || rawSearch !== (query.search || '')
        || rawPage !== nextPage
      );
      if (needsReplace) {
        router.replace({ name: 'assembly', query });
        return true;
      }
      return false;
    };

    const pushQuery = (search, page = 1) => {
      const query = buildPortalQuery(search, page);
      return router.push({ name: 'assembly', query });
    };

    const fetchAssemblies = async () => {
      const token = ++requestToken;
      loading.value = true;
      error.value = false;
      try {
        const response = await axios.get('/files/assemblies/', {
          params: {
            search: routeSearch.value || undefined,
            page: currentPage.value,
            page_size: pageSize.value
          }
        });
        if (token !== requestToken) return;
        const payload = response.data || {};
        assemblies.value = Array.isArray(payload.results) ? payload.results : [];
        total.value = Number(payload.count) || 0;
        currentPage.value = Number(payload.page) || currentPage.value;
        pageSize.value = Number(payload.page_size) || pageSize.value;
      } catch {
        if (token !== requestToken) return;
        assemblies.value = [];
        total.value = 0;
        error.value = true;
        ElMessage.error(t('page.assembly.loadFailed'));
      } finally {
        if (token === requestToken) loading.value = false;
      }
    };

    const submitSearch = () => pushQuery(searchInput.value, 1);
    const clearSearch = () => pushQuery('', 1);
    const changePage = (page) => pushQuery(routeSearch.value, page);

    const loadRecent = () => {
      recentAssemblies.value = getRecentAssemblies();
    };

    const showStorageError = () => ElMessage.warning(t('page.assembly.preferenceSaveFailed'));

    const openRecentDrawer = (trigger) => {
      drawerTrigger = trigger || null;
      recentDrawerOpen.value = true;
    };

    const restoreDrawerFocus = () => {
      drawerTrigger?.focus?.();
      drawerTrigger = null;
    };

    const removeRecent = (id) => {
      const result = removeRecentAssembly(id);
      recentAssemblies.value = result.items;
      if (!result.persisted) showStorageError();
    };

    const clearRecent = () => {
      const result = clearRecentAssemblies();
      recentAssemblies.value = result.items;
      if (!result.persisted) showStorageError();
    };

    const openAssembly = async (row) => {
      const id = Number(row?.id);
      if (!Number.isInteger(id) || id <= 0) return;
      recentDrawerOpen.value = false;
      const result = recordRecentAssembly(row);
      recentAssemblies.value = result.items;
      if (!result.persisted) showStorageError();
      await router.push({
        name: 'assembly-detail',
        params: { assemblyId: String(id) },
        query: {
          from: 'assembly',
          ...buildPortalQuery(routeSearch.value, currentPage.value)
        }
      });
    };

    const openAccession = async (row) => {
      const accession = normalizeText(row?.accession);
      if (!accession) return;
      await router.push({ name: 'accession-card', query: { accession } });
    };

    const relativeTime = (value) => {
      const timestamp = value ? new Date(value).getTime() : NaN;
      if (Number.isNaN(timestamp)) return emptyMark;
      const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
      if (seconds < 60) return t('page.assembly.time.justNow');
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return t('page.assembly.time.minutesAgo', { count: minutes });
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return t('page.assembly.time.hoursAgo', { count: hours });
      const days = Math.floor(hours / 24);
      if (days === 1) return t('page.assembly.time.yesterday');
      if (days < 7) return t('page.assembly.time.daysAgo', { count: days });
      return new Intl.DateTimeFormat(locale.value).format(new Date(timestamp));
    };

    watch(
      () => [routeSearch.value, routePage.value],
      () => {
        if (normalizeRouteQuery()) return;
        syncFromRoute();
        fetchAssemblies();
      },
      { immediate: true }
    );

    watch(selectedColumns, (value) => {
      const normalized = [...new Set([
        ...requiredColumnKeys,
        ...value.filter(key => validColumnKeys.has(key) && !requiredColumnKeys.includes(key))
      ])];
      if (normalized.length !== value.length || normalized.some((key, index) => key !== value[index])) {
        selectedColumns.value = normalized;
        return;
      }
      try { localStorage.setItem(ASSEMBLY_COLUMNS_STORAGE_KEY, JSON.stringify(normalized)); } catch (_) { /* optional */ }
    }, { deep: true });

    onMounted(loadRecent);

    return {
      assemblies,
      changePage,
      clearRecent,
      clearSearch,
      columnOptions,
      columnWidth,
      currentPage,
      displayValue,
      emptyMark,
      emptyText,
      error,
      fetchAssemblies,
      formatStatistic,
      formatLevel,
      handleHeaderDragEnd,
      loading,
      openAccession,
      openAssembly,
      openRecentDrawer,
      pageSize,
      rangeEnd,
      rangeStart,
      recentAssemblies,
      recentDrawerOpen,
      recentPanelItems,
      relativeTime,
      removeRecent,
      restoreColumnWidths,
      restoreDrawerFocus,
      routeSearch,
      searchInput,
      selectedColumns,
      submitSearch,
      total,
      visibleStatisticColumns
    };
  }
};
</script>

<style scoped>
.assembly-portal {
  min-height: calc(100vh - 160px);
  color: #132449;
}

.portal-hero {
  margin-bottom: 12px;
  padding-top: 4px;
}

.breadcrumb {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #4b6693;
  font-size: 13px;
  margin-bottom: 8px;
}

.breadcrumb a {
  color: #31558f;
  text-decoration: none;
}

.breadcrumb a:hover,
.breadcrumb a:focus-visible {
  color: #0068e8;
  text-decoration: underline;
}

.portal-hero h1 {
  margin: 0;
  color: #0a2b73;
  font-size: 30px;
  line-height: 1.15;
}

.search-card,
.list-card,
.recent-card {
  border: 1px solid #d9e7f7;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 14px 36px rgba(36, 103, 178, 0.08);
}

.search-card {
  padding: 16px 20px 14px;
  margin-bottom: 14px;
}

.card-header h2 {
  margin: 0;
  color: #0060df;
  font-size: 18px;
  line-height: 1.2;
}

.search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 134px;
}

.search-row :deep(.el-button) {
  min-height: 46px;
  border: 0;
  border-radius: 0 9px 9px 0;
  background: linear-gradient(180deg, #2e91f5, #0b71df);
  font-weight: 700;
}

.search-row :deep(.el-input__wrapper) {
  min-height: 46px;
  padding-left: 16px;
  border: 1px solid #cbdcf1;
  border-right: 0;
  border-radius: 9px 0 0 9px;
  box-shadow: none;
}

.search-row :deep(.el-input__wrapper.is-focus) {
  border-color: #4c9df3;
  box-shadow: 0 0 0 2px rgba(47, 136, 255, 0.12);
}

.search-row :deep(.el-input__inner) {
  color: #16385f;
  font-size: 14px;
}

.search-row :deep(.el-input__inner::placeholder) {
  color: #7d91ae;
}

.search-prefix-icon {
  color: #173f75;
  font-size: 20px;
}

.link-button,
.inline-action,
.view-all {
  border: 0;
  background: transparent;
  color: #0068e8;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.link-button:hover,
.link-button:focus-visible,
.inline-action:hover,
.inline-action:focus-visible,
.view-all:hover:not(:disabled),
.view-all:focus-visible:not(:disabled) {
  text-decoration: underline;
  outline: none;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.95fr) minmax(300px, 0.9fr);
  gap: 16px;
}

.list-card,
.recent-card {
  padding: 14px 15px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.card-header h2 {
  display: flex;
  align-items: center;
  gap: 9px;
}

.card-header h2 .el-icon {
  color: #153f79;
  font-size: 20px;
}

.list-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.more-columns-button {
  padding: 5px 7px;
  color: #1760e8;
  font-weight: 700;
}

.column-picker :deep(.el-checkbox-group) {
  display: grid;
  gap: 4px;
}

.column-picker :deep(.el-checkbox) {
  margin-right: 0;
}

.reset-widths-button {
  width: 100%;
  margin-top: 10px;
}

.total,
.view-all {
  color: #36598d;
  font-size: 14px;
}

.view-all:disabled {
  color: #9aabc6;
  cursor: not-allowed;
}

.state-alert {
  margin-bottom: 12px;
}

.inline-action {
  margin-left: 10px;
}

.assembly-table {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
}

.assembly-table :deep(.el-table__header th) {
  background: #eff7ff;
  color: #173d7c;
  font-weight: 700;
}

.assembly-table :deep(.el-table__row) {
  cursor: pointer;
}

.link-button {
  padding: 0;
  text-align: left;
}

.link-button.subtle {
  font-weight: 600;
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
}

.table-footer p {
  margin: 0;
  color: #45628f;
  font-size: 13px;
}

.table-empty {
  display: grid;
  gap: 8px;
  justify-items: center;
  padding: 26px 10px;
  color: #6a7fa5;
}

.table-empty p {
  margin: 0;
}

.clear-search-action {
  padding: 6px 10px;
  border: 1px solid #c9dcfb;
  border-radius: 7px;
  background: #fff;
}

.recent-list {
  border-top: 1px solid #e3ebf5;
}

.recent-row {
  display: grid;
  grid-template-columns: minmax(80px, 0.8fr) minmax(110px, 1fr) minmax(74px, 0.8fr);
  align-items: center;
  width: 100%;
  min-height: 42px;
  padding: 0 6px;
  border: 0;
  border-bottom: 1px solid #e3ebf5;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.recent-row:hover,
.recent-row:focus-visible {
  background: #f3f8ff;
  outline: none;
}

.recent-row strong,
.recent-row span,
.recent-row time {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.recent-row strong {
  color: #0068e8;
}

.recent-row span,
.recent-row time {
  color: #5c7398;
}

.recent-row time {
  text-align: right;
}

.empty-recent {
  margin: 18px 0 6px;
  color: #6a7fa5;
  font-size: 14px;
  text-align: center;
}

@media (max-width: 980px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .portal-hero h1 {
    font-size: 27px;
  }

  .search-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .search-row :deep(.el-input__wrapper) {
    border-right: 1px solid #cbdcf1;
    border-radius: 9px;
  }

  .search-row :deep(.el-button) {
    min-height: 44px;
    border-radius: 9px;
  }

  .table-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

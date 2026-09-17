<template>
  <main class="assembly-portal" aria-labelledby="assembly-title">
    <section class="portal-hero">
      <nav class="breadcrumb" :aria-label="$t('page.assembly.breadcrumbLabel')">
        <RouterLink to="/dashboard">{{ $t('nav.home') }}</RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ $t('page.assembly.title') }}</span>
      </nav>
      <h1 id="assembly-title">{{ $t('page.assembly.title') }}</h1>
      <p>{{ $t('page.assembly.portalSubtitle') }}</p>
    </section>

    <section class="search-card" role="search" :aria-labelledby="'assembly-search-title'">
      <h2 id="assembly-search-title">{{ $t('page.assembly.searchTitle') }}</h2>
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
            <span aria-hidden="true">⌕</span>
          </template>
        </el-input>
        <el-button type="primary" size="large" :loading="loading" @click="submitSearch">
          {{ $t('common.search') }}
        </el-button>
      </div>
      <div class="examples" :aria-label="$t('common.examples')">
        <span>{{ $t('page.assembly.examples') }}:</span>
        <button
          v-for="example in examples"
          :key="example"
          type="button"
          :aria-label="$t('page.assembly.searchExample', { example })"
          @click="useExample(example)"
        >
          {{ example }}
        </button>
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
            <span aria-hidden="true">▣</span>
            {{ $t('page.assembly.listTitle') }}
          </h2>
          <div class="list-actions">
            <span class="total">{{ $t('page.assembly.totalAssemblies', { count: total }) }}</span>
            <details class="column-picker">
              <summary
                class="column-picker-trigger"
                :aria-label="$t('page.assembly.columnSettings')"
              >
                <span>{{ $t('page.assembly.showColumns') }}</span>
                <span class="column-count">{{ visibleColumns.length }}/{{ columnOptions.length }}</span>
              </summary>
              <div
                class="column-menu"
                role="group"
                :aria-label="$t('page.assembly.columnSettings')"
              >
                <label
                  v-for="column in columnOptions"
                  :key="column.key"
                  class="column-option"
                >
                  <input
                    type="checkbox"
                    :checked="isColumnVisible(column.key)"
                    :disabled="visibleColumns.length === 1 && isColumnVisible(column.key)"
                    @change="toggleColumn(column.key, $event.target.checked)"
                  >
                  <span>{{ $t(column.labelKey) }}</span>
                </label>
                <div class="column-menu-actions">
                  <button type="button" class="inline-action" @click="selectAllColumns">
                    {{ $t('page.assembly.selectAllColumns') }}
                  </button>
                  <button type="button" class="inline-action" @click="restoreDefaultColumns">
                    {{ $t('page.assembly.restoreDefaultColumns') }}
                  </button>
                </div>
              </div>
            </details>
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
          @row-click="openAssembly"
        >
          <el-table-column v-if="isColumnVisible('accession')" prop="accession" :label="$t('page.assembly.columns.accession')" min-width="110">
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
          <el-table-column v-if="isColumnVisible('assembly')" prop="assembly" :label="$t('page.assembly.columns.assembly')" min-width="150">
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
          <el-table-column v-if="isColumnVisible('assembly_accession')" prop="assembly_accession" :label="$t('page.assembly.columns.assemblyAccession')" min-width="180">
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
          <el-table-column v-if="isColumnVisible('assembly_level')" prop="assembly_level" :label="$t('page.assembly.columns.level')" min-width="130">
            <template #default="{ row }">
              {{ formatLevel(row.assembly_level) }}
            </template>
          </el-table-column>
          <el-table-column v-if="isColumnVisible('species')" prop="species" :label="$t('page.assembly.columns.species')" min-width="150">
            <template #default="{ row }">
              <em>{{ displayValue(row.species) }}</em>
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
            <span aria-hidden="true">◷</span>
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
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import AssemblyRecentDrawer from '@/components/assembly/AssemblyRecentDrawer.vue';
import {
  clearRecentAssemblies,
  getRecentAssemblies,
  recordRecentAssembly,
  removeRecentAssembly
} from '@/services/assemblyPreferences.js';

const RECENT_PANEL_LIMIT = 5;
const DEFAULT_PAGE_SIZE = 20;
const COLUMN_STORAGE_KEY = 'genedata_assembly_list_columns_v1';
const DEFAULT_COLUMN_KEYS = ['accession', 'assembly', 'assembly_accession', 'assembly_level', 'species'];
const ASSEMBLY_COLUMN_OPTIONS = [
  { key: 'accession', labelKey: 'page.assembly.columns.accession' },
  { key: 'assembly', labelKey: 'page.assembly.columns.assembly' },
  { key: 'assembly_accession', labelKey: 'page.assembly.columns.assemblyAccession' },
  { key: 'assembly_level', labelKey: 'page.assembly.columns.level' },
  { key: 'species', labelKey: 'page.assembly.columns.species' }
];
const emptyMark = '—';

const firstQueryValue = (value) => (Array.isArray(value) ? value[0] : value);

const normalizeText = (value) => {
  const normalized = value === null || value === undefined ? '' : String(value).trim();
  return normalized;
};

const normalizeColumnKeys = (keys) => {
  if (!Array.isArray(keys)) return [...DEFAULT_COLUMN_KEYS];
  const selected = DEFAULT_COLUMN_KEYS.filter((key) => keys.includes(key));
  return selected.length ? selected : [...DEFAULT_COLUMN_KEYS];
};

const readColumnPreference = () => {
  try {
    const raw = window.localStorage.getItem(COLUMN_STORAGE_KEY);
    return normalizeColumnKeys(raw ? JSON.parse(raw) : DEFAULT_COLUMN_KEYS);
  } catch {
    return [...DEFAULT_COLUMN_KEYS];
  }
};

const writeColumnPreference = (keys) => {
  try {
    window.localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(keys));
    return true;
  } catch {
    return false;
  }
};

export default {
  name: 'AssemblyPortalView',
  components: {
    AssemblyRecentDrawer
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
    const columnOptions = ASSEMBLY_COLUMN_OPTIONS;
    const visibleColumns = ref(readColumnPreference());
    const examples = ['IR64', '02428', 'default'];
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

    const rangeStart = computed(() => (total.value ? ((currentPage.value - 1) * pageSize.value) + 1 : 0));
    const rangeEnd = computed(() => Math.min(currentPage.value * pageSize.value, total.value));

    const displayValue = (value) => normalizeText(value) || emptyMark;

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
    const useExample = (example) => {
      searchInput.value = example;
      submitSearch();
    };
    const changePage = (page) => pushQuery(routeSearch.value, page);

    const loadRecent = () => {
      recentAssemblies.value = getRecentAssemblies();
    };

    const showStorageError = () => ElMessage.warning(t('page.assembly.preferenceSaveFailed'));

    const isColumnVisible = (key) => visibleColumns.value.includes(key);

    const setVisibleColumns = (keys) => {
      const normalized = normalizeColumnKeys(keys);
      visibleColumns.value = normalized;
      if (!writeColumnPreference(normalized)) showStorageError();
    };

    const toggleColumn = (key, checked) => {
      if (!DEFAULT_COLUMN_KEYS.includes(key)) return;
      if (checked) {
        setVisibleColumns([...visibleColumns.value, key]);
        return;
      }
      if (visibleColumns.value.length <= 1) return;
      setVisibleColumns(visibleColumns.value.filter((columnKey) => columnKey !== key));
    };

    const selectAllColumns = () => setVisibleColumns(DEFAULT_COLUMN_KEYS);

    const restoreDefaultColumns = () => setVisibleColumns(DEFAULT_COLUMN_KEYS);

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

    onMounted(loadRecent);

    return {
      assemblies,
      changePage,
      clearRecent,
      clearSearch,
      columnOptions,
      currentPage,
      displayValue,
      emptyMark,
      emptyText,
      error,
      examples,
      fetchAssemblies,
      formatLevel,
      isColumnVisible,
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
      restoreDrawerFocus,
      routeSearch,
      searchInput,
      selectAllColumns,
      submitSearch,
      restoreDefaultColumns,
      toggleColumn,
      total,
      useExample,
      visibleColumns
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
  padding: 24px 8px 14px;
}

.breadcrumb {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #4b6693;
  font-size: 14px;
  margin-bottom: 10px;
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
  font-size: 34px;
  line-height: 1.15;
}

.portal-hero p {
  margin: 8px 0 0;
  color: #46618f;
  font-size: 16px;
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
  padding: 22px 26px 18px;
  margin-bottom: 16px;
}

.search-card h2,
.card-header h2 {
  margin: 0;
  color: #0060df;
  font-size: 22px;
  line-height: 1.2;
}

.search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  gap: 12px;
  margin-top: 16px;
}

.search-row :deep(.el-button) {
  min-height: 44px;
  font-weight: 700;
  border-radius: 8px;
}

.search-row :deep(.el-input__wrapper) {
  min-height: 44px;
  border-radius: 8px;
}

.examples {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 14px;
  margin-top: 12px;
  color: #58719b;
  font-size: 13px;
}

.examples button,
.link-button,
.inline-action,
.view-all,
.column-picker-trigger {
  border: 0;
  background: transparent;
  color: #0068e8;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.examples button:hover,
.examples button:focus-visible,
.link-button:hover,
.link-button:focus-visible,
.inline-action:hover,
.inline-action:focus-visible,
.view-all:hover:not(:disabled),
.view-all:focus-visible:not(:disabled),
.column-picker-trigger:hover,
.column-picker-trigger:focus-visible {
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
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.card-header h2 {
  display: flex;
  align-items: center;
  gap: 9px;
}

.list-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.column-picker {
  position: relative;
}

.column-picker-trigger {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid #c9dcfb;
  border-radius: 8px;
  background: #fff;
  list-style: none;
}

.column-picker-trigger::-webkit-details-marker {
  display: none;
}

.column-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  min-height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #edf5ff;
  color: #31558f;
  font-size: 12px;
}

.column-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 30;
  display: grid;
  gap: 8px;
  min-width: 220px;
  padding: 12px;
  border: 1px solid #d5e2f3;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 14px 30px rgba(32, 68, 119, 0.16);
}

.column-option {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #173d7c;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.column-option input {
  width: 15px;
  height: 15px;
  accent-color: #1677e8;
}

.column-option input:disabled + span {
  color: #9aabc6;
}

.column-menu-actions {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #e3ebf5;
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
    font-size: 28px;
  }

  .search-row {
    grid-template-columns: 1fr;
  }

  .table-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

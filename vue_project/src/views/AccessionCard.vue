<template>
  <div class="accession-workbench">
    <template v-if="!routeAccession">
      <AccessionPortalHeader />
      <AccessionSearchPanel @select="openAccession" />

      <div class="shortcut-grid">
        <RecentAccessions
          :items="recentItems"
          @select="openAccession"
          @view-all="openDrawer('recent', $event)"
        />
        <FavoriteAccessions
          :items="favoriteItems"
          @select="openAccession"
          @remove="removeFavorite"
          @view-all="openDrawer('favorites', $event)"
        />
      </div>

      <p v-if="metadataError" class="metadata-error" role="alert">
        {{ $t('page.accessionPortal.metadataError') }}
        <button type="button" @click="fetchMetadata">{{ $t('page.accessionPortal.retry') }}</button>
      </p>

      <AccessionDistributionMap
        :items="geoItems"
        @select-accession="openAccession"
      />

      <AccessionListDrawer
        v-model="drawerOpen"
        :mode="drawerMode"
        :items="drawerItems"
        @closed="restoreDrawerFocus"
        @select="openAccession"
        @remove="removeDrawerItem"
        @clear="clearRecent"
      />
    </template>

    <AccessionDetailTableView v-else embedded />
  </div>
</template>

<script>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import AccessionPortalHeader from '@/components/accession/AccessionPortalHeader.vue';
import AccessionSearchPanel from '@/components/accession/AccessionSearchPanel.vue';
import RecentAccessions from '@/components/accession/RecentAccessions.vue';
import FavoriteAccessions from '@/components/accession/FavoriteAccessions.vue';
import AccessionListDrawer from '@/components/accession/AccessionListDrawer.vue';
import AccessionDistributionMap from '@/components/accession/AccessionDistributionMap.vue';
import {
  clearRecentAccessions,
  getFavoriteAccessions,
  getRecentAccessions,
  removeFavoriteAccession,
  removeRecentAccession
} from '@/services/accessionPreferences.js';
import AccessionDetailTableView from './AccessionDetailTableView.vue';

const normalizeQueryValue = (value) => {
  if (Array.isArray(value)) return value[0] ? String(value[0]).trim() : '';
  return value ? String(value).trim() : '';
};

export default {
  name: 'AccessionCard',
  components: {
    AccessionDetailTableView,
    AccessionDistributionMap,
    AccessionListDrawer,
    AccessionPortalHeader,
    AccessionSearchPanel,
    FavoriteAccessions,
    RecentAccessions
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { t } = useI18n();
    const recentPreferences = ref([]);
    const favoritePreferences = ref([]);
    const metadata = ref({});
    const metadataError = ref(false);
    const metadataLoading = ref(false);
    const drawerOpen = ref(false);
    const drawerMode = ref('recent');
    let metadataController = null;
    let drawerTrigger = null;
    const routeAccession = computed(() => (
      normalizeQueryValue(route.query.accession) || normalizeQueryValue(route.query.organism)
    ));
    const hydrateItems = (items) => items.map((item) => ({
      ...item,
      scientific_name: metadata.value[item.accession]?.scientific_name || null,
      sub_population: metadata.value[item.accession]?.sub_population || null
    }));
    const recentItems = computed(() => hydrateItems(recentPreferences.value));
    const favoriteItems = computed(() => hydrateItems(favoritePreferences.value));
    const geoItems = computed(() => Object.entries(metadata.value).map(([accession, item]) => ({
      accession,
      ...item
    })));
    const drawerItems = computed(() => (
      drawerMode.value === 'favorites'
        ? favoriteItems.value
        : recentItems.value
    ));

    const loadPreferences = () => {
      recentPreferences.value = getRecentAccessions();
      favoritePreferences.value = getFavoriteAccessions();
    };

    const fetchMetadata = async () => {
      if (metadataLoading.value) return;
      if (metadataController) metadataController.abort();
      const controller = new AbortController();
      metadataController = controller;
      metadataLoading.value = true;
      metadataError.value = false;
      try {
        const response = await axios.get('/files/query/supplementary-data/', {
          signal: controller.signal
        });
        if (metadataController !== controller) return;
        metadata.value = response.data && typeof response.data === 'object'
          ? response.data
          : {};
      } catch (error) {
        if (error?.name !== 'CanceledError' && error?.name !== 'AbortError' && !axios.isCancel(error)) {
          metadataError.value = true;
        }
      } finally {
        if (metadataController === controller) {
          metadataController = null;
          metadataLoading.value = false;
        }
      }
    };

    const openAccession = async (accession) => {
      const normalizedAccession = String(accession || '').trim();
      if (!normalizedAccession) return;
      drawerOpen.value = false;
      const query = { ...route.query, accession: normalizedAccession };
      delete query.organism;
      await router.push({ name: 'accession-card', query });
    };

    const openDrawer = (mode, trigger) => {
      drawerMode.value = mode;
      drawerTrigger = trigger || null;
      drawerOpen.value = true;
    };

    const restoreDrawerFocus = () => {
      drawerTrigger?.focus?.();
      drawerTrigger = null;
    };

    const showStorageError = () => ElMessage.warning(t('messages.accessionPreferenceSaveFailed'));

    const removeFavorite = (accession) => {
      const result = removeFavoriteAccession(accession);
      favoritePreferences.value = result.items;
      if (!result.persisted) showStorageError();
    };

    const removeDrawerItem = (accession) => {
      if (drawerMode.value === 'favorites') {
        removeFavorite(accession);
        return;
      }
      const result = removeRecentAccession(accession);
      recentPreferences.value = result.items;
      if (!result.persisted) showStorageError();
    };

    const clearRecent = () => {
      const result = clearRecentAccessions();
      recentPreferences.value = result.items;
      if (!result.persisted) showStorageError();
    };

    watch(routeAccession, (accession) => {
      if (accession) return;
      loadPreferences();
      if (!Object.keys(metadata.value).length) fetchMetadata();
    }, { immediate: true });

    onBeforeUnmount(() => {
      metadataController?.abort();
      metadataController = null;
    });

    return {
      clearRecent,
      drawerItems,
      drawerMode,
      drawerOpen,
      favoriteItems,
      fetchMetadata,
      geoItems,
      metadataError,
      openAccession,
      openDrawer,
      recentItems,
      removeDrawerItem,
      removeFavorite,
      restoreDrawerFocus,
      routeAccession
    };
  }
};
</script>

<style scoped>
.accession-workbench { min-height:calc(100vh - 160px); color:#132449; }
.shortcut-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:16px; margin-top:12px; }
.metadata-error { margin:10px 0 0; color:#b5473e; font-size:12px; text-align:center; }
.metadata-error button { padding:3px 7px; border:0; background:transparent; color:#1760e8; font:inherit; font-weight:700; cursor:pointer; }
@media (max-width:900px) {
  .shortcut-grid { grid-template-columns:1fr; }
}
</style>

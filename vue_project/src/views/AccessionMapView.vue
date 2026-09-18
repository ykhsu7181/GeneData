<template>
  <main class="accession-map-view">
    <header class="page-heading">
      <div>
        <nav class="map-breadcrumb" :aria-label="$t('page.accessionPortal.breadcrumbLabel')">
          <router-link :to="{ name: 'dashboard-home' }">{{ $t('nav.home') }}</router-link>
          <span aria-hidden="true">/</span>
          <router-link :to="{ name: 'accession-card' }">{{ $t('nav.accession') }}</router-link>
          <span aria-hidden="true">/</span>
          <span>{{ $t('page.accessionMap.title') }}</span>
        </nav>
        <h1>{{ $t('page.accessionMap.title') }}</h1>
      </div>
      <el-button :loading="loading" @click="fetchData">
        <el-icon aria-hidden="true"><Refresh /></el-icon>
        {{ $t('page.accessionMap.refreshData') }}
      </el-button>
    </header>

    <section class="filter-card" :aria-label="$t('page.accessionMap.filters')">
      <div class="filter-grid">
        <label class="filter-field">
          <span>{{ $t('page.accessionMap.accessionFilter') }}</span>
          <el-select
            v-model="selectedAccession"
            filterable
            clearable
            :placeholder="$t('page.accessionMap.searchPlaceholder')"
            @change="applyFilters"
          >
            <el-option
              v-for="item in accessionOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </label>

        <label class="filter-field">
          <span>{{ $t('page.accessionMap.regionFilter') }}</span>
          <el-input
            v-model="selectedRegion"
            clearable
            :placeholder="$t('page.accessionMap.regionPlaceholder')"
            @change="applyFilters"
            @clear="applyFilters"
          >
            <template #prefix><el-icon aria-hidden="true"><Search /></el-icon></template>
          </el-input>
        </label>

        <label class="filter-field">
          <span>{{ $t('page.accessionMap.subPopulationFilter') }}</span>
          <el-select
            v-model="selectedSubPopulations"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            :placeholder="$t('page.accessionMap.allSubPopulations')"
            @change="applyFilters"
          >
            <el-option
              v-for="subPopulation in allSubPopulations"
              :key="subPopulation"
              :label="subPopulation"
              :value="subPopulation"
            />
          </el-select>
        </label>

        <div class="filter-actions">
          <el-button :disabled="!hasActiveFilters" @click="resetFilters">
            {{ $t('page.accessionMap.resetFilters') }}
          </el-button>
        </div>
      </div>
    </section>

    <section class="map-card" :aria-label="$t('page.accessionMap.mapAriaLabel')">
      <div class="map-toolbar">
        <div class="map-actions">
          <el-select
            v-model="selectedClusterKey"
            class="region-select"
            size="small"
            :placeholder="$t('page.accessionMap.browseRegions')"
            :aria-label="$t('page.accessionMap.browseRegions')"
            @change="openClusterByKey"
          >
            <el-option
              v-for="cluster in clusterOptions"
              :key="cluster.key"
              :label="cluster.label"
              :value="cluster.key"
            />
          </el-select>
          <el-button size="small" @click="fitFilteredData">
            <el-icon aria-hidden="true"><Aim /></el-icon>
            {{ $t('page.accessionMap.fitDataView') }}
          </el-button>
          <el-button size="small" @click="showGlobalView">
            <el-icon aria-hidden="true"><FullScreen /></el-icon>
            {{ $t('page.accessionMap.globalView') }}
          </el-button>
        </div>
      </div>

      <div class="map-stage" aria-live="polite">
        <div v-if="loading" class="state-panel" role="status">
          <el-icon class="is-loading" aria-hidden="true"><Loading /></el-icon>
          <span>{{ $t('page.accessionMap.loadingGeographicData') }}</span>
        </div>
        <div v-else-if="loadError" class="state-panel" role="alert">
          <el-icon aria-hidden="true"><Warning /></el-icon>
          <span>{{ $t('page.accessionMap.loadFailed') }}</span>
          <el-button size="small" @click="fetchData">{{ $t('page.accessionMap.retry') }}</el-button>
        </div>
        <div v-else-if="!filteredData.length" class="state-panel" role="status">
          <el-icon aria-hidden="true"><Location /></el-icon>
          <span>{{ $t('page.accessionMap.noResults') }}</span>
          <el-button v-if="hasActiveFilters" size="small" @click="resetFilters">
            {{ $t('page.accessionMap.resetFilters') }}
          </el-button>
        </div>
        <div
          v-show="!loading && !loadError && filteredData.length"
          ref="mapContainer"
          class="echarts-map"
          role="img"
          tabindex="0"
          :aria-label="$t('page.accessionMap.mapAriaLabelWithCount', {
            count: filteredMetrics.mappedAccessions,
            regions: filteredMetrics.geographicRegions
          })"
        />
      </div>

      <footer class="map-footer">
        <div class="size-legend" :aria-label="$t('page.accessionMap.bubbleLegend')">
          <strong>{{ $t('page.accessionMap.bubbleColor') }}</strong>
          <span><i class="bubble cluster-single" />1</span>
          <span><i class="bubble cluster-small" />2–5</span>
          <span><i class="bubble cluster-medium" />6–10</span>
          <span><i class="bubble cluster-large" />11–19</span>
          <span><i class="bubble cluster-extra-large" />20–50</span>
          <span><i class="bubble cluster-extra-large" />51–100</span>
          <span><i class="bubble cluster-extreme" />&gt;100</span>
        </div>
      </footer>
    </section>

    <section class="metrics" :aria-label="$t('page.accessionMap.dataOverview')">
      <article>
        <strong>{{ baseMetrics.totalAccessions }}</strong>
        <span>{{ $t('page.accessionMap.totalGermplasm') }}</span>
      </article>
      <article>
        <strong>{{ baseMetrics.mappedAccessions }}</strong>
        <span>{{ $t('page.accessionMap.locatedGermplasm') }}</span>
      </article>
      <article>
        <strong>{{ baseMetrics.unmappedAccessions }}</strong>
        <span>{{ $t('page.accessionMap.unmappedGermplasm') }}</span>
      </article>
      <article>
        <strong>{{ filteredMetrics.geographicRegions }}</strong>
        <span>{{ $t('page.accessionMap.geographicRegions') }}</span>
      </article>
    </section>

    <AccessionListDrawer
      v-model="drawerOpen"
      mode="cluster"
      :items="drawerItems"
      @select="openAccession"
    />
  </main>
</template>

<script>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import * as echarts from 'echarts';
import {
  Aim,
  FullScreen,
  Loading,
  Location,
  Refresh,
  Search,
  Warning
} from '@element-plus/icons-vue';
import AccessionListDrawer from '@/components/accession/AccessionListDrawer.vue';
import { worldMapData } from '@/data/worldMapData.js';
import {
  GEOGRAPHIC_GRID_SIZE,
  aggregateGeographicItems,
  buildGeographicMetrics,
  filterGeographicItems,
  getGeographicClusterColor,
  getGeographicViewport,
  normalizeGeographicItems,
  normalizeSubPopulation
} from '@/services/accessionGeography.mjs';
import {
  parseAccessionMapQuery,
  serializeAccessionMapQuery
} from '@/services/accessionMapRoute.mjs';

export default {
  name: 'AccessionMapView',
  components: {
    AccessionListDrawer,
    Aim,
    FullScreen,
    Loading,
    Location,
    Refresh,
    Search,
    Warning
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { t } = useI18n();
    const loading = ref(true);
    const loadError = ref(false);
    const supplementaryData = ref({});
    const selectedAccession = ref('');
    const selectedRegion = ref('');
    const selectedSubPopulations = ref([]);
    const mapContainer = ref(null);
    const mapInstance = ref(null);
    const drawerOpen = ref(false);
    const drawerItems = ref([]);
    const selectedClusterKey = ref('');
    let resizeObserver = null;

    const geographicItems = computed(() => normalizeGeographicItems(supplementaryData.value));
    const accessionOptions = computed(() => (
      geographicItems.value.map((item) => item.accession).sort((a, b) => a.localeCompare(b))
    ));
    const allSubPopulations = computed(() => (
      Array.from(new Set(geographicItems.value.map((item) => item.sub_population)))
        .sort((a, b) => a.localeCompare(b))
    ));
    const baseMetrics = computed(() => buildGeographicMetrics(geographicItems.value));
    const filteredData = computed(() => filterGeographicItems(geographicItems.value, {
      accession: selectedAccession.value,
      region: selectedRegion.value,
      subPopulations: selectedSubPopulations.value.length ? selectedSubPopulations.value : null
    }));
    const filteredMetrics = computed(() => buildGeographicMetrics(filteredData.value));
    const clusters = computed(() => aggregateGeographicItems(filteredData.value, GEOGRAPHIC_GRID_SIZE));
    const clusterOptions = computed(() => clusters.value
      .map((cluster) => {
        const namedLocations = cluster.accessions
          .map((item) => item.country || item.region)
          .filter(Boolean);
        const location = namedLocations[0]
          || `${cluster.latitude.toFixed(1)}°, ${cluster.longitude.toFixed(1)}°`;
        return {
          ...cluster,
          label: t('page.accessionMap.regionOption', { location, count: cluster.count })
        };
      })
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)));
    const hasActiveFilters = computed(() => Boolean(
      selectedAccession.value || selectedRegion.value || selectedSubPopulations.value.length
    ));

    const readRouteFilters = () => {
      const filters = parseAccessionMapQuery(route.query);
      selectedAccession.value = filters.accession;
      selectedRegion.value = filters.region;
      selectedSubPopulations.value = filters.subPopulations.map(normalizeSubPopulation);
    };

    const syncRouteFilters = async () => {
      const query = serializeAccessionMapQuery({
        accession: selectedAccession.value,
        region: selectedRegion.value,
        subPopulations: selectedSubPopulations.value
      });
      if (JSON.stringify(route.query) !== JSON.stringify(query)) {
        await router.replace({ name: 'accession-map', query });
      }
    };

    const setViewport = (viewport) => {
      if (!mapInstance.value) return;
      mapInstance.value.setOption({ geo: viewport });
    };

    const fitFilteredData = () => setViewport(getGeographicViewport(filteredData.value));
    const showGlobalView = () => setViewport({ center: [0, 15], zoom: 1.05 });

    const openCluster = (cluster) => {
      drawerItems.value = [...cluster.accessions].sort((a, b) => a.accession.localeCompare(b.accession));
      drawerOpen.value = true;
    };

    const openClusterByKey = (key) => {
      const cluster = clusters.value.find((item) => item.key === key);
      if (cluster) openCluster(cluster);
      nextTick(() => { selectedClusterKey.value = ''; });
    };

    const openAccession = async (accession) => {
      drawerOpen.value = false;
      const mapQuery = serializeAccessionMapQuery({
        accession: selectedAccession.value,
        region: selectedRegion.value,
        subPopulations: selectedSubPopulations.value
      });
      const returnTo = router.resolve({ name: 'accession-map', query: mapQuery }).fullPath;
      await router.push({
        name: 'accession-card',
        query: { accession, return_to: returnTo }
      });
    };

    const buildMapOption = () => {
      const viewport = getGeographicViewport(filteredData.value);
      const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false;
      return {
        backgroundColor: '#f7faff',
        tooltip: {
          trigger: 'item',
          confine: true,
          renderMode: 'richText',
          formatter: ({ data }) => data
            ? t('page.accessionMap.clusterTooltip', {
              count: data.cluster.count,
              accessions: data.cluster.accessions.slice(0, 3).map((item) => item.accession).join(', ')
            })
            : ''
        },
        geo: {
          map: 'world',
          roam: true,
          center: viewport.center,
          zoom: viewport.zoom,
          scaleLimit: { min: 1, max: 12 },
          left: 12,
          right: 12,
          top: 12,
          bottom: 12,
          itemStyle: { areaColor: '#edf4fc', borderColor: '#bfd2e8', borderWidth: 0.8 },
          emphasis: { itemStyle: { areaColor: '#dceafb' }, label: { show: false } },
          select: { disabled: true }
        },
        series: [{
          type: 'effectScatter',
          coordinateSystem: 'geo',
          data: clusters.value.map((cluster) => ({
            name: cluster.key,
            value: [cluster.longitude, cluster.latitude, cluster.count],
            itemStyle: { color: getGeographicClusterColor(cluster.count) },
            cluster
          })),
          symbolSize: ({ 2: count }) => Math.min(34, 10 + Math.sqrt(count) * 4),
          showEffectOn: 'emphasis',
          rippleEffect: { scale: 2.2, brushType: 'stroke' },
          itemStyle: { borderColor: '#fff', borderWidth: 1.5, opacity: 0.9 },
          label: { show: false },
          emphasis: { scale: 1.15 },
          animation: !reducedMotion,
          animationDuration: reducedMotion ? 0 : 450
        }]
      };
    };

    const handleMapClick = ({ data }) => {
      if (data?.cluster) openCluster(data.cluster);
    };

    const renderMap = async () => {
      if (loading.value || loadError.value || !filteredData.value.length) return;
      await nextTick();
      if (!mapContainer.value) return;
      if (!mapInstance.value) {
        echarts.registerMap('world', worldMapData);
        mapInstance.value = echarts.init(mapContainer.value);
        mapInstance.value.on('click', handleMapClick);
        resizeObserver = new ResizeObserver(() => mapInstance.value?.resize());
        resizeObserver.observe(mapContainer.value);
      }
      mapInstance.value.setOption(buildMapOption(), true);
    };

    const applyFilters = async () => {
      await syncRouteFilters();
      await renderMap();
    };

    const resetFilters = async () => {
      selectedAccession.value = '';
      selectedRegion.value = '';
      selectedSubPopulations.value = [];
      await applyFilters();
    };

    const fetchData = async () => {
      loading.value = true;
      loadError.value = false;
      try {
        const response = await axios.get('/files/query/supplementary-data/');
        supplementaryData.value = response.data && typeof response.data === 'object'
          ? response.data
          : {};
      } catch (error) {
        console.error('Failed to load geographic data:', error);
        loadError.value = true;
      } finally {
        loading.value = false;
      }
      await renderMap();
    };

    watch(
      () => route.query,
      async () => {
        readRouteFilters();
        await renderMap();
      }
    );

    onMounted(async () => {
      readRouteFilters();
      await syncRouteFilters();
      await fetchData();
    });

    onUnmounted(() => {
      resizeObserver?.disconnect();
      if (mapInstance.value) {
        mapInstance.value.off('click', handleMapClick);
        mapInstance.value.dispose();
      }
    });

    return {
      accessionOptions,
      allSubPopulations,
      applyFilters,
      baseMetrics,
      clusterOptions,
      drawerItems,
      drawerOpen,
      fetchData,
      filteredData,
      filteredMetrics,
      fitFilteredData,
      hasActiveFilters,
      loadError,
      loading,
      mapContainer,
      openAccession,
      openClusterByKey,
      resetFilters,
      selectedAccession,
      selectedClusterKey,
      selectedRegion,
      selectedSubPopulations,
      showGlobalView
    };
  }
};
</script>

<style scoped>
.accession-map-view {
  width: min(1440px, calc(100% - 40px));
  margin: 0 auto;
  padding: 4px 0 48px;
  color: #12335f;
}

.page-heading {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
  margin-bottom: 18px;
}

.map-breadcrumb { display:flex; align-items:center; gap:8px; margin-bottom:8px; color:#76849a; font-size:13px; }
.map-breadcrumb a { color:#3974c7; text-decoration:none; }
.map-breadcrumb a:hover,.map-breadcrumb a:focus-visible { color:#086cde; text-decoration:underline; }
.page-heading h1 { margin:0; color:#102f61; font-size:30px; line-height:1.12; letter-spacing:-.03em; }

.filter-card,
.map-card,
.metrics {
  border: 1px solid #d6e4f4;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 5px 18px rgba(23, 73, 128, 0.06);
}

.filter-card { margin-bottom: 16px; padding: 18px; }
.filter-grid { display: grid; grid-template-columns: 1.15fr 1fr 1.15fr auto; gap: 14px; align-items: end; }
.filter-field { display: grid; gap: 7px; min-width: 0; color: #284c77; font-size: 13px; font-weight: 650; }
.filter-actions { display: flex; }

.map-card { overflow: hidden; }
.map-toolbar { display: flex; justify-content: flex-end; gap: 20px; align-items: center; padding: 16px 18px; border-bottom: 1px solid #e1ebf6; }
.map-actions { display: flex; flex-shrink: 0; align-items: center; }
.region-select { width: 230px; margin-right: 10px; }
.map-stage { position: relative; min-height: clamp(460px, 62vh, 680px); background: #f7faff; }
.echarts-map { width: 100%; height: clamp(460px, 62vh, 680px); }
.state-panel { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 12px; color: #637b9a; text-align: center; }
.state-panel > .el-icon { font-size: 30px; color: #287fdc; }
.map-footer { display: flex; justify-content: flex-start; gap: 18px; align-items: center; min-height: 50px; padding: 8px 18px; border-top: 1px solid #e1ebf6; color: #637b9a; font-size: 12px; }
.size-legend { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
.size-legend span { display: inline-flex; gap: 6px; align-items: center; }
.bubble { display: inline-block; width: 11px; height: 11px; border-radius: 50%; }
.cluster-single { background: #1677e8; }
.cluster-small,.cluster-large { background: #f07818; }
.cluster-medium { background: #7c3aed; }
.cluster-extra-large { background: #eab308; }
.cluster-extreme { background: #ec4899; }

.metrics { display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 16px; overflow: hidden; }
.metrics article { display: grid; gap: 3px; padding: 18px 22px; border-right: 1px solid #e1ebf6; }
.metrics article:last-child { border-right: 0; }
.metrics strong { color: #0b54ac; font-size: 24px; }
.metrics span { color: #647b99; font-size: 13px; }

@media (max-width: 960px) {
  .filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .metrics article:nth-child(2) { border-right: 0; }
  .metrics article:nth-child(-n+2) { border-bottom: 1px solid #e1ebf6; }
}

@media (max-width: 640px) {
  .accession-map-view { width: min(100% - 24px, 1440px); padding-top: 4px; }
  .page-heading { align-items: flex-start; }
  .page-heading h1 { font-size: 26px; }
  .page-heading > .el-button { padding-inline: 9px; }
  .filter-grid { grid-template-columns: 1fr; }
  .filter-actions .el-button { width: 100%; }
  .map-toolbar { align-items: flex-start; flex-direction: column; }
  .map-actions { width: 100%; }
  .region-select { flex: 1; width: auto; min-width: 0; }
  .map-actions .el-button { flex: 1; }
  .map-stage,
  .echarts-map { min-height: 430px; height: 56vh; }
  .map-footer { align-items: flex-start; flex-direction: column; padding-block: 12px; }
  .metrics { grid-template-columns: 1fr; }
  .metrics article { border-right: 0; border-bottom: 1px solid #e1ebf6; }
  .metrics article:last-child { border-bottom: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .accession-map-view :deep(*) { scroll-behavior: auto !important; }
}
</style>

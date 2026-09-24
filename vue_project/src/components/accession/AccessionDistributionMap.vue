<template>
  <section class="distribution-card" :aria-labelledby="titleId">
    <header class="card-heading">
      <div>
        <h2 :id="titleId"><el-icon aria-hidden="true"><Location /></el-icon>{{ $t('page.accessionPortal.geographicDistribution') }}</h2>
      </div>
      <router-link class="full-map-link" to="/accession-map">
        {{ $t('page.accessionPortal.viewFullMap') }}
        <span aria-hidden="true">→</span>
      </router-link>
    </header>

    <div v-if="mappedAccessions" class="map-stage">
      <div
        ref="mapContainer"
        class="distribution-map"
        role="img"
        :aria-label="$t('page.accessionPortal.mapAriaLabel', { mapped: mappedAccessions, total: totalAccessions })"
      ></div>
      <div class="map-controls">
        <button
          type="button"
          class="map-control-button"
          :aria-label="$t('page.accessionPortal.fitDataView')"
          @click="resetDataView"
        >
          <el-icon aria-hidden="true"><Location /></el-icon>
          {{ $t('page.accessionPortal.fitDataView') }}
        </button>
        <button
          type="button"
          class="map-control-button"
          :aria-label="$t('page.accessionPortal.globalView')"
          @click="resetGlobalView"
        >
          <el-icon aria-hidden="true"><FullScreen /></el-icon>
          {{ $t('page.accessionPortal.globalView') }}
        </button>
      </div>
      <AccessionClusterPanel
        v-model="clusterPanelOpen"
        :items="clusterPanelItems"
        @select="$emit('select-accession', $event)"
      />
    </div>
    <p v-else class="map-empty">{{ $t('page.accessionPortal.mapEmpty') }}</p>

    <footer class="map-footer">
      <div class="legend" :aria-label="$t('page.accessionPortal.numberOfAccessions')">
        <strong>{{ $t('page.accessionPortal.numberOfAccessions') }}:</strong>
        <span><i class="dot cluster-single"></i>1</span>
        <span><i class="dot cluster-small"></i>2–5</span>
        <span><i class="dot cluster-medium"></i>6–10</span>
        <span><i class="dot cluster-large"></i>11–19</span>
        <span><i class="dot cluster-extra-large"></i>20–50</span>
        <span><i class="dot cluster-very-large"></i>51–100</span>
        <span><i class="dot cluster-extreme"></i>&gt;100</span>
      </div>
      <div v-if="topRegions.length" class="top-regions">
        <strong>{{ $t('page.accessionPortal.topRegions') }}:</strong>
        <span v-for="region in topRegions" :key="region.name">{{ region.name }} {{ region.count }}</span>
      </div>
    </footer>
  </section>
</template>

<script>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { FullScreen, Location } from '@element-plus/icons-vue';
import * as echarts from 'echarts';
import AccessionClusterPanel from '@/components/accession/AccessionClusterPanel.vue';
import { worldMapData } from '@/data/worldMapData.js';
import {
  aggregateGeographicItems,
  buildGeographicMetrics,
  GEOGRAPHIC_GRID_SIZE,
  getGeographicViewport,
  getGeographicClusterColor,
  getTopGeographicRegions
} from '@/services/accessionGeography.mjs';

const getBubbleSize = (count) => {
  if (count <= 10) return 8;
  if (count <= 50) return 13;
  if (count <= 100) return 18;
  return 24;
};

export default {
  name: 'AccessionDistributionMap',
  components: { AccessionClusterPanel, FullScreen, Location },
  props: {
    items: { type: Array, default: () => [] }
  },
  emits: ['select-accession'],
  setup(props) {
    const { t } = useI18n();
    const titleId = 'accession-distribution-title';
    const mapContainer = ref(null);
    const clusterPanelOpen = ref(false);
    const clusterPanelItems = ref([]);
    let mapInstance = null;

    const metrics = computed(() => buildGeographicMetrics(props.items));
    const totalAccessions = computed(() => metrics.value.totalAccessions);
    const mappedAccessions = computed(() => metrics.value.mappedAccessions);
    const topRegions = computed(() => getTopGeographicRegions(props.items));
    const dataViewport = computed(() => getGeographicViewport(props.items));
    const clusters = computed(() => (
      aggregateGeographicItems(props.items, GEOGRAPHIC_GRID_SIZE)
    ));

    const tooltipFormatter = (params) => {
      const cluster = params.data?.cluster;
      if (!cluster) return '';
      if (cluster.count === 1) {
        const item = cluster.accessions[0];
        return [
          item.accession,
          `<em>${item.scientific_name || '—'}</em>`,
          item.sub_population || '—',
          item.country || item.region || '—',
          `${item.latitude.toFixed(2)}, ${item.longitude.toFixed(2)}`
        ].join('<br>');
      }
      const names = cluster.accessions.slice(0, 5).map((item) => item.accession);
      const more = cluster.count > 5 ? [`+${cluster.count - 5} ${t('page.accessionPortal.moreItems')}`] : [];
      return [
        t('page.accessionPortal.clusterAccessions'),
        `${cluster.count} ${t('page.accessionPortal.accessions')}`,
        ...names,
        ...more
      ].join('<br>');
    };

    const updateMap = () => {
      if (!mapInstance) return;
      const data = clusters.value.map((cluster) => ({
        name: cluster.count === 1 ? cluster.accessions[0].accession : cluster.key,
        value: [cluster.longitude, cluster.latitude, cluster.count],
        symbolSize: getBubbleSize(cluster.count),
        itemStyle: { color: getGeographicClusterColor(cluster.count) },
        cluster
      }));

      mapInstance.setOption({
        animationDuration: 400,
        backgroundColor: '#eef6ff',
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(255,255,255,.97)',
          borderColor: '#d9e6f6',
          textStyle: { color: '#18335f', fontSize: 12 },
          formatter: tooltipFormatter
        },
        geo: {
          map: 'world',
          center: dataViewport.value.center,
          zoom: dataViewport.value.zoom,
          roam: true,
          scaleLimit: { min: 1, max: 6 },
          itemStyle: {
            areaColor: '#dceafa',
            borderColor: '#ffffff',
            borderWidth: .8
          },
          emphasis: {
            itemStyle: { areaColor: '#c9def6' },
            label: { show: false }
          },
          label: { show: false }
        },
        series: [{
          type: 'scatter',
          coordinateSystem: 'geo',
          data,
          itemStyle: {
            opacity: .86,
            borderColor: '#ffffff',
            borderWidth: 1.5,
            shadowBlur: 8,
            shadowColor: 'rgba(47,136,255,.28)'
          },
          emphasis: {
            scale: 1.25
          },
          label: { show: false }
        }]
      }, true);
    };

    const resizeMap = () => mapInstance?.resize();
    const handleMapClick = (params) => {
      const cluster = params.data?.cluster;
      if (!cluster) return;
      clusterPanelItems.value = [...cluster.accessions]
        .sort((a, b) => a.accession.localeCompare(b.accession));
      clusterPanelOpen.value = true;
    };

    const resetGlobalView = () => {
      mapInstance?.setOption({ geo: { center: [0, 15], zoom: 1.05 } });
    };

    const resetDataView = () => {
      mapInstance?.setOption({
        geo: {
          center: dataViewport.value.center,
          zoom: dataViewport.value.zoom
        }
      });
    };

    const initMap = async () => {
      await nextTick();
      if (!mapContainer.value || mapInstance || !mappedAccessions.value) return;
      echarts.registerMap('world', worldMapData);
      mapInstance = echarts.init(mapContainer.value);
      mapInstance.on('click', handleMapClick);
      window.addEventListener('resize', resizeMap);
      updateMap();
    };

    onMounted(initMap);
    watch(clusters, async () => {
      if (!mappedAccessions.value) {
        if (mapInstance) {
          mapInstance.off('click', handleMapClick);
          window.removeEventListener('resize', resizeMap);
          mapInstance.dispose();
          mapInstance = null;
        }
        return;
      }
      if (!mapInstance) await initMap();
      else updateMap();
    });

    onUnmounted(() => {
      window.removeEventListener('resize', resizeMap);
      if (mapInstance) {
        mapInstance.off('click', handleMapClick);
        mapInstance.dispose();
        mapInstance = null;
      }
    });

    return {
      clusterPanelItems,
      clusterPanelOpen,
      mapContainer,
      mappedAccessions,
      resetDataView,
      resetGlobalView,
      titleId,
      topRegions,
      totalAccessions
    };
  }
};
</script>

<style scoped>
.distribution-card { margin-top:14px; padding:14px 12px 12px; border:1px solid rgba(202,220,240,.9); border-radius:12px; background:rgba(255,255,255,.97); box-shadow:0 10px 28px rgba(49,93,147,.06); }
.card-heading { display:flex; align-items:center; justify-content:space-between; gap:18px; margin:0 5px 10px; }
.card-heading h2 { display:flex; align-items:center; gap:8px; margin:0; color:#086cde; font-size:17px; }
.card-heading h2 .el-icon { color:#153f79; font-size:20px; }
.full-map-link { display:inline-flex; align-items:center; gap:6px; min-height:34px; padding:0 12px; flex:0 0 auto; border:1px solid #bed8fb; border-radius:8px; color:#0874e9; background:#f7fbff; font-size:12px; font-weight:700; text-decoration:none; }
.full-map-link:hover,.full-map-link:focus-visible { border-color:#78acef; background:#edf6ff; outline:none; }
.map-stage { position:relative; }
.distribution-map,.map-empty { height:240px; border-radius:9px; background:#eef6ff; }
.map-empty { display:grid; place-items:center; margin:0; color:#8291a8; font-size:13px; }
.map-controls { position:absolute; top:10px; right:10px; z-index:2; display:flex; gap:6px; }
.map-control-button { display:inline-flex; align-items:center; gap:5px; min-height:30px; padding:0 9px; border:1px solid #cbdcf1; border-radius:7px; color:#315b94; background:rgba(255,255,255,.94); font:inherit; font-size:11px; font-weight:700; cursor:pointer; box-shadow:0 4px 12px rgba(32,68,119,.1); }
.map-control-button:hover,.map-control-button:focus-visible { border-color:#78acef; color:#086cde; outline:none; }
.map-footer { display:grid; grid-template-columns:1fr; align-items:start; gap:8px; margin:9px 5px 0; color:#526d94; font-size:11px; }
.top-regions strong { color:#183c6e; }
.legend { display:flex; align-items:center; flex-wrap:wrap; gap:16px; }
.legend strong { color:#183c6e; }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.top-regions { grid-column:1 / -1; display:flex; align-items:center; flex-wrap:wrap; gap:8px 14px; padding-top:7px; border-top:1px solid #e5edf7; }
.dot { display:inline-block; width:11px; height:11px; border-radius:50%; }
.cluster-single { background:#1677e8; }
.cluster-small { background:#16a34a; }
.cluster-large { background:#f07818; }
.cluster-medium { background:#7c3aed; }
.cluster-extra-large { background:#eab308; }
.cluster-very-large { background:#ef4444; }
.cluster-extreme { background:#ec4899; }
@media (max-width:700px) {
  .card-heading { align-items:flex-start; }
  .full-map-link { padding:0 9px; }
  .map-footer { grid-template-columns:1fr; }
  .map-footer,.legend { align-items:flex-start; flex-wrap:wrap; }
  .top-regions { grid-column:auto; }
  .distribution-map,.map-empty { height:190px; }
}
</style>

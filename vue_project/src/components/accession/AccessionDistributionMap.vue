<template>
  <section class="distribution-card" :aria-labelledby="titleId">
    <header class="card-heading">
      <h2 :id="titleId"><span aria-hidden="true">⌖</span>{{ $t('page.accessionPortal.geographicDistribution') }}</h2>
      <router-link to="/accession-map">{{ $t('page.accessionPortal.viewFullMap') }} →</router-link>
    </header>

    <div
      v-if="mappedAccessions"
      ref="mapContainer"
      class="distribution-map"
      role="img"
      :aria-label="$t('page.accessionPortal.mapAriaLabel', { mapped: mappedAccessions, total: totalAccessions })"
    ></div>
    <p v-else class="map-empty">{{ $t('page.accessionPortal.mapEmpty') }}</p>

    <footer class="map-footer">
      <div class="legend" :aria-label="$t('page.accessionPortal.numberOfAccessions')">
        <strong>{{ $t('page.accessionPortal.numberOfAccessions') }}:</strong>
        <span><i class="dot dot-s"></i>1-10</span>
        <span><i class="dot dot-m"></i>11-50</span>
        <span><i class="dot dot-l"></i>51-100</span>
        <span><i class="dot dot-xl"></i>&gt;100</span>
      </div>
      <span aria-live="polite">{{ $t('page.accessionPortal.mappedOfTotal', { mapped: mappedAccessions, total: totalAccessions }) }}</span>
    </footer>
  </section>
</template>

<script>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import * as echarts from 'echarts';
import { worldMapData } from '@/data/worldMapData.js';

const GRID_SIZE = 2;

const isValidCoordinate = (longitude, latitude) => (
  longitude !== null &&
  latitude !== null &&
  Number.isFinite(longitude) &&
  Number.isFinite(latitude) &&
  longitude >= -180 &&
  longitude <= 180 &&
  latitude >= -90 &&
  latitude <= 90
);

const getBubbleSize = (count) => {
  if (count <= 10) return 8;
  if (count <= 50) return 13;
  if (count <= 100) return 18;
  return 24;
};

export default {
  name: 'AccessionDistributionMap',
  props: {
    items: { type: Array, default: () => [] }
  },
  emits: ['select', 'select-cluster'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const titleId = 'accession-distribution-title';
    const mapContainer = ref(null);
    let mapInstance = null;

    const totalAccessions = computed(() => (
      new Set(props.items.map((item) => item.accession).filter(Boolean)).size
    ));

    const validItems = computed(() => props.items
      .map((item) => ({
        ...item,
        longitude: Number(item.longitude),
        latitude: Number(item.latitude)
      }))
      .filter((item) => item.accession && isValidCoordinate(item.longitude, item.latitude)));

    const mappedAccessions = computed(() => (
      new Set(validItems.value.map((item) => item.accession)).size
    ));

    const clusters = computed(() => {
      const maxGridX = Math.ceil(360 / GRID_SIZE) - 1;
      const maxGridY = Math.ceil(180 / GRID_SIZE) - 1;
      const grouped = new Map();

      validItems.value.forEach((item) => {
        const gridX = Math.min(maxGridX, Math.floor((item.longitude + 180) / GRID_SIZE));
        const gridY = Math.min(maxGridY, Math.floor((item.latitude + 90) / GRID_SIZE));
        const key = `${gridX}:${gridY}`;
        if (!grouped.has(key)) grouped.set(key, []);
        grouped.get(key).push(item);
      });

      return Array.from(grouped.entries()).map(([key, accessions]) => {
        const longitude = accessions.reduce((sum, item) => sum + item.longitude, 0) / accessions.length;
        const latitude = accessions.reduce((sum, item) => sum + item.latitude, 0) / accessions.length;
        return {
          key,
          accessions,
          count: accessions.length,
          longitude,
          latitude
        };
      });
    });

    const tooltipFormatter = (params) => {
      const cluster = params.data?.cluster;
      if (!cluster) return '';
      if (cluster.count === 1) {
        const item = cluster.accessions[0];
        return [
          item.accession,
          item.scientific_name || '—',
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
          center: [62, 19],
          zoom: 1.35,
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
            color: '#2f88ff',
            opacity: .86,
            borderColor: '#ffffff',
            borderWidth: 1.5,
            shadowBlur: 8,
            shadowColor: 'rgba(47,136,255,.28)'
          },
          emphasis: {
            scale: 1.25
          }
        }]
      }, true);
    };

    const resizeMap = () => mapInstance?.resize();
    const handleMapClick = (params) => {
      const cluster = params.data?.cluster;
      if (!cluster) return;
      if (cluster.count === 1) {
        emit('select', cluster.accessions[0].accession);
        return;
      }
      emit('select-cluster', cluster.accessions);
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
      mapContainer,
      mappedAccessions,
      titleId,
      totalAccessions
    };
  }
};
</script>

<style scoped>
.distribution-card { margin-top:14px; padding:14px 12px 12px; border:1px solid rgba(202,220,240,.9); border-radius:12px; background:rgba(255,255,255,.97); box-shadow:0 10px 28px rgba(49,93,147,.06); }
.card-heading { display:flex; align-items:center; justify-content:space-between; gap:14px; margin:0 5px 9px; }
.card-heading h2 { display:flex; align-items:center; gap:9px; margin:0; color:#086cde; font-size:18px; }
.card-heading h2 span { color:#153f79; font-size:24px; }
.card-heading a { color:#0874e9; font-size:12px; font-weight:700; text-decoration:none; }
.distribution-map,.map-empty { height:240px; border-radius:9px; background:#eef6ff; }
.map-empty { display:grid; place-items:center; margin:0; color:#8291a8; font-size:13px; }
.map-footer { display:flex; align-items:center; justify-content:space-between; gap:18px; margin:8px 5px 0; color:#526d94; font-size:11px; }
.legend { display:flex; align-items:center; flex-wrap:wrap; gap:16px; }
.legend strong { color:#183c6e; }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.dot { display:inline-block; border-radius:50%; background:#65aaf5; }
.dot-s { width:8px; height:8px; }
.dot-m { width:13px; height:13px; }
.dot-l { width:18px; height:18px; }
.dot-xl { width:22px; height:22px; background:#2f88ff; }
@media (max-width:700px) {
  .map-footer,.legend { align-items:flex-start; flex-wrap:wrap; }
  .distribution-map,.map-empty { height:190px; }
}
</style>

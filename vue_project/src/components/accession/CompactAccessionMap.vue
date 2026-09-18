<template>
  <div
    ref="mapContainer"
    class="compact-accession-map"
    role="img"
    :aria-label="$t('page.accessionDetail.mapAriaLabel', { accession })"
  ></div>
</template>

<script>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import * as echarts from 'echarts';
import { worldMapData } from '@/data/worldMapData.js';

export default {
  name: 'CompactAccessionMap',
  props: {
    accession: { type: String, required: true },
    latitude: { type: Number, required: true },
    longitude: { type: Number, required: true }
  },
  setup(props) {
    const { t } = useI18n();
    const mapContainer = ref(null);
    let mapInstance = null;

    const updateMap = () => {
      if (!mapInstance) return;
      const longitude = Number(props.longitude);
      const latitude = Number(props.latitude);
      if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return;

      mapInstance.setOption({
        animationDuration: 500,
        backgroundColor: '#eef6ff',
        aria: {
          enabled: true,
          description: t('page.accessionDetail.mapAriaLabel', { accession: props.accession })
        },
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(255, 255, 255, .96)',
          borderColor: '#d9e6f6',
          textStyle: { color: '#18335f', fontSize: 12 },
          formatter: () => `${props.accession}<br>${t('page.accessionDetail.coordinates')}：${latitude.toFixed(2)}, ${longitude.toFixed(2)}`
        },
        geo: {
          map: 'world',
          center: [longitude, latitude],
          zoom: 4,
          roam: true,
          scaleLimit: { min: 1, max: 12 },
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
          type: 'effectScatter',
          coordinateSystem: 'geo',
          data: [{ name: props.accession, value: [longitude, latitude] }],
          symbolSize: 12,
          rippleEffect: { scale: 3, brushType: 'stroke' },
          itemStyle: { color: '#176ee8', shadowBlur: 8, shadowColor: 'rgba(23, 110, 232, .45)' },
          label: {
            show: true,
            formatter: props.accession,
            position: 'top',
            distance: 8,
            color: '#12366d',
            fontSize: 12,
            fontWeight: 700
          },
          zlevel: 2
        }]
      }, true);
    };

    const resizeMap = () => mapInstance?.resize();

    onMounted(async () => {
      await nextTick();
      if (!mapContainer.value) return;
      echarts.registerMap('world', worldMapData);
      mapInstance = echarts.init(mapContainer.value);
      updateMap();
      window.addEventListener('resize', resizeMap);
    });

    watch(() => [props.accession, props.latitude, props.longitude], updateMap);

    onUnmounted(() => {
      window.removeEventListener('resize', resizeMap);
      mapInstance?.dispose();
      mapInstance = null;
    });

    return { mapContainer };
  }
};
</script>

<style scoped>
.compact-accession-map {
  width:100%;
  height:210px;
  overflow:hidden;
  border:1px solid #e1ebf7;
  border-radius:10px;
  background:#eef6ff;
}
</style>

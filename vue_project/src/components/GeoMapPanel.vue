<template>
  <section class="geo-panel">
    <div class="geo-header">
      <div class="geo-heading">
        <p class="geo-kicker">Geographic distribution</p>
        <h3>地理分布</h3>
        <p class="geo-description">
          基于已有经纬度信息，展示材料采集的空间分布情况与重点区域聚集度。
        </p>
      </div>
    </div>

    <div v-if="points.length" class="geo-layout">
      <div class="geo-map-shell">
        <div class="geo-scale-legend" aria-label="Geographic distribution scale">
          <div
            v-for="bucket in legendBuckets"
            :key="bucket.label"
            class="geo-scale-row"
          >
            <i
              class="geo-scale-dot"
              :style="{
                backgroundColor: bucket.color,
                width: `${bucket.size}px`,
                height: `${bucket.size}px`
              }"
            ></i>
            <span>{{ bucket.label }}</span>
          </div>
        </div>
        <div ref="mapRef" class="geo-map"></div>
      </div>

      <aside class="geo-side-panel">
        <div class="geo-summary-card">
          <span>总计</span>
          <strong>{{ totalPointCount }}</strong>
          <em>地理点位数</em>
        </div>

        <div class="geo-list-head">
          <span>点位</span>
          <span>材料数</span>
        </div>

        <div class="geo-point-list">
          <button
            v-for="point in topPoints"
            :key="`${point.region}-${point.latitude}-${point.longitude}-${buildPointListText(point.accession_names, '')}`"
            class="legend-card"
            @click="$emit('select', point)"
          >
            <div class="legend-main">
              <div class="legend-title-row">
                <strong>{{ getRegionDisplayName(point.region) }}</strong>
                <b>{{ point.accession_count }}</b>
              </div>
              <div class="legend-detail-grid">
                <span><em>Accession</em>{{ buildPointListText(point.accession_names, '暂无') }}</span>
                <span><em>物种</em>{{ buildPointListText(point.species_names, '暂无') }}</span>
                <span><em>样本数</em>{{ point.sample_count }}</span>
                <span class="legend-meta"><em>经纬度</em>{{ formatCoordinate(point.longitude) }}, {{ formatCoordinate(point.latitude) }}</span>
              </div>
            </div>
          </button>
        </div>
      </aside>
    </div>

    <div v-else class="geo-empty">
      暂无地图点位数据
    </div>
  </section>
</template>

<script>
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { worldMapData } from '@/data/worldMapData.js'

const GEO_BUCKETS = [
  { label: '1 - 10', min: 1, max: 10, size: 10, color: '#22c55e' },
  { label: '11 - 50', min: 11, max: 50, size: 14, color: '#84cc16' },
  { label: '51 - 100', min: 51, max: 100, size: 18, color: '#facc15' },
  { label: '101 - 500', min: 101, max: 500, size: 23, color: '#f97316' },
  { label: '>500', min: 501, max: Number.POSITIVE_INFINITY, size: 29, color: '#ef4444' }
]

const MAX_TOOLTIP_ITEMS = 4

const getBucketForAccessionCount = (count) => {
  const accessionCount = Number(count) || 0
  return GEO_BUCKETS.find(
    (bucket) => accessionCount >= bucket.min && accessionCount <= bucket.max
  ) || GEO_BUCKETS[0]
}

const getRegionDisplayName = (region) => {
  if (!region || region === 'Unknown') {
    return '未标注地区'
  }
  return region
}

const formatCoordinate = (value) => {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(2) : '--'
}

const buildTooltipList = (items, fallback = 'Unknown') => {
  const normalized = (items || []).filter(Boolean)
  if (!normalized.length) {
    return fallback
  }

  const visible = normalized.slice(0, MAX_TOOLTIP_ITEMS)
  if (normalized.length > visible.length) {
    return `${visible.join(', ')} ... (${normalized.length})`
  }
  return visible.join(', ')
}

const buildPointListText = (items, fallback = '暂无') => {
  const normalized = (items || []).filter(Boolean)
  if (!normalized.length) {
    return fallback
  }

  const visible = normalized.slice(0, 2)
  if (normalized.length > visible.length) {
    return `${visible.join(', ')} 等 ${normalized.length} 个`
  }
  return visible.join(', ')
}

export default {
  name: 'GeoMapPanel',
  props: {
    points: {
      type: Array,
      default: () => []
    }
  },
  emits: ['select'],
  setup(props) {
    const mapRef = ref(null)
    const mapInstance = ref(null)
    const resizeTimer = ref(null)

    const topPoints = computed(() => props.points.slice(0, 6))
    const legendBuckets = GEO_BUCKETS
    const totalPointCount = computed(() => props.points.length.toLocaleString())

    const buildSeriesData = () =>
      props.points.map((point) => {
        const bucket = getBucketForAccessionCount(point.accession_count)
        return {
          name: point.region,
          region_display: getRegionDisplayName(point.region),
          value: [point.longitude, point.latitude, point.accession_count],
          latitude: point.latitude,
          longitude: point.longitude,
          accession_count: point.accession_count,
          accession_names: point.accession_names || [],
          sample_count: point.sample_count,
          species_names: point.species_names || [],
          bucket_label: bucket.label,
          symbolSize: bucket.size,
          itemStyle: {
            color: bucket.color,
            opacity: 0.9
          }
        }
      })

    const renderMap = () => {
      if (!mapRef.value) {
        return
      }

      if (!mapInstance.value) {
        echarts.registerMap('world-dashboard', worldMapData)
        mapInstance.value = echarts.init(mapRef.value, null, {
          devicePixelRatio: window.devicePixelRatio || 2,
          renderer: 'canvas',
          useDirtyRect: false,
          width: mapRef.value.clientWidth,
          height: mapRef.value.clientHeight
        })
      }

      mapInstance.value.clear()
      mapInstance.value.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          formatter: (params) => {
            if (!params.data) {
              return ''
            }

            return `
              <div style="padding: 8px 10px; color: #0f172a; line-height: 1.65; min-width: 280px;">
                <div><strong>地区:</strong> ${params.data.region_display}</div>
                <div><strong>材料数:</strong> ${params.data.accession_count}</div>
                <div><strong>样本数:</strong> ${params.data.sample_count}</div>
                <div><strong>Accession:</strong> ${buildTooltipList(params.data.accession_names, '暂无')}</div>
                <div><strong>物种名:</strong> ${buildTooltipList(params.data.species_names, '暂无')}</div>
                <div><strong>经纬度:</strong> ${formatCoordinate(params.data.longitude)}, ${formatCoordinate(params.data.latitude)}</div>
              </div>
            `
          }
        },
        geo: {
          map: 'world-dashboard',
          roam: true,
          zoom: 1.48,
          center: [18, 8],
          layoutCenter: ['48%', '54%'],
          layoutSize: '126%',
          boundingCoords: [[-180, -90], [180, 90]],
          itemStyle: {
            areaColor: '#d7e6fb',
            borderColor: '#8aa7cf',
            borderWidth: 0.9
          },
          emphasis: {
            itemStyle: {
              areaColor: '#bfdbfe',
              borderColor: '#4f6fa1',
              borderWidth: 1.1
            }
          },
          select: {
            itemStyle: {
              areaColor: '#93c5fd',
              borderColor: '#315b97'
            }
          }
        },
        series: [
          {
            type: 'scatter',
            coordinateSystem: 'geo',
            data: buildSeriesData(),
            zlevel: 3,
            itemStyle: {
              borderColor: '#ffffff',
              borderWidth: 1.8,
              shadowBlur: 14,
              shadowColor: 'rgba(15, 23, 42, 0.28)'
            },
            emphasis: {
              scale: 1.2,
              itemStyle: {
                borderColor: '#ffffff',
                borderWidth: 2.4,
                shadowBlur: 18,
                shadowColor: 'rgba(14, 116, 144, 0.32)'
              }
            }
          }
        ]
      }, true)
    }

    const resizeMap = () => {
      if (mapInstance.value) {
        mapInstance.value.resize()
        renderMap()
      }
    }

    const scheduleResize = () => {
      window.clearTimeout(resizeTimer.value)
      resizeTimer.value = window.setTimeout(() => {
        resizeMap()
      }, 80)
    }

    onMounted(async () => {
      await nextTick()
      renderMap()
      window.addEventListener('resize', scheduleResize)
    })

    watch(
      () => props.points,
      async () => {
        await nextTick()
        renderMap()
      },
      { deep: true }
    )

    onBeforeUnmount(() => {
      window.removeEventListener('resize', scheduleResize)
      window.clearTimeout(resizeTimer.value)
      if (mapInstance.value) {
        mapInstance.value.dispose()
      }
    })

    return {
      mapRef,
      legendBuckets,
      topPoints,
      totalPointCount,
      getRegionDisplayName,
      formatCoordinate,
      buildPointListText
    }
  }
}
</script>

<style scoped>
.geo-panel {
  --geo-map-height: 460px;
  --geo-column-height: 486px;
  padding: 24px;
  border-radius: 30px;
  background: linear-gradient(180deg, #ffffff, #fdfeff);
  border: 1px solid rgba(210, 221, 236, 0.9);
  box-shadow: 0 18px 40px rgba(14, 30, 66, 0.08);
}

.geo-header {
  display: flex;
  justify-content: flex-start;
  gap: 18px;
  align-items: flex-start;
}

.geo-kicker {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 800;
  color: #1d4ed8;
}

.geo-header h3 {
  margin: 0;
  font-size: 34px;
  color: #0f172a;
}

.geo-description {
  margin: 12px 0 0;
  max-width: 760px;
  color: #607085;
  font-size: 15px;
  line-height: 1.7;
}

.geo-scale-legend {
  position: absolute;
  top: 18px;
  right: 18px;
  z-index: 2;
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 18px;
  background: rgba(248, 251, 255, 0.94);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(214, 223, 235, 0.9);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
}

.geo-scale-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #23324d;
  font-size: 13px;
  font-weight: 700;
}

.geo-scale-dot {
  display: inline-block;
  border-radius: 999px;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.94);
  flex: 0 0 auto;
}

.geo-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.75fr);
  align-items: start;
  gap: 20px;
  margin-top: 18px;
}

.geo-map-shell {
  position: relative;
  padding: 12px;
  border-radius: 26px;
  background: linear-gradient(180deg, #edf5ff, #dfeefe);
  border: 1px solid rgba(173, 194, 222, 0.95);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.86),
    0 16px 32px rgba(19, 55, 110, 0.08);
}

.geo-map {
  height: var(--geo-map-height);
  border-radius: 22px;
  background:
    radial-gradient(circle at top, rgba(255, 255, 255, 0.92), rgba(231, 241, 255, 0.55) 38%, transparent 64%),
    linear-gradient(180deg, #e0edff, #f4f8ff);
}

.geo-side-panel {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  align-content: start;
  gap: 12px;
  height: var(--geo-column-height);
  min-height: 0;
}

.geo-summary-card {
  display: grid;
  justify-items: center;
  gap: 5px;
  padding: 12px 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, #f7fbff, #eff6ff);
  border: 1px solid rgba(204, 220, 240, 0.9);
  text-align: center;
}

.geo-summary-card span {
  color: #4b5c72;
  font-size: 12px;
  font-weight: 700;
}

.geo-summary-card strong {
  color: #133a82;
  font-size: 32px;
  line-height: 1;
}

.geo-summary-card em {
  color: #6b7b91;
  font-size: 12px;
  font-style: normal;
}

.geo-list-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 0 6px;
  color: #5d6d82;
  font-size: 13px;
  font-weight: 800;
}

.geo-point-list {
  display: grid;
  gap: 10px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.geo-point-list::-webkit-scrollbar {
  width: 6px;
}

.geo-point-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.42);
}

.legend-card {
  display: block;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(217, 225, 235, 0.9);
  background: linear-gradient(180deg, #fbfdff, #f7fafc);
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.legend-card:hover {
  transform: translateY(-2px);
  border-color: rgba(37, 99, 235, 0.22);
  box-shadow: 0 12px 20px rgba(37, 99, 235, 0.08);
}

.legend-main {
  display: grid;
  gap: 7px;
}

.legend-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.legend-title-row strong {
  color: #15326e;
  font-size: 13px;
  line-height: 1.35;
}

.legend-title-row b {
  flex: 0 0 auto;
  color: #15326e;
  font-size: 16px;
}

.legend-detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 4px;
}

.legend-detail-grid span {
  color: #5b6b81;
  font-size: 11px;
  line-height: 1.35;
}

.legend-detail-grid em {
  display: inline-block;
  min-width: 52px;
  margin-right: 6px;
  color: #7a8ba0;
  font-style: normal;
  font-weight: 700;
}

.legend-main span {
  color: #5b6b81;
  font-size: 11px;
}

.legend-meta {
  font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
}

.geo-side-panel > * {
  animation: geoFadeUp 0.55s ease both;
}

.geo-side-panel > *:nth-child(2) {
  animation-delay: 0.06s;
}

.geo-side-panel > *:nth-child(3) {
  animation-delay: 0.12s;
}

.geo-side-panel > *:nth-child(4) {
  animation-delay: 0.18s;
}

@keyframes geoFadeUp {
  from {
    opacity: 0;
    transform: translateY(14px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.geo-empty {
  margin-top: 18px;
  padding: 32px 18px;
  border-radius: 18px;
  background: #f8fafc;
  color: #64748b;
  text-align: center;
}

@media (max-width: 980px) {
  .geo-layout {
    grid-template-columns: 1fr;
  }

  .geo-map {
    height: 400px;
  }

  .geo-scale-legend {
    position: static;
    margin-bottom: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .geo-side-panel > * {
    animation: none;
  }
}
</style>

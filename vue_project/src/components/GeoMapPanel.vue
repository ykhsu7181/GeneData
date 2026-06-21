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
          <span>区域</span>
          <span>材料数</span>
        </div>

        <button
          v-for="point in topPoints"
          :key="`${point.region}-${point.latitude}-${point.longitude}`"
          class="legend-card"
          @click="$emit('select', point)"
        >
          <div class="legend-main">
            <strong>{{ point.region }}</strong>
            <span>样本数 {{ point.sample_count }}</span>
          </div>
          <b>{{ point.accession_count }}</b>
        </button>
      </aside>
    </div>

    <div v-else class="geo-empty">
      暂无地图点位数据
    </div>
  </section>
</template>

<script>
import * as echarts from 'echarts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { worldMapData } from '@/data/worldMapData.js'

const GEO_BUCKETS = [
  { label: '1 - 10', min: 1, max: 10, size: 10, color: '#22c55e' },
  { label: '11 - 50', min: 11, max: 50, size: 14, color: '#84cc16' },
  { label: '51 - 100', min: 51, max: 100, size: 18, color: '#facc15' },
  { label: '101 - 500', min: 101, max: 500, size: 23, color: '#f97316' },
  { label: '>500', min: 501, max: Number.POSITIVE_INFINITY, size: 29, color: '#ef4444' }
]

const getBucketForAccessionCount = (count) => {
  const accessionCount = Number(count) || 0
  return GEO_BUCKETS.find(
    (bucket) => accessionCount >= bucket.min && accessionCount <= bucket.max
  ) || GEO_BUCKETS[0]
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
    const topPoints = computed(() => props.points.slice(0, 6))
    const legendBuckets = GEO_BUCKETS
    const totalPointCount = computed(() => props.points.length.toLocaleString())

    const buildSeriesData = () =>
      props.points.map((point) => {
        const bucket = getBucketForAccessionCount(point.accession_count)
        return {
          name: point.region,
          value: [point.longitude, point.latitude, point.accession_count],
          accession_count: point.accession_count,
          sample_count: point.sample_count,
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
        mapInstance.value = echarts.init(mapRef.value)
      }

      mapInstance.value.setOption({
        tooltip: {
          trigger: 'item',
          formatter: (params) =>
            `
              <div style="padding: 6px 8px; color: #0f172a;">
                地区: ${params.data.name}<br/>
                材料数: ${params.data.accession_count}<br/>
                样本数: ${params.data.sample_count}
              </div>
            `
        },
        geo: {
          map: 'world-dashboard',
          roam: true,
          zoom: 1.12,
          itemStyle: {
            areaColor: '#e7eff8',
            borderColor: '#ffffff'
          },
          emphasis: {
            itemStyle: {
              areaColor: '#cfe1fb'
            }
          }
        },
        series: [
          {
            type: 'scatter',
            coordinateSystem: 'geo',
            data: buildSeriesData(),
            emphasis: {
              scale: 1.2,
              itemStyle: {
                borderColor: '#ffffff',
                borderWidth: 2
              }
            }
          }
        ]
      })
    }

    const resizeMap = () => {
      if (mapInstance.value) {
        mapInstance.value.resize()
      }
    }

    onMounted(() => {
      renderMap()
      window.addEventListener('resize', resizeMap)
    })

    watch(
      () => props.points,
      () => renderMap(),
      { deep: true }
    )

    onBeforeUnmount(() => {
      window.removeEventListener('resize', resizeMap)
      if (mapInstance.value) {
        mapInstance.value.dispose()
      }
    })

    return {
      mapRef,
      legendBuckets,
      topPoints,
      totalPointCount
    }
  }
}
</script>

<style scoped>
.geo-panel {
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
  gap: 20px;
  margin-top: 18px;
}

.geo-map-shell {
  position: relative;
  padding: 12px;
  border-radius: 26px;
  background: linear-gradient(180deg, #f5faff, #eef5ff);
  border: 1px solid rgba(214, 223, 235, 0.9);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.geo-map {
  height: 520px;
  border-radius: 22px;
  background: linear-gradient(180deg, #edf5ff, #f8fbff);
}

.geo-side-panel {
  display: grid;
  align-content: start;
  gap: 12px;
}

.geo-summary-card {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 20px 16px;
  border-radius: 22px;
  background: linear-gradient(180deg, #f7fbff, #eff6ff);
  border: 1px solid rgba(204, 220, 240, 0.9);
  text-align: center;
}

.geo-summary-card span {
  color: #4b5c72;
  font-size: 14px;
  font-weight: 700;
}

.geo-summary-card strong {
  color: #133a82;
  font-size: 42px;
  line-height: 1;
}

.geo-summary-card em {
  color: #6b7b91;
  font-size: 13px;
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

.legend-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 18px;
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
  gap: 6px;
}

.legend-main strong {
  color: #15326e;
  font-size: 15px;
}

.legend-main span {
  color: #5b6b81;
  font-size: 13px;
}

.legend-card b {
  color: #15326e;
  font-size: 18px;
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

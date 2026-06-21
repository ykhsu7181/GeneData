<template>
  <section class="geo-panel">
    <div class="geo-header">
      <div>
        <p class="geo-kicker">Geographic distribution</p>
        <h3>地理分布</h3>
      </div>
      <div class="geo-scale-legend" aria-label="Geographic distribution scale">
        <span
          v-for="bucket in legendBuckets"
          :key="bucket.label"
          class="geo-scale-chip">
          <i
            class="geo-scale-dot"
            :style="{
              backgroundColor: bucket.color,
              width: `${bucket.size}px`,
              height: `${bucket.size}px`
            }"></i>
          {{ bucket.label }}
        </span>
      </div>
    </div>

    <div v-if="points.length" class="geo-layout">
      <div ref="mapRef" class="geo-map"></div>
      <div class="geo-legend">
        <button
          v-for="point in topPoints"
          :key="`${point.region}-${point.latitude}-${point.longitude}`"
          class="legend-card"
          @click="$emit('select', point)">
          <strong>{{ point.region }}</strong>
          <span>材料数 {{ point.accession_count }}</span>
          <span>样本数 {{ point.sample_count }}</span>
        </button>
      </div>
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
  { label: '11 - 50', min: 11, max: 50, size: 14, color: '#0ea5e9' },
  { label: '51 - 100', min: 51, max: 100, size: 18, color: '#6366f1' },
  { label: '101 - 500', min: 101, max: 500, size: 24, color: '#f59e0b' },
  { label: '>500', min: 501, max: Number.POSITIVE_INFINITY, size: 30, color: '#ef4444' }
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

    const buildSeriesData = () =>
      props.points.map((point) => {
        const bucket = getBucketForAccessionCount(point.accession_count)
        return {
          name: point.region,
          value: [point.longitude, point.latitude, point.accession_count],
          accession_count: point.accession_count,
          sample_count: point.sample_count,
          dataset_count: point.dataset_count,
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
        mapInstance.value.on('click', { seriesType: 'scatter' }, (params) => {
          const matched = props.points.find(
            (point) =>
              point.region === params.data.name &&
              Number(point.longitude) === Number(params.data.value[0]) &&
              Number(point.latitude) === Number(params.data.value[1])
          )
          if (matched) {
            mapInstance.value.dispatchAction({
              type: 'highlight',
              seriesIndex: 0,
              dataIndex: params.dataIndex
            })
          }
        })
      }

      mapInstance.value.setOption({
        tooltip: {
          trigger: 'item',
          formatter: (params) =>
            `
              <div style="padding: 6px 8px;">
                地区: ${params.data.name}<br/>
                材料数: ${params.data.accession_count}<br/>
                样本数: ${params.data.sample_count}
              </div>
            `
        },
        geo: {
          map: 'world-dashboard',
          roam: true,
          zoom: 1.15,
          itemStyle: {
            areaColor: '#e2e8f0',
            borderColor: '#ffffff'
          },
          emphasis: {
            itemStyle: {
              areaColor: '#bfdbfe'
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
                borderColor: '#1d4ed8',
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
      topPoints
    }
  }
}
</script>

<style scoped>
.geo-panel {
  padding: 26px;
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.08);
}

.geo-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.geo-kicker {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
  color: #0f766e;
}

.geo-header h3 {
  margin: 0;
  font-size: 28px;
  color: #0f172a;
}

.geo-scale-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.geo-scale-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #f8fafc;
  color: #1e293b;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.geo-scale-dot {
  display: inline-block;
  flex: 0 0 auto;
  border-radius: 999px;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.9);
}

.geo-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.85fr);
  gap: 18px;
  margin-top: 18px;
}

.geo-map {
  height: 500px;
  border-radius: 24px;
  background: linear-gradient(180deg, #edf5ff, #f8fbff);
}

.geo-legend {
  display: grid;
  gap: 12px;
}

.legend-card {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 18px;
  background: #f8fafc;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.legend-card:hover {
  transform: translateY(-2px);
  border-color: rgba(29, 78, 216, 0.22);
}

.legend-card strong {
  color: #0f172a;
}

.legend-card span {
  color: #475569;
}

.geo-empty {
  margin-top: 18px;
  padding: 32px 18px;
  border-radius: 18px;
  background: #f8fafc;
  color: #64748b;
  text-align: center;
}

@media (max-width: 960px) {
  .geo-scale-legend {
    justify-content: flex-start;
  }

  .geo-layout {
    grid-template-columns: 1fr;
  }

  .geo-map {
    height: 380px;
  }
}
</style>

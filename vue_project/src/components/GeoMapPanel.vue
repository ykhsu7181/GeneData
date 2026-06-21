<template>
  <section class="geo-panel">
    <div class="geo-header">
      <div>
        <p class="geo-kicker">Geographic distribution</p>
        <h3>地理分布</h3>
      </div>
      <span class="geo-note">点击区域可跳转到地图页</span>
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
          <span>{{ point.accession_count }} accession</span>
          <span>{{ point.sample_count }} sample</span>
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

    const buildSeriesData = () =>
      props.points.map((point) => ({
        name: point.region,
        value: [point.longitude, point.latitude, point.accession_count],
        accession_count: point.accession_count,
        sample_count: point.sample_count,
        dataset_count: point.dataset_count
      }))

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
                <strong>${params.data.name}</strong><br/>
                accession: ${params.data.accession_count}<br/>
                sample: ${params.data.sample_count}<br/>
                dataset: ${params.data.dataset_count}
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
            symbolSize: (value) => Math.max(10, Math.min(30, 8 + Number(value[2]) * 2)),
            itemStyle: {
              color: '#16a34a',
              opacity: 0.85
            },
            emphasis: {
              scale: 1.2,
              itemStyle: {
                color: '#1d4ed8'
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
  align-items: flex-start;
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

.geo-note {
  padding: 10px 14px;
  border-radius: 999px;
  background: #ecfccb;
  color: #365314;
  font-size: 13px;
  font-weight: 700;
}

.geo-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.8fr);
  gap: 18px;
  margin-top: 18px;
}

.geo-map {
  height: 460px;
  border-radius: 22px;
  background: linear-gradient(180deg, #eff6ff, #f8fafc);
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
  .geo-layout {
    grid-template-columns: 1fr;
  }

  .geo-map {
    height: 380px;
  }
}
</style>

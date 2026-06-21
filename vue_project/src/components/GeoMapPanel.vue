<template>
  <section class="geo-panel">
    <div class="geo-header">
      <div>
        <p class="geo-kicker">Geographic distribution</p>
        <h3>地理分布</h3>
      </div>
      <div class="geo-scale-legend" aria-label="Geographic distribution scale">
        <span>1 - 10</span>
        <span>11 - 50</span>
        <span>51 - 100</span>
        <span>101 - 500</span>
        <span>&gt;500</span>
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

.geo-scale-legend span {
  padding: 8px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
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

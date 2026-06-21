<template>
  <section class="distribution-panel">
    <div class="panel-header">
      <div>
        <p class="panel-kicker">{{ kicker }}</p>
        <h3>{{ title }}</h3>
      </div>
      <span class="panel-total">{{ totalValueLabel }}</span>
    </div>

    <div v-if="items.length" class="panel-content">
      <div ref="chartRef" class="chart-box"></div>
      <div class="legend-list">
        <div
          v-for="(item, index) in normalizedItems"
          :key="`${item[labelKey]}-${index}`"
          class="legend-row">
          <div class="legend-label">
            <span class="color-chip" :style="{ backgroundColor: palette[index % palette.length] }"></span>
            <span>{{ item[labelKey] }}</span>
          </div>
          <strong>{{ item[valueKey] }}</strong>
        </div>
      </div>
    </div>

    <div v-else class="panel-empty">
      {{ emptyText }}
    </div>
  </section>
</template>

<script>
import * as echarts from 'echarts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const palette = ['#1d4ed8', '#0f766e', '#f97316', '#9333ea', '#e11d48', '#16a34a', '#6b7280']

export default {
  name: 'DistributionPanel',
  props: {
    title: {
      type: String,
      default: ''
    },
    kicker: {
      type: String,
      default: ''
    },
    items: {
      type: Array,
      default: () => []
    },
    labelKey: {
      type: String,
      default: 'name'
    },
    valueKey: {
      type: String,
      default: 'accession_count'
    },
    emptyText: {
      type: String,
      default: 'No Data'
    }
  },
  setup(props) {
    const chartRef = ref(null)
    const chartInstance = ref(null)

    const normalizedItems = computed(() => props.items.slice(0, 8))
    const totalValueLabel = computed(() =>
      normalizedItems.value.reduce((sum, item) => sum + Number(item[props.valueKey] || 0), 0).toLocaleString()
    )

    const renderChart = () => {
      if (!chartRef.value) {
        return
      }
      if (!chartInstance.value) {
        chartInstance.value = echarts.init(chartRef.value)
      }

      chartInstance.value.setOption({
        color: palette,
        tooltip: {
          trigger: 'item'
        },
        series: [
          {
            type: 'pie',
            radius: ['54%', '78%'],
            avoidLabelOverlap: true,
            itemStyle: {
              borderColor: '#fff',
              borderWidth: 3
            },
            label: {
              show: false
            },
            data: normalizedItems.value.map((item) => ({
              name: item[props.labelKey],
              value: Number(item[props.valueKey] || 0)
            }))
          }
        ]
      })
    }

    const resizeChart = () => {
      if (chartInstance.value) {
        chartInstance.value.resize()
      }
    }

    onMounted(() => {
      renderChart()
      window.addEventListener('resize', resizeChart)
    })

    watch(
      () => props.items,
      () => renderChart(),
      { deep: true }
    )

    onBeforeUnmount(() => {
      window.removeEventListener('resize', resizeChart)
      if (chartInstance.value) {
        chartInstance.value.dispose()
      }
    })

    return {
      chartRef,
      normalizedItems,
      totalValueLabel,
      palette
    }
  }
}
</script>

<style scoped>
.distribution-panel {
  padding: 24px;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.panel-kicker {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
  color: #0f766e;
}

.panel-header h3 {
  margin: 0;
  font-size: 24px;
  color: #0f172a;
}

.panel-total {
  padding: 10px 14px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
}

.panel-content {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr);
  gap: 18px;
  align-items: center;
  margin-top: 18px;
}

.chart-box {
  width: 100%;
  height: 280px;
}

.legend-list {
  display: grid;
  gap: 12px;
}

.legend-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  background: #f8fafc;
}

.legend-label {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #334155;
}

.color-chip {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-row strong {
  color: #0f172a;
}

.panel-empty {
  margin-top: 18px;
  padding: 32px 18px;
  border-radius: 18px;
  background: #f8fafc;
  color: #64748b;
  text-align: center;
}

@media (max-width: 900px) {
  .panel-content {
    grid-template-columns: 1fr;
  }
}
</style>

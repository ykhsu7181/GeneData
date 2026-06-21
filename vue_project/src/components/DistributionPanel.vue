<template>
  <section class="distribution-panel">
    <div class="panel-header">
      <div class="panel-heading">
        <p class="panel-kicker">{{ kicker }}</p>
        <h3>{{ title }}</h3>
      </div>
      <div class="panel-switches">
        <button class="switch-chip is-active" type="button">图表</button>
        <button class="switch-chip" type="button">卡片</button>
      </div>
    </div>

    <div v-if="items.length" class="panel-body">
      <aside class="panel-stat-card">
        <span>总计</span>
        <strong>{{ totalValueLabel }}</strong>
      </aside>
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
  align-items: center;
  gap: 16px;
}

.panel-heading {
  min-width: 0;
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

.panel-switches {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 999px;
  background: #f1f5f9;
}

.switch-chip {
  border: 0;
  border-radius: 999px;
  padding: 8px 14px;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
  cursor: default;
}

.switch-chip.is-active {
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.panel-body {
  display: grid;
  grid-template-columns: 180px minmax(220px, 1fr) minmax(220px, 0.95fr);
  gap: 18px;
  align-items: center;
  margin-top: 18px;
}

.panel-stat-card {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 160px;
  border-radius: 22px;
  background: linear-gradient(180deg, #f8fbff, #eef6ff);
  text-align: center;
}

.panel-stat-card span {
  color: #64748b;
  font-size: 14px;
  letter-spacing: 0.08em;
}

.panel-stat-card strong {
  color: #0f172a;
  font-size: 34px;
  line-height: 1;
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
  border: 1px solid #e2e8f0;
}

.legend-label {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #334155;
  min-width: 0;
}

.legend-label span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  .panel-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .panel-switches {
    align-self: flex-start;
  }

  .panel-body {
    grid-template-columns: 1fr;
  }

  .panel-stat-card {
    min-height: 140px;
  }
}
</style>

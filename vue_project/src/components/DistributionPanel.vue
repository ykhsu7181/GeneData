<template>
  <section :class="['distribution-panel', { 'is-empty': !items.length }]">
    <div class="panel-header">
      <div class="panel-heading">
        <p class="panel-kicker">{{ kicker }}</p>
        <h3>{{ title }}</h3>
      </div>

      <div class="panel-view-toggle" aria-label="分布视图切换">
        <button
          :class="['view-toggle-button', { 'is-active': viewMode === 'chart' }]"
          type="button"
          @click="setViewMode('chart')"
        >
          图表视图
        </button>
        <button
          :class="['view-toggle-button', { 'is-active': viewMode === 'list' }]"
          type="button"
          @click="setViewMode('list')"
        >
          列表视图
        </button>
      </div>
    </div>

    <div v-if="items.length" class="panel-body">
      <aside class="panel-stat-card">
        <div class="stat-icon">◎</div>
        <span>总计</span>
        <strong>{{ totalValueLabel }}</strong>
        <em>{{ statisticCaption }}</em>
      </aside>

      <div v-show="viewMode === 'chart'" class="chart-shell">
        <div ref="chartRef" class="chart-box"></div>
      </div>

      <div v-if="viewMode === 'chart'" class="legend-list">
        <div class="legend-head">
          <span>{{ legendLabelTitle }}</span>
          <span>{{ legendValueTitle }}</span>
        </div>

        <div
          v-for="(item, index) in normalizedItems"
          :key="`${item[labelKey]}-${index}`"
          class="legend-row"
        >
          <div class="legend-label">
            <span
              class="color-chip"
              :style="{ backgroundColor: palette[index % palette.length] }"
            ></span>
            <span>{{ item[labelKey] }}</span>
          </div>
          <strong>{{ formatNumber(item[valueKey]) }}</strong>
        </div>
      </div>

      <div v-else class="bar-list">
        <div class="bar-list-head">
          <span>{{ legendLabelTitle }}</span>
          <span>{{ legendValueTitle }}</span>
        </div>
        <div
          v-for="(item, index) in normalizedItems"
          :key="`${item[labelKey]}-${index}`"
          class="bar-row"
        >
          <div class="bar-row-top">
            <span class="bar-label">
              <i
                class="color-chip"
                :style="{ backgroundColor: palette[index % palette.length] }"
              ></i>
              {{ item[labelKey] }}
            </span>
            <strong>{{ formatNumber(item[valueKey]) }}</strong>
          </div>
          <div class="bar-track">
            <span
              class="bar-fill"
              :style="{
                width: getBarWidth(item),
                backgroundColor: palette[index % palette.length]
              }"
            ></span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="panel-empty">
      <div class="empty-icon">◌</div>
      <h4>{{ emptyText }}</h4>
      <p>当前维度暂无可展示的聚合结果，建议先补充对应主数据或切换到其他模块继续浏览。</p>
    </div>
  </section>
</template>

<script>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const palette = ['#1f77ff', '#ff7a18', '#22b573', '#5b6cff', '#f04d4f', '#10b981', '#8c63ff', '#94a3b8']

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
    const viewMode = ref('chart')
    let chartRuntimePromise = null

    const loadChartRuntime = () => {
      if (!chartRuntimePromise) {
        chartRuntimePromise = import('@/utils/dashboardPieCharts')
          .then((module) => module.default)
      }
      return chartRuntimePromise
    }

    const normalizedItems = computed(() => props.items.slice(0, 8))
    const totalValue = computed(() =>
      props.items.reduce((sum, item) => sum + Number(item[props.valueKey] || 0), 0)
    )
    const maxValue = computed(() =>
      normalizedItems.value.reduce((max, item) => Math.max(max, Number(item[props.valueKey] || 0)), 0)
    )
    const totalValueLabel = computed(() => totalValue.value.toLocaleString())
    const formatNumber = (value) => Number(value || 0).toLocaleString()
    const getBarWidth = (item) => {
      const value = Number(item[props.valueKey] || 0)
      if (!maxValue.value || value <= 0) {
        return '0%'
      }
      return `${Math.max((value / maxValue.value) * 100, 4).toFixed(2)}%`
    }

    const legendLabelTitle = computed(() => {
      if (props.labelKey === 'dataset_type') {
        return '类型'
      }
      if (props.labelKey === 'file_role') {
        return '角色'
      }
      return '分类'
    })

    const legendValueTitle = computed(() => {
      if (props.valueKey === 'dataset_count') {
        return '数据集数'
      }
      if (props.valueKey === 'datafile_count') {
        return '文件数'
      }
      return '数量'
    })

    const statisticCaption = computed(() => {
      if (props.valueKey === 'dataset_count') {
        return '有效数据集统计'
      }
      if (props.valueKey === 'datafile_count') {
        return '正式文件统计'
      }
      if (props.valueKey === 'accession_count') {
        return '材料归属统计'
      }
      if (props.valueKey === 'sample_count') {
        return '样本归属统计'
      }
      return '对象聚合统计'
    })

    const renderChart = async () => {
      if (!chartRef.value || viewMode.value !== 'chart') {
        return
      }

      const echarts = await loadChartRuntime()
      if (!chartRef.value || viewMode.value !== 'chart') {
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
            radius: ['56%', '80%'],
            center: ['50%', '50%'],
            avoidLabelOverlap: true,
            itemStyle: {
              borderColor: '#ffffff',
              borderWidth: 4
            },
            label: {
              show: true,
              formatter: ({ percent }) => (percent >= 3 ? `${Math.round(percent)}%` : ''),
              color: '#1e3a8a',
              fontSize: 12,
              fontWeight: 700
            },
            labelLine: {
              length: 10,
              length2: 10
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
      if (chartInstance.value && viewMode.value === 'chart') {
        chartInstance.value.resize()
      }
    }

    const setViewMode = (mode) => {
      viewMode.value = mode
      if (mode === 'chart') {
        requestAnimationFrame(() => {
          renderChart().then(resizeChart)
        })
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
      viewMode,
      normalizedItems,
      totalValueLabel,
      statisticCaption,
      legendLabelTitle,
      legendValueTitle,
      palette,
      formatNumber,
      getBarWidth,
      setViewMode
    }
  }
}
</script>

<style scoped>
.distribution-panel {
  align-self: start;
  padding: 22px 22px 24px;
  border-radius: 28px;
  background: linear-gradient(180deg, #ffffff, #fdfefe);
  border: 1px solid rgba(210, 221, 236, 0.9);
  box-shadow: 0 18px 40px rgba(14, 30, 66, 0.08);
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
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 800;
  color: #1d4ed8;
}

.panel-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 32px;
  line-height: 1.1;
}

.panel-view-toggle {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fafc, #eef2f8);
  border: 1px solid rgba(212, 221, 233, 0.9);
}

.view-toggle-button {
  min-height: 34px;
  padding: 0 14px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #4f627b;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.view-toggle-button.is-active {
  color: #ffffff;
  background: linear-gradient(135deg, #2d68e3 0%, #1d4ed8 100%);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.24);
}

.panel-body {
  display: grid;
  grid-template-columns: 168px minmax(240px, 1fr) minmax(238px, 0.9fr);
  gap: 16px;
  align-items: stretch;
  margin-top: 18px;
}

.panel-stat-card {
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 8px;
  padding: 20px 16px;
  border-radius: 24px;
  background: linear-gradient(180deg, #f7fbff, #eff6ff);
  border: 1px solid rgba(204, 220, 240, 0.9);
  text-align: center;
}

.stat-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border-radius: 18px;
  background: #ffffff;
  color: #2563eb;
  font-size: 20px;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.12);
}

.panel-stat-card span {
  color: #4b5c72;
  font-size: 15px;
  font-weight: 700;
}

.panel-stat-card strong {
  color: #133a82;
  font-size: 42px;
  line-height: 1;
}

.panel-stat-card em {
  color: #6b7b91;
  font-size: 13px;
  font-style: normal;
}

.chart-shell {
  display: grid;
  place-items: center;
  min-height: 320px;
  padding: 10px;
  border-radius: 24px;
  background:
    radial-gradient(circle at center, rgba(59, 130, 246, 0.08), transparent 58%),
    linear-gradient(180deg, #fbfdff, #f6faff);
  border: 1px solid rgba(220, 228, 240, 0.88);
}

.chart-box {
  width: 100%;
  height: 300px;
}

.legend-list {
  display: grid;
  align-content: start;
  gap: 10px;
}

.legend-head,
.legend-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}

.legend-head {
  padding: 0 8px;
  color: #5d6d82;
  font-size: 13px;
  font-weight: 800;
}

.legend-row {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(217, 225, 235, 0.9);
  background: linear-gradient(180deg, #fbfdff, #f7fafc);
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.legend-row:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.22);
  box-shadow: 0 10px 18px rgba(37, 99, 235, 0.08);
}

.legend-label {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  color: #334155;
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
  flex: 0 0 auto;
}

.legend-row strong {
  color: #15326e;
  font-size: 15px;
}

.bar-list {
  display: grid;
  align-content: start;
  gap: 10px;
  min-height: 320px;
  padding: 12px;
  border-radius: 24px;
  background:
    radial-gradient(circle at center, rgba(59, 130, 246, 0.06), transparent 58%),
    linear-gradient(180deg, #fbfdff, #f6faff);
  border: 1px solid rgba(220, 228, 240, 0.88);
  grid-column: span 2;
}

.bar-list-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 0 4px 2px;
  color: #5d6d82;
  font-size: 13px;
  font-weight: 800;
}

.bar-row {
  display: grid;
  gap: 9px;
  padding: 11px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(217, 225, 235, 0.85);
}

.bar-row-top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}

.bar-label {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  color: #334155;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bar-row-top strong {
  color: #15326e;
  font-size: 15px;
}

.bar-track {
  overflow: hidden;
  height: 10px;
  border-radius: 999px;
  background: #e8eef7;
}

.bar-fill {
  display: block;
  height: 100%;
  min-width: 0;
  border-radius: inherit;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.62) inset;
  transition: width 0.28s ease;
}

.panel-empty {
  margin-top: 18px;
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 34px 20px;
  border-radius: 22px;
  background: linear-gradient(180deg, #f8fafc, #f3f7fc);
  color: #64748b;
  text-align: center;
}

.empty-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border-radius: 18px;
  background: #ffffff;
  color: #2563eb;
  font-size: 22px;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.1);
}

.panel-empty h4 {
  margin: 0;
  color: #18345f;
  font-size: 22px;
}

.panel-empty p {
  max-width: 420px;
  margin: 0;
  color: #607085;
  font-size: 14px;
  line-height: 1.7;
}

@media (max-width: 980px) {
  .panel-header {
    flex-direction: column;
  }

  .panel-body {
    grid-template-columns: 1fr;
  }

  .panel-stat-card {
    min-height: 160px;
  }
}
</style>

<template>
  <section class="hero-panel">
    <div class="hero-copy">
      <p class="eyebrow">Data portal</p>
      <h1>基因数据仓库首页</h1>
      <p class="hero-subtitle">快速检索与浏览，探索作物种质、基因组、注释与转录组数据集合。</p>

      <div class="hero-search">
        <el-input
          v-model="queryText"
          placeholder="支持 accession、物种名、亚群、数据类型、地理位置关键词"
          size="large"
          @keyup.enter="submitSearch">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" size="large" class="search-button" @click="submitSearch">
          {{ $t('common.search') }}
        </el-button>
      </div>

      <div class="hot-keywords">
        <span class="hot-label">热门搜索</span>
        <button
          v-for="keyword in hotKeywords"
          :key="keyword.label"
          class="keyword-chip"
          @click="$emit('keyword-click', keyword)">
          {{ keyword.label }}
        </button>
      </div>
    </div>

    <div class="hero-summary">
      <div
        v-for="item in summaryCards"
        :key="item.key"
        class="summary-card">
        <span class="summary-label">{{ item.label }}</span>
        <strong class="summary-value">{{ item.value }}</strong>
      </div>
    </div>
  </section>
</template>

<script>
import { computed, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'

export default {
  name: 'DashboardHero',
  components: {
    Search
  },
  props: {
    summary: {
      type: Object,
      default: () => ({})
    },
    hotKeywords: {
      type: Array,
      default: () => []
    }
  },
  emits: ['search', 'keyword-click'],
  setup(props, { emit }) {
    const queryText = ref('')

    const summaryCards = computed(() => [
      { key: 'species', label: '物种数', value: props.summary.species_count || 0 },
      { key: 'accession', label: '材料数', value: props.summary.accession_count || 0 },
      { key: 'sample', label: '样本数', value: props.summary.sample_count || 0 },
      { key: 'file', label: '文件数', value: props.summary.datafile_count || 0 },
      { key: 'size', label: '数据量', value: props.summary.total_size_display || '0 B' }
    ])

    const submitSearch = () => {
      emit('search', queryText.value)
    }

    return {
      queryText,
      summaryCards,
      submitSearch
    }
  }
}
</script>

<style scoped>
.hero-panel {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.9fr);
  gap: 28px;
  padding: 42px;
  border-radius: 30px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.2), transparent 30%),
    radial-gradient(circle at bottom right, rgba(22, 163, 74, 0.24), transparent 32%),
    linear-gradient(135deg, #0b3a7e 0%, #0e5a5a 48%, #365314 100%);
  box-shadow: 0 28px 60px rgba(10, 26, 61, 0.22);
}

.hero-panel::after {
  content: '';
  position: absolute;
  inset: auto -8% -28% auto;
  width: 280px;
  height: 280px;
  border-radius: 50%;
  background: rgba(253, 224, 71, 0.18);
  filter: blur(4px);
}

.hero-copy {
  position: relative;
  z-index: 1;
  color: #fff;
}

.eyebrow {
  margin: 0 0 14px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(226, 232, 240, 0.86);
}

.hero-copy h1 {
  margin: 0;
  font-size: 44px;
  line-height: 1.08;
}

.hero-subtitle {
  max-width: 720px;
  margin: 16px 0 0;
  font-size: 18px;
  line-height: 1.7;
  color: rgba(226, 232, 240, 0.92);
}

.hero-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  margin-top: 28px;
}

.search-button {
  min-width: 130px;
  border-radius: 16px;
  background: linear-gradient(135deg, #16a34a, #059669);
  border: none;
}

.hot-keywords {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 24px;
}

.hot-label {
  color: rgba(226, 232, 240, 0.88);
  font-weight: 600;
}

.keyword-chip {
  padding: 8px 14px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.keyword-chip:hover {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.16);
}

.hero-summary {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  align-content: center;
}

.summary-card {
  padding: 20px 22px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.summary-label {
  display: block;
  color: rgba(226, 232, 240, 0.78);
  font-size: 13px;
}

.summary-value {
  display: block;
  margin-top: 8px;
  color: #fff;
  font-size: 30px;
  line-height: 1.1;
}

@media (max-width: 1024px) {
  .hero-panel {
    grid-template-columns: 1fr;
    padding: 30px;
  }

  .hero-copy h1 {
    font-size: 36px;
  }

  .hero-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .hero-panel {
    padding: 24px;
    border-radius: 24px;
  }

  .hero-copy h1 {
    font-size: 30px;
  }

  .hero-subtitle {
    font-size: 16px;
  }

  .hero-search {
    grid-template-columns: 1fr;
  }

  .hero-summary {
    grid-template-columns: 1fr;
  }
}
</style>

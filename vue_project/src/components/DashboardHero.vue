<template>
  <section class="hero-panel">
    <div class="hero-backdrop"></div>

    <div class="hero-content">
      <div class="hero-copy">
        <p class="eyebrow">Gene Data Warehouse</p>
        <h1>基因数据仓库首页</h1>
        <p class="hero-subtitle">
          快速检索与浏览，探索作物种基因数据结果
        </p>

        <div class="hero-search">
          <el-input
            v-model="queryText"
            placeholder="支持 accession、物种名、亚群、数据类型、地理位置关键词"
            size="large"
            @keyup.enter="submitSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button
            type="primary"
            size="large"
            class="search-button"
            @click="submitSearch"
          >
            {{ $t('common.search') }}
          </el-button>
        </div>

        <div class="hot-keywords">
          <span class="hot-label">热门搜索:</span>
          <button
            v-for="keyword in hotKeywords"
            :key="keyword.label"
            class="keyword-chip"
            @click="$emit('keyword-click', keyword)"
          >
            {{ keyword.label }}
          </button>
        </div>
      </div>

      <div class="hero-summary">
        <div
          v-for="item in summaryCards"
          :key="item.key"
          class="summary-card"
        >
          <span class="summary-label">{{ item.label }}</span>
          <strong class="summary-value">{{ item.value }}</strong>
        </div>
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
  min-height: 540px;
  padding: 88px 64px 56px;
  border-radius: 0 0 32px 32px;
  overflow: hidden;
  background:
    linear-gradient(rgba(8, 24, 40, 0.38), rgba(8, 24, 40, 0.42)),
    linear-gradient(120deg, #527d18 0%, #9aa63d 28%, #436b12 56%, #8b7a16 100%);
  box-shadow: 0 30px 72px rgba(28, 46, 12, 0.24);
}

.hero-backdrop {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 14% 20%, rgba(255, 244, 191, 0.28), transparent 26%),
    radial-gradient(circle at 82% 24%, rgba(255, 255, 255, 0.14), transparent 22%),
    linear-gradient(135deg, rgba(21, 61, 12, 0.06), rgba(255, 255, 255, 0));
  opacity: 0.95;
}

.hero-panel::before,
.hero-panel::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.hero-panel::before {
  width: 420px;
  height: 420px;
  right: -120px;
  top: -120px;
  background: rgba(255, 255, 255, 0.12);
}

.hero-panel::after {
  width: 320px;
  height: 320px;
  left: -110px;
  bottom: -180px;
  background: rgba(250, 204, 21, 0.14);
}

.hero-content {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.75fr);
  gap: 32px;
  align-items: center;
}

.hero-copy {
  color: #f8fafc;
}

.eyebrow {
  margin: 0 0 18px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(241, 245, 249, 0.82);
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(2.5rem, 5vw, 4rem);
  line-height: 1.04;
  letter-spacing: 0.01em;
  text-shadow: 0 10px 28px rgba(8, 24, 40, 0.24);
}

.hero-subtitle {
  max-width: 680px;
  margin: 20px 0 0;
  font-size: 1.125rem;
  line-height: 1.85;
  color: rgba(248, 250, 252, 0.9);
}

.hero-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  margin-top: 28px;
  max-width: 760px;
}

.hero-search :deep(.el-input__wrapper) {
  min-height: 62px;
  padding: 0 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow:
    0 20px 48px rgba(8, 24, 40, 0.18),
    inset 0 0 0 1px rgba(255, 255, 255, 0.58);
}

.hero-search :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 20px 48px rgba(8, 24, 40, 0.18),
    inset 0 0 0 1px rgba(255, 255, 255, 0.72),
    0 0 0 4px rgba(253, 224, 71, 0.22);
}

.hero-search :deep(.el-input__inner) {
  font-size: 16px;
  color: #17311e;
}

.hero-search :deep(.el-input__prefix-inner) {
  color: #55731b;
  font-size: 18px;
}

.search-button {
  min-width: 152px;
  min-height: 62px;
  padding: 0 28px;
  border: none;
  border-radius: 22px;
  background: linear-gradient(135deg, #facc15 0%, #f59e0b 100%);
  color: #243417;
  font-size: 16px;
  font-weight: 700;
  box-shadow: 0 18px 40px rgba(84, 66, 9, 0.28);
}

.search-button:hover,
.search-button:focus {
  background: linear-gradient(135deg, #fde047 0%, #f59e0b 100%);
  color: #1f2f12;
}

.hot-keywords {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 26px;
}

.hot-label {
  font-weight: 600;
  color: rgba(248, 250, 252, 0.88);
}

.keyword-chip {
  padding: 9px 16px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.11);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: transform 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
}

.keyword-chip:hover {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.18);
  border-color: rgba(255, 255, 255, 0.28);
}

.hero-summary {
  display: grid;
  gap: 16px;
  align-content: center;
}

.summary-card {
  padding: 22px 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    0 20px 40px rgba(14, 24, 10, 0.18);
  backdrop-filter: blur(12px);
}

.summary-label {
  display: block;
  font-size: 13px;
  letter-spacing: 0.08em;
  color: rgba(248, 250, 252, 0.76);
}

.summary-value {
  display: block;
  margin-top: 10px;
  color: #fff;
  font-size: clamp(1.9rem, 4vw, 2.4rem);
  line-height: 1.08;
}

@media (max-width: 1100px) {
  .hero-panel {
    padding: 72px 40px 48px;
  }

  .hero-content {
    grid-template-columns: 1fr;
  }

  .hero-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .hero-panel {
    min-height: unset;
    padding: 56px 20px 36px;
    border-radius: 0 0 24px 24px;
  }

  .hero-subtitle {
    font-size: 1rem;
    line-height: 1.7;
  }

  .hero-search {
    grid-template-columns: 1fr;
  }

  .search-button {
    width: 100%;
  }

  .hero-summary {
    grid-template-columns: 1fr;
  }
}
</style>

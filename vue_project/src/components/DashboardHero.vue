<template>
  <section class="hero-panel">
    <div class="hero-backdrop"></div>
    <div class="hero-grain"></div>

    <div class="hero-shell">
      <div class="hero-copy">
        <p class="eyebrow">Gene Data Warehouse</p>
        <h1>基因数据仓库首页</h1>
        <p class="hero-subtitle">
          快速检索与浏览，探索作物种质、组学数据与注释资源。
        </p>

        <div class="hero-pill-row">
          <span class="hero-pill">统一统计口径</span>
          <span class="hero-pill">DataFile 正式资产链路</span>
          <span class="hero-pill">物种 / 亚群 / 地理位置联动浏览</span>
        </div>
      </div>

      <div class="hero-search-block">
        <div class="hero-search">
          <el-input
            v-model="queryText"
            placeholder="全局搜索（物种、亚群、地理位置、数据类型、Accession 等）"
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
            搜索
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
          <span class="summary-note">{{ item.note }}</span>
        </div>
      </div>

      <div class="hero-scroll-tip">
        <span>继续向下浏览数据卡片、分布图与地理分布</span>
        <i class="scroll-arrow"></i>
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
      { key: 'species', label: '物种数', value: props.summary.species_count || 0, note: '系统记录物种' },
      { key: 'accession', label: '材料数', value: props.summary.accession_count || 0, note: '有效材料对象' },
      { key: 'sample', label: '样本数', value: props.summary.sample_count || 0, note: '标准化样本记录' },
      { key: 'file', label: '文件数', value: props.summary.datafile_count || 0, note: '正式 DataFile 资产' },
      { key: 'size', label: '总数据量', value: props.summary.total_size_display || '0 B', note: '可管理文件体量' }
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
  min-height: 650px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(6, 42, 103, 0.26), rgba(5, 30, 74, 0.28)),
    linear-gradient(115deg, #2c5a14 0%, #8aa52b 24%, #5c7d1d 46%, #c29e1f 66%, #4f7715 100%);
  box-shadow: 0 30px 70px rgba(19, 39, 89, 0.22);
}

.hero-panel::before,
.hero-panel::after {
  content: '';
  position: absolute;
  inset: auto;
  pointer-events: none;
}

.hero-panel::before {
  left: -6%;
  right: -6%;
  bottom: -4%;
  height: 56%;
  background:
    radial-gradient(circle at 20% 100%, rgba(20, 84, 18, 0.62), transparent 34%),
    radial-gradient(circle at 35% 100%, rgba(114, 127, 23, 0.55), transparent 28%),
    radial-gradient(circle at 54% 100%, rgba(175, 121, 18, 0.42), transparent 24%),
    radial-gradient(circle at 78% 100%, rgba(42, 93, 26, 0.56), transparent 30%);
  opacity: 0.9;
}

.hero-panel::after {
  top: 0;
  right: -140px;
  width: 440px;
  height: 440px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
}

.hero-backdrop {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 18%, rgba(255, 244, 186, 0.42), transparent 20%),
    radial-gradient(circle at 82% 28%, rgba(255, 255, 255, 0.2), transparent 16%),
    linear-gradient(180deg, rgba(9, 27, 46, 0.08), rgba(9, 27, 46, 0.28));
}

.hero-grain {
  position: absolute;
  inset: 0;
  opacity: 0.14;
  background-image:
    linear-gradient(90deg, rgba(255, 255, 255, 0.28) 1px, transparent 1px),
    linear-gradient(rgba(255, 255, 255, 0.22) 1px, transparent 1px);
  background-size: 120px 120px;
  mix-blend-mode: soft-light;
}

.hero-shell {
  position: relative;
  z-index: 1;
  width: min(1680px, calc(100% - 40px));
  margin: 0 auto;
  padding: 72px 0 116px;
  display: grid;
  gap: 26px;
  justify-items: center;
  text-align: center;
}

.hero-copy {
  max-width: 980px;
  color: #ffffff;
  animation: heroFadeUp 0.72s ease both;
}

.eyebrow {
  margin: 0 0 16px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.88);
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(2.8rem, 4.8vw, 4.5rem);
  line-height: 1.06;
  letter-spacing: 0.04em;
  text-shadow: 0 12px 30px rgba(7, 24, 58, 0.26);
}

.hero-subtitle {
  max-width: 860px;
  margin: 18px auto 0;
  font-size: 1.22rem;
  line-height: 1.8;
  color: rgba(248, 250, 252, 0.94);
}

.hero-pill-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 22px;
  animation: heroFadeUp 0.88s ease both;
}

.hero-pill {
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
}

.hero-search-block {
  width: min(980px, 100%);
  display: grid;
  gap: 18px;
  animation: heroFadeUp 1s ease both;
}

.hero-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
}

.hero-search :deep(.el-input__wrapper) {
  min-height: 84px;
  padding: 0 26px;
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow:
    0 24px 48px rgba(6, 28, 56, 0.2),
    inset 0 0 0 1px rgba(255, 255, 255, 0.68);
}

.hero-search :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 24px 48px rgba(6, 28, 56, 0.2),
    inset 0 0 0 1px rgba(255, 255, 255, 0.78),
    0 0 0 4px rgba(37, 99, 235, 0.16);
}

.hero-search :deep(.el-input__inner) {
  font-size: 20px;
  color: #334155;
}

.hero-search :deep(.el-input__prefix-inner) {
  color: #475569;
  font-size: 26px;
}

.search-button {
  min-width: 170px;
  min-height: 76px;
  padding: 0 34px;
  border: none;
  border-radius: 22px;
  background: linear-gradient(135deg, #0f9f6e 0%, #12815c 100%);
  color: #ffffff;
  font-size: 26px;
  font-weight: 800;
  box-shadow: 0 20px 42px rgba(15, 127, 92, 0.28);
}

.search-button:hover,
.search-button:focus {
  background: linear-gradient(135deg, #12ae77 0%, #0f8b63 100%);
  color: #ffffff;
}

.hot-keywords {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 10px;
}

.hot-label {
  color: rgba(255, 255, 255, 0.88);
  font-size: 15px;
  font-weight: 700;
}

.keyword-chip {
  padding: 8px 16px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 999px;
  background: rgba(64, 90, 20, 0.44);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s ease, background-color 0.2s ease;
}

.keyword-chip:hover {
  transform: translateY(-1px);
  background: rgba(79, 111, 24, 0.62);
}

.hero-summary {
  width: min(1160px, 100%);
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  animation: heroFadeUp 1.12s ease both;
}

.summary-card {
  padding: 18px 18px 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    0 18px 36px rgba(7, 24, 58, 0.14);
  backdrop-filter: blur(12px);
  transition: transform 0.22s ease, background-color 0.22s ease;
}

.summary-card:hover {
  transform: translateY(-4px);
  background: rgba(255, 255, 255, 0.2);
}

.summary-label {
  display: block;
  font-size: 13px;
  letter-spacing: 0.08em;
  color: rgba(241, 245, 249, 0.84);
}

.summary-value {
  display: block;
  margin-top: 10px;
  color: #ffffff;
  font-size: clamp(1.6rem, 3vw, 2.1rem);
  line-height: 1.08;
}

.summary-note {
  display: block;
  margin-top: 8px;
  color: rgba(241, 245, 249, 0.76);
  font-size: 12px;
}

.hero-scroll-tip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  font-weight: 700;
  animation: heroFadeUp 1.2s ease both;
}

.scroll-arrow {
  width: 10px;
  height: 10px;
  border-right: 2px solid rgba(255, 255, 255, 0.85);
  border-bottom: 2px solid rgba(255, 255, 255, 0.85);
  transform: rotate(45deg);
  animation: heroArrowFloat 1.4s ease-in-out infinite;
}

@keyframes heroFadeUp {
  from {
    opacity: 0;
    transform: translateY(14px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes heroArrowFloat {
  0%,
  100% {
    transform: rotate(45deg) translateY(0);
  }

  50% {
    transform: rotate(45deg) translateY(4px);
  }
}

@media (max-width: 1200px) {
  .hero-panel {
    min-height: 590px;
  }

  .hero-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .hero-shell {
    width: min(100%, calc(100% - 24px));
    padding: 56px 0 84px;
  }

  .hero-search {
    grid-template-columns: 1fr;
  }

  .search-button {
    width: 100%;
    min-height: 64px;
    font-size: 20px;
  }

  .hero-search :deep(.el-input__wrapper) {
    min-height: 70px;
  }

  .hero-search :deep(.el-input__inner) {
    font-size: 17px;
  }

  .hero-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .hero-panel {
    min-height: 540px;
  }

  .hero-copy h1 {
    font-size: 2.35rem;
  }

  .hero-subtitle {
    font-size: 1rem;
    line-height: 1.65;
  }

  .hero-summary {
    grid-template-columns: 1fr;
  }

  .hot-keywords,
  .hero-pill-row {
    justify-content: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-copy,
  .hero-pill-row,
  .hero-search-block,
  .hero-summary,
  .hero-scroll-tip,
  .scroll-arrow {
    animation: none;
  }
}
</style>

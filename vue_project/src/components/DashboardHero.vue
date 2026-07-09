<template>
  <section class="hero-panel">
    <div class="hero-backdrop"></div>
    <div class="hero-grain"></div>

    <div class="hero-shell">
      <div class="hero-copy">
        <p class="eyebrow">Gene Data Warehouse</p>
        <h1>基因数据仓库</h1>
        <p class="hero-subtitle">
          快速检索与浏览，探索作物种质、组学数据与注释资源。
        </p>
      </div>

      <div class="hero-search-block">
        <div class="hero-search">
          <el-input
            v-model="queryText"
            placeholder="输入品种名搜索，如IR64"
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

        <div class="search-examples" aria-label="搜索示例">
          <span class="example-label">示例:</span>
          <button
            v-for="example in searchExamples"
            :key="example"
            class="example-link"
            @click="submitExampleSearch(example)"
          >
            {{ example }}
          </button>
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
    </div>
  </section>
</template>

<script>
import { ref } from 'vue'
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
  setup(_, { emit }) {
    const queryText = ref('')
    const searchExamples = ['IR64']

    const submitSearch = () => {
      emit('search', queryText.value)
    }

    const submitExampleSearch = (example) => {
      queryText.value = example
      emit('search', example)
    }

    return {
      queryText,
      searchExamples,
      submitExampleSearch,
      submitSearch
    }
  }
}
</script>

<style scoped>
.hero-panel {
  position: relative;
  min-height: 330px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(6, 42, 103, 0.18), rgba(5, 30, 74, 0.22)),
    linear-gradient(115deg, #2f641b 0%, #9cac35 30%, #6e8526 52%, #c19b22 72%, #4c7219 100%);
  box-shadow: 0 18px 42px rgba(19, 39, 89, 0.18);
}

.hero-panel::before,
.hero-panel::after {
  content: '';
  position: absolute;
  inset: auto;
  pointer-events: none;
}

.hero-panel::before {
  left: -4%;
  right: -4%;
  bottom: -18%;
  height: 56%;
  background:
    radial-gradient(circle at 20% 100%, rgba(20, 84, 18, 0.48), transparent 34%),
    radial-gradient(circle at 42% 100%, rgba(108, 124, 26, 0.42), transparent 30%),
    radial-gradient(circle at 72% 100%, rgba(38, 89, 27, 0.42), transparent 34%);
  opacity: 0.82;
}

.hero-panel::after {
  top: -84px;
  right: -110px;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.11);
}

.hero-backdrop {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 21% 10%, rgba(255, 245, 181, 0.34), transparent 20%),
    radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.16), transparent 18%),
    linear-gradient(180deg, rgba(9, 27, 46, 0.04), rgba(9, 27, 46, 0.18));
}

.hero-grain {
  position: absolute;
  inset: 0;
  opacity: 0.12;
  background-image:
    linear-gradient(90deg, rgba(255, 255, 255, 0.25) 1px, transparent 1px),
    linear-gradient(rgba(255, 255, 255, 0.2) 1px, transparent 1px);
  background-size: 110px 110px;
  mix-blend-mode: soft-light;
}

.hero-shell {
  position: relative;
  z-index: 1;
  width: min(1180px, calc(100% - 40px));
  margin: 0 auto;
  padding: 32px 0 30px;
  display: grid;
  gap: 14px;
  justify-items: center;
  text-align: center;
}

.hero-copy {
  max-width: 820px;
  color: #ffffff;
  animation: heroFadeUp 0.72s ease both;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.9);
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(2.25rem, 3.4vw, 3.1rem);
  line-height: 1.12;
  letter-spacing: 0.04em;
  text-shadow: 0 10px 24px rgba(7, 24, 58, 0.24);
}

.hero-subtitle {
  max-width: 700px;
  margin: 8px auto 0;
  font-size: 16px;
  line-height: 1.55;
  color: rgba(248, 250, 252, 0.94);
}

.hero-search-block {
  width: min(760px, 100%);
  display: grid;
  gap: 10px;
  animation: heroFadeUp 0.9s ease both;
}

.hero-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 120px;
  gap: 12px;
  align-items: center;
}

.hero-search :deep(.el-input__wrapper) {
  min-height: 56px;
  padding: 0 20px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow:
    0 16px 34px rgba(6, 28, 56, 0.18),
    inset 0 0 0 1px rgba(255, 255, 255, 0.68);
}

.hero-search :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 16px 34px rgba(6, 28, 56, 0.18),
    inset 0 0 0 1px rgba(255, 255, 255, 0.78),
    0 0 0 4px rgba(37, 99, 235, 0.16);
}

.hero-search :deep(.el-input__inner) {
  font-size: 16px;
  color: #334155;
}

.hero-search :deep(.el-input__prefix-inner) {
  color: #475569;
  font-size: 22px;
}

.search-button {
  min-width: 120px;
  min-height: 54px;
  padding: 0 22px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #0f9f6e 0%, #12815c 100%);
  color: #ffffff;
  font-size: 18px;
  font-weight: 800;
  box-shadow: 0 16px 34px rgba(15, 127, 92, 0.26);
}

.search-button:hover,
.search-button:focus {
  background: linear-gradient(135deg, #12ae77 0%, #0f8b63 100%);
  color: #ffffff;
}

.search-examples {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 7px;
  margin-top: -2px;
  font-size: 13px;
  font-weight: 700;
}

.example-label {
  color: rgba(255, 255, 255, 0.92);
}

.example-link {
  border: 0;
  padding: 0;
  background: transparent;
  color: #facc15;
  font: inherit;
  cursor: pointer;
  text-shadow: 0 2px 8px rgba(15, 23, 42, 0.24);
}

.example-link:hover,
.example-link:focus {
  color: #fde68a;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.hot-keywords {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 8px;
}

.hot-label {
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  font-weight: 700;
}

.keyword-chip {
  padding: 5px 13px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 999px;
  background: rgba(64, 90, 20, 0.44);
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s ease, background-color 0.2s ease;
}

.keyword-chip:hover {
  transform: translateY(-1px);
  background: rgba(79, 111, 24, 0.62);
}

@keyframes heroFadeUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1200px) {
  .hero-panel {
    min-height: 320px;
  }
}

@media (max-width: 860px) {
  .hero-shell {
    width: min(100%, calc(100% - 24px));
    padding: 30px 0 30px;
  }

  .hero-search {
    grid-template-columns: 1fr;
  }

  .search-button {
    width: 100%;
  }
}

@media (max-width: 560px) {
  .hero-panel {
    min-height: 300px;
  }

  .hero-copy h1 {
    font-size: 2rem;
  }

  .hero-subtitle {
    font-size: 0.95rem;
  }

  .hot-keywords {
    justify-content: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-copy,
  .hero-search-block {
    animation: none;
  }
}
</style>

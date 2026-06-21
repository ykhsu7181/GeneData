<template>
  <section class="species-section">
    <div class="section-header">
      <div class="section-copy">
        <p class="section-kicker">Featured species</p>
        <h2>重点物种卡片</h2>
        <p class="section-description">
          以统一统计口径展示代表性物种的材料、样本与数据集概况。
        </p>
      </div>
    </div>

    <div v-if="cards.length" class="species-grid">
      <article
        v-for="(card, index) in decoratedCards"
        :key="card.species_id"
        class="species-card"
        :style="{
          '--card-accent': card.accent,
          '--card-secondary': card.secondaryAccent,
          '--card-glow': card.glowAccent
        }"
        @click="$emit('select', card)"
      >
        <div class="card-cover">
          <div class="cover-overlay"></div>
          <div class="cover-sheen"></div>
          <span class="card-badge">{{ card.species_code || `SP-${index + 1}` }}</span>
        </div>

        <div class="card-float-mark">
          <span>{{ card.shortName }}</span>
        </div>

        <div class="card-body">
          <div class="card-title">
            <h3>{{ card.name_cn }}</h3>
            <p>{{ card.latin_name }}</p>
          </div>

          <div class="metrics-row">
            <div class="metric-item">
              <span>材料数</span>
              <strong>{{ formatNumber(card.accession_count) }}</strong>
            </div>
            <div class="metric-item">
              <span>样本数</span>
              <strong>{{ formatNumber(card.sample_count) }}</strong>
            </div>
            <div class="metric-item">
              <span>数据集数</span>
              <strong>{{ formatNumber(card.dataset_count) }}</strong>
            </div>
          </div>

          <div class="card-footer">
            <span>进入该物种数据一览</span>
            <i class="footer-arrow"></i>
          </div>
        </div>
      </article>
    </div>

    <div v-else class="empty-state">
      <div class="empty-icon">◌</div>
      <h3>暂无物种卡片数据</h3>
      <p>
        当前首页接口没有返回可展示的物种主数据，建议先进入数据一览页查看已有材料与文件分布。
      </p>
      <button class="empty-action" @click="$emit('browse-all')">
        前往数据一览
      </button>
    </div>
  </section>
</template>

<script>
import { computed } from 'vue'

const CARD_THEMES = [
  {
    accent: '#1f8f5f',
    secondaryAccent: '#8fbf39',
    glowAccent: 'rgba(31, 143, 95, 0.24)'
  },
  {
    accent: '#f2a91b',
    secondaryAccent: '#5f8a19',
    glowAccent: 'rgba(242, 169, 27, 0.24)'
  },
  {
    accent: '#ff7a18',
    secondaryAccent: '#c4a61b',
    glowAccent: 'rgba(255, 122, 24, 0.22)'
  },
  {
    accent: '#3b82f6',
    secondaryAccent: '#5d9a32',
    glowAccent: 'rgba(59, 130, 246, 0.24)'
  }
]

export default {
  name: 'SpeciesCardGrid',
  props: {
    cards: {
      type: Array,
      default: () => []
    }
  },
  emits: ['select', 'browse-all'],
  setup(props) {
    const formatNumber = (value) => Number(value || 0).toLocaleString()
    const shortNameFrom = (card) =>
      (card.name_cn || card.latin_name || card.species_code || 'SP')
        .replace(/\s+/g, '')
        .slice(0, 2)

    const decoratedCards = computed(() =>
      props.cards.map((card, index) => ({
        ...card,
        ...CARD_THEMES[index % CARD_THEMES.length],
        shortName: shortNameFrom(card)
      }))
    )

    return {
      decoratedCards,
      formatNumber
    }
  }
}
</script>

<style scoped>
.species-section {
  display: grid;
  gap: 20px;
}

.section-header {
  display: flex;
  align-items: end;
  justify-content: space-between;
}

.section-kicker {
  margin: 0 0 8px;
  color: #147460;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.section-copy h2 {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  color: #0f172a;
}

.section-description {
  margin: 10px 0 0;
  color: #607085;
  font-size: 15px;
}

.species-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 24px;
}

.species-card {
  position: relative;
  overflow: hidden;
  border-radius: 26px;
  cursor: pointer;
  background: #ffffff;
  border: 1px solid rgba(207, 216, 229, 0.8);
  box-shadow:
    0 18px 36px rgba(12, 35, 66, 0.1),
    0 10px 24px var(--card-glow);
  transition: transform 0.22s ease, box-shadow 0.22s ease;
  animation: cardFadeUp 0.6s ease both;
}

.species-card:nth-child(2) {
  animation-delay: 0.08s;
}

.species-card:nth-child(3) {
  animation-delay: 0.16s;
}

.species-card:nth-child(4) {
  animation-delay: 0.24s;
}

.species-card:hover {
  transform: translateY(-6px);
  box-shadow:
    0 26px 42px rgba(12, 35, 66, 0.14),
    0 14px 28px var(--card-glow);
}

.species-card::after {
  content: '';
  position: absolute;
  inset: auto 0 0;
  height: 4px;
  background: linear-gradient(90deg, var(--card-accent), var(--card-secondary));
}

.card-cover {
  position: relative;
  min-height: 122px;
  background:
    linear-gradient(180deg, rgba(7, 24, 58, 0.08), rgba(7, 24, 58, 0.26)),
    linear-gradient(120deg, var(--card-secondary) 0%, #6ca52f 30%, #d4b533 70%, var(--card-accent) 100%);
}

.card-cover::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 16% 14%, rgba(255, 255, 255, 0.38), transparent 20%),
    radial-gradient(circle at 86% 26%, rgba(255, 255, 255, 0.22), transparent 16%),
    linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(15, 23, 42, 0.2));
}

.cover-overlay {
  position: absolute;
  inset: auto -8% -6% -8%;
  height: 52%;
  background:
    radial-gradient(circle at 18% 100%, rgba(46, 130, 38, 0.5), transparent 28%),
    radial-gradient(circle at 45% 100%, rgba(180, 141, 24, 0.38), transparent 22%),
    radial-gradient(circle at 76% 100%, rgba(63, 118, 25, 0.44), transparent 26%);
}

.cover-sheen {
  position: absolute;
  inset: 0;
  background: linear-gradient(105deg, rgba(255, 255, 255, 0.28), transparent 34%);
  mix-blend-mode: soft-light;
}

.card-badge {
  position: absolute;
  top: 18px;
  right: 18px;
  z-index: 1;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.32);
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.card-float-mark {
  position: absolute;
  top: 94px;
  left: 22px;
  z-index: 2;
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--card-accent), var(--card-secondary));
  border: 4px solid #ffffff;
  color: #ffffff;
  font-size: 22px;
  font-weight: 800;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.18);
}

.card-body {
  padding: 34px 22px 18px;
}

.card-title h3 {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
}

.card-title p {
  margin: 8px 0 0;
  color: #27406a;
  font-size: 15px;
  font-style: italic;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}

.metric-item {
  padding: 12px 10px;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfdff, #f3f8ff);
  border: 1px solid rgba(205, 217, 232, 0.8);
}

.metric-item span {
  display: block;
  color: #55657a;
  font-size: 12px;
  font-weight: 600;
}

.metric-item strong {
  display: block;
  margin-top: 6px;
  color: #0f3e91;
  font-size: 18px;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed rgba(190, 203, 222, 0.9);
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 700;
}

.species-card:hover .card-footer {
  color: #0f3e91;
}

.footer-arrow {
  width: 9px;
  height: 9px;
  border-top: 2px solid currentColor;
  border-right: 2px solid currentColor;
  transform: rotate(45deg);
  transition: transform 0.2s ease;
}

.species-card:hover .footer-arrow {
  transform: rotate(45deg) translate(2px, -2px);
}

@keyframes cardFadeUp {
  from {
    opacity: 0;
    transform: translateY(18px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.empty-state {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 40px 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(205, 217, 232, 0.9);
  color: #64748b;
  text-align: center;
}

.empty-icon {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: linear-gradient(180deg, #eef5ff, #f8fbff);
  color: #2563eb;
  font-size: 24px;
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.08);
}

.empty-state h3 {
  margin: 0;
  color: #173161;
  font-size: 22px;
}

.empty-state p {
  max-width: 620px;
  margin: 0;
  color: #607085;
  font-size: 15px;
  line-height: 1.7;
}

.empty-action {
  margin-top: 6px;
  padding: 12px 18px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.18);
}

@media (max-width: 1320px) {
  .species-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .section-copy h2 {
    font-size: 28px;
  }

  .section-description {
    font-size: 14px;
  }

  .species-grid {
    grid-template-columns: 1fr;
  }

  .metrics-row {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .species-card {
    animation: none;
  }
}
</style>

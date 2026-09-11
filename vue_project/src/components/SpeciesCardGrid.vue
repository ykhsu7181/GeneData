<template>
  <section class="species-section">
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
        </div>
      </article>
    </div>

    <div v-else class="empty-state">
      <span>暂无可展示的物种数据。</span>
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
  setup(props) {
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
      decoratedCards
    }
  }
}
</script>

<style scoped>
.species-section {
  display: grid;
  gap: 0;
}

.species-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 280px));
  justify-content: start;
  gap: 18px;
}

.species-card {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  background: #ffffff;
  border: 1px solid rgba(207, 216, 229, 0.8);
  box-shadow:
    0 12px 24px rgba(12, 35, 66, 0.08),
    0 8px 18px var(--card-glow);
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

.species-card::after {
  content: '';
  position: absolute;
  inset: auto 0 0;
  height: 4px;
  background: linear-gradient(90deg, var(--card-accent), var(--card-secondary));
}

.card-cover {
  position: relative;
  min-height: 56px;
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
  top: 10px;
  right: 10px;
  z-index: 1;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.32);
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.card-float-mark {
  position: absolute;
  top: 38px;
  left: 14px;
  z-index: 2;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--card-accent), var(--card-secondary));
  border: 3px solid #ffffff;
  color: #ffffff;
  font-size: 15px;
  font-weight: 800;
  box-shadow: 0 8px 16px rgba(15, 23, 42, 0.16);
}

.card-body {
  padding: 18px 14px 10px;
}

.card-title h3 {
  margin: 0;
  color: #0f172a;
  font-size: 17px;
}

.card-title p {
  margin: 5px 0 0;
  color: #27406a;
  font-size: 13px;
  font-style: italic;
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
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  min-height: 82px;
  padding: 18px 22px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(205, 217, 232, 0.9);
  color: #64748b;
  text-align: center;
}

.empty-state span {
  color: #607085;
  font-size: 14px;
  line-height: 1.5;
}

@media (max-width: 1320px) {
  .species-grid {
    grid-template-columns: repeat(auto-fit, minmax(220px, 280px));
  }
}

@media (max-width: 720px) {
  .species-grid {
    grid-template-columns: 1fr;
  }

  .empty-state {
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .species-card {
    animation: none;
  }
}
</style>

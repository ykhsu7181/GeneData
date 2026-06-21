<template>
  <section class="section-panel">
    <div class="section-header">
      <div>
        <p class="section-kicker">Species overview</p>
        <h2>重点物种卡片</h2>
      </div>
    </div>

    <div v-if="cards.length" class="species-grid">
      <article
        v-for="card in cards"
        :key="card.species_id"
        class="species-card"
        :style="{ '--card-accent': card.accent_color || '#1d4ed8' }"
        @click="$emit('select', card)">
        <div class="card-cover">
          <div class="card-overlay"></div>
          <div class="card-badge">{{ card.species_code }}</div>
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
        </div>
      </article>
    </div>

    <div v-else class="empty-state">
      暂无物种卡片数据
    </div>
  </section>
</template>

<script>
export default {
  name: 'SpeciesCardGrid',
  props: {
    cards: {
      type: Array,
      default: () => []
    }
  },
  emits: ['select'],
  setup() {
    const formatNumber = (value) => Number(value || 0).toLocaleString()

    return {
      formatNumber
    }
  }
}
</script>

<style scoped>
.section-panel {
  padding: 28px;
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.08);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 22px;
}

.section-kicker {
  margin: 0 0 8px;
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.section-header h2 {
  margin: 0;
  font-size: 28px;
  color: #0f172a;
}

.species-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 22px;
}

.species-card {
  position: relative;
  border-radius: 26px;
  overflow: hidden;
  cursor: pointer;
  background: #fff;
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.1);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.species-card::after {
  content: '';
  display: block;
  height: 4px;
  background: var(--card-accent);
}

.species-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 24px 42px rgba(15, 23, 42, 0.14);
}

.card-cover {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  min-height: 128px;
  padding: 20px;
  background:
    linear-gradient(rgba(15, 23, 42, 0.15), rgba(15, 23, 42, 0.22)),
    linear-gradient(135deg, color-mix(in srgb, var(--card-accent) 48%, #1e293b), #84cc16);
}

.card-overlay {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.28), transparent 46%),
    linear-gradient(180deg, transparent, rgba(15, 23, 42, 0.18));
}

.card-badge {
  position: relative;
  z-index: 1;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.26);
  background: rgba(255, 255, 255, 0.16);
  color: #f8fafc;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  backdrop-filter: blur(12px);
}

.card-body {
  padding: 22px 22px 20px;
}

.card-title h3 {
  margin: 0;
  font-size: 24px;
  color: #0f172a;
}

.card-title p {
  margin: 8px 0 0;
  color: #64748b;
  font-style: italic;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 22px;
}

.metric-item {
  padding: 14px 12px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: linear-gradient(180deg, #f8fafc, #f1f5f9);
}

.metric-item span {
  display: block;
  font-size: 12px;
  color: #64748b;
}

.metric-item strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 18px;
}

.empty-state {
  padding: 36px 18px;
  border-radius: 18px;
  background: #f8fafc;
  color: #64748b;
  text-align: center;
}

@media (max-width: 720px) {
  .section-panel {
    padding: 22px;
  }

  .section-header h2 {
    font-size: 24px;
  }

  .metrics-row {
    grid-template-columns: 1fr;
  }
}
</style>

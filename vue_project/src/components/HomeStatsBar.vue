<template>
  <section class="stats-bar" :aria-label="$t('page.home.stats.ariaLabel')">
    <div class="stats-inner">
      <article v-for="metric in metrics" :key="metric.key" class="metric">
        <span class="metric-icon" aria-hidden="true">
          <svg viewBox="0 0 32 32">
            <circle cx="16" cy="16" r="12"></circle>
            <path :d="metric.icon"></path>
          </svg>
        </span>
        <div>
          <strong>{{ formatCount(summary[metric.key]) }}</strong>
          <span>{{ metric.label }}</span>
        </div>
      </article>

      <p class="values">{{ $t('page.home.stats.slogan') }}</p>
    </div>
  </section>
</template>

<script>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

export default {
  name: 'HomeStatsBar',
  props: { summary: { type: Object, default: () => ({}) } },
  setup() {
    const { locale, t } = useI18n()
    const metrics = computed(() => [
      { key: 'assembly_count', label: t('page.home.stats.assemblies'), icon: 'M10 11h12M10 16h12M10 21h12' },
      { key: 'species_count', label: t('page.home.stats.species'), icon: 'M16 24V10m0 8-5-5m5 2 5-5' },
      { key: 'annotation_count', label: t('page.home.stats.annotations'), icon: 'M11 10h10v12H11zm3 4h4m-4 4h4' },
      { key: 'accession_count', label: t('page.home.stats.accessions'), icon: 'M11 21c1-4 9-4 10 0M16 10a3 3 0 1 0 0 6 3 3 0 0 0 0-6' }
    ])

    const formatCount = (value) => {
      if (value === null || value === undefined || value === '') return '—'
      const number = Number(value)
      const numberLocale = locale.value === 'zh' ? 'zh-CN' : 'en-US'
      return Number.isFinite(number) ? new Intl.NumberFormat(numberLocale).format(number) : value
    }

    return { metrics, formatCount }
  }
}
</script>

<style scoped>
.stats-bar { border-top: 1px solid #e2ebf4; border-bottom: 1px solid #e2ebf4; background: rgba(255, 255, 255, 0.96); }
.stats-inner { width: min(1400px, calc(100% - 44px)); min-height: 112px; margin: 0 auto; display: grid; grid-template-columns: repeat(4, minmax(130px, 1fr)) 1.7fr; align-items: center; gap: 28px; }
.metric { display: flex; align-items: center; gap: 13px; min-width: 0; }
.metric + .metric { position: relative; }
.metric + .metric::before { content: ''; position: absolute; left: -15px; width: 1px; height: 38px; background: #e1e9f2; }
.metric-icon { width: 38px; flex: 0 0 38px; color: #4b6b8f; }
.metric-icon svg { display: block; width: 100%; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.metric strong, .metric span { display: block; }
.metric strong { color: #132c4b; font-size: 1.18rem; line-height: 1.1; }
.metric div span { margin-top: 4px; color: #7890ad; font-size: 0.78rem; }
.values { justify-self: end; margin: 0; padding-left: 28px; border-left: 1px solid #e1e9f2; color: #7890ad; font-size: 0.82rem; white-space: nowrap; }
.values i { margin: 0 10px; color: #91a5bd; font-style: normal; }

@media (max-width: 1100px) {
  .stats-inner { grid-template-columns: repeat(4, 1fr); padding: 22px 0; }
  .values { grid-column: 1 / -1; justify-self: center; padding: 0; border: 0; }
}

@media (max-width: 680px) {
  .stats-inner { width: calc(100% - 24px); grid-template-columns: repeat(2, 1fr); gap: 22px 12px; }
  .metric + .metric::before { display: none; }
  .values { text-align: center; white-space: normal; line-height: 1.8; }
}
</style>

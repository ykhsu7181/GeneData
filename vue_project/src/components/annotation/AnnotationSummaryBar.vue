<template>
  <dl
    class="annotation-summary"
    :aria-label="$t('page.annotation.summaryLabel')"
    :aria-busy="String(loading)"
    aria-live="polite"
  >
    <div class="summary-item">
      <dt>{{ $t('page.annotation.totalFeaturesLabel') }}</dt>
      <dd>{{ display(summary?.total_features) }}</dd>
    </div>
    <div class="summary-item">
      <dt>{{ $t('page.annotation.chromosomeCountLabel') }}</dt>
      <dd>{{ display(summary?.chromosome_count) }}</dd>
    </div>
    <div class="summary-item">
      <dt>{{ $t('page.annotation.featureTypeCountLabel') }}</dt>
      <dd>{{ display(summary?.feature_type_count) }}</dd>
    </div>
  </dl>
</template>

<script>
export default {
  name: 'AnnotationSummaryBar',
  props: {
    summary: { type: Object, default: null },
    loading: Boolean
  },
  setup() {
    const display = value => (value === null || value === undefined ? '—' : value);
    return { display };
  }
};
</script>

<style scoped>
.annotation-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 14px;
  overflow: hidden;
  border: 1px solid #d9e7f7;
  border-radius: 12px;
  background: rgba(255, 255, 255, .96);
  box-shadow: 0 14px 36px rgba(36, 103, 178, .06);
}
.summary-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 60px;
  padding: 0 24px;
  color: #496386;
  font-size: 13px;
  font-weight: 600;
}
.summary-item + .summary-item { border-left: 1px solid #dfe9f5; }
.summary-item dt, .summary-item dd { margin: 0; }
.summary-item dd { color: #075fd7; font-size: 24px; font-weight: 700; line-height: 1; }
@media (max-width: 680px) {
  .annotation-summary {
    grid-template-columns: repeat(3, minmax(180px, 1fr));
    overflow-x: auto;
  }
  .summary-item { padding: 0 16px; }
  .summary-item dd { font-size: 20px; }
}
</style>

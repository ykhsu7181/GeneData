<template>
  <section class="featured-card" aria-labelledby="featured-accessions-title">
    <header class="featured-heading">
      <h3 id="featured-accessions-title"><span aria-hidden="true">★</span> {{ $t('page.home.featuredAccessions') }}</h3>
      <button type="button" @click="$emit('view-all')">{{ $t('common.viewAll') }} <span aria-hidden="true">→</span></button>
    </header>

    <div v-if="loading" class="table-skeleton" :aria-label="$t('page.home.featuredLoading')">
      <span v-for="index in 5" :key="index"></span>
    </div>

    <div v-else-if="error" class="featured-state featured-error">
      <span>{{ error }}</span>
      <button type="button" @click="$emit('retry')">{{ $t('common.retry') }}</button>
    </div>

    <div v-else-if="!items.length" class="featured-state">{{ $t('page.home.featuredEmpty') }}</div>

    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Accession</th>
            <th scope="col">{{ $t('page.home.species') }}</th>
            <th scope="col">{{ $t('page.home.commonName') }}</th>
            <th scope="col">{{ $t('page.home.assembly') }}</th>
            <th scope="col">{{ $t('page.home.annotation') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.accession">
            <td data-label="Accession">
              <button type="button" class="accession-link" @click="$emit('select', item)">
                {{ displayValue(item.accession) }}
              </button>
            </td>
            <td :data-label="$t('page.home.species')"><em>{{ displayValue(item.species_scientific_name) }}</em></td>
            <td :data-label="$t('page.home.commonName')">{{ displayValue(item.species_common_name) }}</td>
            <td :data-label="$t('page.home.assembly')">{{ displayValue(item.assembly) }}</td>
            <td :data-label="$t('page.home.annotation')">{{ displayValue(item.annotation) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script>
export default {
  name: 'FeaturedAccessions',
  props: {
    items: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' }
  },
  emits: ['select', 'view-all', 'retry'],
  setup() {
    const displayValue = (value) => {
      if (value === null || value === undefined || String(value).trim() === '') return '—'
      return value
    }
    return { displayValue }
  }
}
</script>

<style scoped>
.featured-card {
  width: min(900px, calc(100% - 40px));
  margin: 0 auto;
  padding: 20px 24px 22px;
  border: 1px solid #dce8f3;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 18px 42px rgba(34, 85, 140, 0.09);
}

.featured-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 12px;
}

.featured-heading h3 {
  margin: 0;
  color: #122943;
  font-size: 1.1rem;
}

.featured-heading h3 span { margin-right: 7px; color: #17426f; }
.featured-heading button,
.accession-link {
  padding: 4px;
  border: 0;
  background: transparent;
  color: #0e70d9;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
}

.featured-heading button { font-size: 0.85rem; }
.featured-heading button:hover,
.featured-heading button:focus-visible,
.accession-link:hover,
.accession-link:focus-visible { text-decoration: underline; text-underline-offset: 3px; }

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
thead { background: #edf4fa; }
th, td { padding: 11px 13px; border-bottom: 1px solid #e0e9f3; text-align: left; white-space: nowrap; }
th { color: #375170; font-weight: 700; }
td { color: #304661; }
td em { font-style: normal; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: #f8fbff; }
.accession-link { margin: -4px; }

.featured-state {
  min-height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #71859d;
  font-size: 0.92rem;
}

.featured-error { color: #a84848; }
.featured-error button { padding: 7px 13px; border: 1px solid #c9dced; border-radius: 7px; background: #fff; color: #1268cc; cursor: pointer; }
.table-skeleton { display: grid; gap: 9px; padding: 3px 0; }
.table-skeleton span { height: 35px; border-radius: 5px; background: linear-gradient(90deg, #e8eff6 25%, #f8fbff 45%, #e8eff6 65%); background-size: 300% 100%; animation: shimmer 1.3s linear infinite; }

@keyframes shimmer { to { background-position: -150% 0; } }

@media (max-width: 680px) {
  .featured-card { width: calc(100% - 24px); padding: 18px 14px; }
  .table-wrap { overflow: visible; }
  table, tbody, tr, td { display: block; width: 100%; }
  thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
  tbody { display: grid; gap: 12px; }
  tr { padding: 12px 14px; border: 1px solid #dfebf5; border-radius: 10px; background: #fbfdff; }
  td { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 10px; padding: 5px 0; border: 0; white-space: normal; }
  td::before { content: attr(data-label); color: #71859d; font-weight: 650; }
  .accession-link { justify-self: start; text-align: left; }
}

@media (prefers-reduced-motion: reduce) { .table-skeleton span { animation: none; } }
</style>

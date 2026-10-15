<template>
  <section class="overview-stats" :aria-label="$t('page.dataOverview.summary.label')">
    <article v-for="card in cards" :key="card.key" class="stat-card">
      <span class="stat-icon" aria-hidden="true"><el-icon><component :is="card.icon" /></el-icon></span>
      <span>
        <span class="stat-label">{{ card.label }}</span>
        <strong>{{ card.value }}<small v-if="card.unit"> {{ card.unit }}</small></strong>
      </span>
    </article>
  </section>
</template>

<script setup>
/* global defineProps */
import { computed } from 'vue'
import { Collection, DataAnalysis, Document, Location, User } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({ summary: { type: Object, default: () => ({}) } })
const { t } = useI18n()
const cards = computed(() => [
  { key: 'accessions', icon: User, label: t('page.dataOverview.summary.accessions'), value: props.summary.accession_count || 0 },
  { key: 'assemblies', icon: Collection, label: t('page.dataOverview.summary.assemblies'), value: props.summary.assembly_count || 0 },
  { key: 'files', icon: Document, label: t('page.dataOverview.summary.files'), value: props.summary.datafile_count || 0 },
  { key: 'size', icon: DataAnalysis, label: t('page.dataOverview.summary.totalSize'), value: props.summary.total_size_display || '-' },
  { key: 'locations', icon: Location, label: t('page.dataOverview.summary.locations'), value: props.summary.geo_location_count || 0, unit: t('page.dataOverview.summary.locationUnit') }
])
</script>

<style scoped>
.overview-stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin:18px 0}.stat-card{display:flex;align-items:center;gap:13px;min-height:82px;padding:14px 16px;border:1px solid #dce8f6;border-radius:13px;background:#fff;box-shadow:0 7px 22px rgba(25,74,132,.06)}.stat-icon{display:grid;place-items:center;width:42px;height:42px;flex:0 0 auto;border-radius:12px;background:#edf5ff;color:#1672ed;font-size:21px}.stat-label{display:block;color:#647996;font-size:13px}.stat-card strong{display:block;margin-top:3px;color:#0a3474;font-size:22px}.stat-card small{color:#617794;font-size:12px}@media(max-width:1100px){.overview-stats{grid-template-columns:repeat(3,1fr)}}@media(max-width:680px){.overview-stats{grid-template-columns:1fr 1fr}.stat-card:last-child{grid-column:1/-1}}
</style>

<template>
  <div class="portal-home">
    <section class="portal-hero">
      <HomeHero @search="handleSearch" />
      <FeaturedAccessions
        :items="dashboard.featured_accessions"
        :loading="isLoading"
        :error="loadError"
        @select="handleAccessionSelect"
        @view-all="handleViewAllAccessions"
        @retry="loadDashboard"
      />
    </section>

    <HomeStatsBar :summary="dashboard.summary" />
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import FeaturedAccessions from '@/components/FeaturedAccessions.vue'
import HomeHero from '@/components/HomeHero.vue'
import HomeStatsBar from '@/components/HomeStatsBar.vue'
import { resolveDashboardSearch } from '@/config/dashboardSearch'
import { emptyDashboardPayload, fetchDashboardData } from '@/services/dashboard'

export default {
  name: 'DashboardHomeView',
  components: { HomeHero, FeaturedAccessions, HomeStatsBar },
  setup() {
    const router = useRouter()
    const { t } = useI18n()
    const dashboard = ref(emptyDashboardPayload())
    const isLoading = ref(true)
    const loadErrorKey = ref('')
    const loadError = computed(() => (loadErrorKey.value ? t(loadErrorKey.value) : ''))

    const loadDashboard = async () => {
      isLoading.value = true
      loadErrorKey.value = ''
      try {
        dashboard.value = await fetchDashboardData()
      } catch (error) {
        console.error('Failed to load homepage data', error)
        loadErrorKey.value = 'messages.homepageLoadFailed'
      } finally {
        isLoading.value = false
      }
    }

    const handleSearch = (query) => {
      const target = resolveDashboardSearch(query)
      if (target) router.push(target)
    }

    const handleAccessionSelect = (item) => {
      if (!item?.accession) return
      router.push({ name: 'accession-card', query: { accession: item.accession } })
    }

    const handleViewAllAccessions = () => router.push({ name: 'accession-card' })

    onMounted(loadDashboard)

    return {
      dashboard,
      isLoading,
      loadError,
      loadDashboard,
      handleSearch,
      handleAccessionSelect,
      handleViewAllAccessions
    }
  }
}
</script>

<style scoped>
.portal-home { min-height: 100%; background: #f5f9fe; }
.portal-hero {
  position: relative;
  overflow: hidden;
  padding-bottom: 48px;
  background:
    radial-gradient(circle at 50% 12%, rgba(255, 255, 255, 0.98) 0 13%, rgba(250, 253, 255, 0.76) 32%, transparent 52%),
    linear-gradient(180deg, #eaf4ff 0%, #f8fbff 62%, #ebf5ff 100%);
}
.portal-hero::before { content: ''; position: absolute; inset: 0; pointer-events: none; background: radial-gradient(circle at 8% 28%, rgba(90, 164, 226, 0.1), transparent 18rem), radial-gradient(circle at 92% 65%, rgba(90, 164, 226, 0.09), transparent 20rem); }

@media (max-width: 680px) { .portal-hero { padding-bottom: 28px; } }
</style>

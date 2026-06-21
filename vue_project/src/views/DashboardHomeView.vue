<template>
  <div class="dashboard-home">
    <DashboardHero
      :summary="dashboard.summary"
      :hot-keywords="dashboard.hot_keywords"
      @search="handleSearch"
      @keyword-click="handleKeywordClick"
    />

    <section v-if="isLoading" class="dashboard-skeleton-grid">
      <div v-for="index in 4" :key="index" class="dashboard-skeleton-card"></div>
    </section>
    <div v-else-if="loadError" class="dashboard-error">{{ loadError }}</div>
    <template v-else>
      <section class="dashboard-section">
        <SpeciesCardGrid
          :cards="featuredSpeciesCards"
          @select="handleSpeciesSelect"
        />
      </section>

      <section class="distribution-grid">
        <DistributionPanel
          title="亚群分布"
          kicker="Subpopulation"
          :items="dashboard.sub_population_distribution"
          value-key="accession_count"
          empty-text="暂无分布数据"
        />

        <DistributionPanel
          title="XI 组分布"
          kicker="XI groups"
          :items="dashboard.xi_distribution"
          value-key="accession_count"
          empty-text="暂无 XI 组统计数据"
        />
      </section>

      <section class="distribution-grid">
        <DistributionPanel
          title="数据集类型分布"
          kicker="Dataset types"
          :items="dashboard.dataset_type_summary"
          label-key="dataset_type"
          value-key="dataset_count"
          empty-text="暂无分布数据"
        />

        <DistributionPanel
          title="文件类型分布"
          kicker="File roles"
          :items="dashboard.file_role_summary"
          label-key="file_role"
          value-key="datafile_count"
          empty-text="暂无分布数据"
        />
      </section>

      <section class="dashboard-section">
        <GeoMapPanel
          :points="dashboard.geo_distribution"
          @select="handleGeoSelect"
        />
      </section>
    </template>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import DashboardHero from '@/components/DashboardHero.vue'
import DistributionPanel from '@/components/DistributionPanel.vue'
import GeoMapPanel from '@/components/GeoMapPanel.vue'
import SpeciesCardGrid from '@/components/SpeciesCardGrid.vue'
import { keywordToRoute, resolveDashboardSearch } from '@/config/dashboardSearch'
import { emptyDashboardPayload, fetchDashboardData } from '@/services/dashboard'

export default {
  name: 'DashboardHomeView',
  components: {
    DashboardHero,
    SpeciesCardGrid,
    DistributionPanel,
    GeoMapPanel
  },
  setup() {
    const router = useRouter()
    const dashboard = ref(emptyDashboardPayload())
    const isLoading = ref(true)
    const loadError = ref('')

    const featuredSpeciesCards = computed(() => dashboard.value.species_cards.slice(0, 4))

    const loadDashboard = async () => {
      isLoading.value = true
      loadError.value = ''
      try {
        dashboard.value = await fetchDashboardData()
      } catch (error) {
        console.error('Failed to load dashboard data', error)
        loadError.value = '首页统计加载失败，请稍后重试。'
        ElMessage.error(loadError.value)
      } finally {
        isLoading.value = false
      }
    }

    const navigateToRoute = (target) => {
      if (!target) {
        return
      }
      router.push(target)
    }

    const handleSearch = (query) => {
      const target = resolveDashboardSearch(query, dashboard.value)
      navigateToRoute(target)
    }

    const handleKeywordClick = (keyword) => {
      navigateToRoute(keywordToRoute(keyword, dashboard.value))
    }

    const handleSpeciesSelect = (card) => {
      navigateToRoute({
        path: '/data-overview',
        query: {
          search: card.name_cn || card.latin_name || card.species_code
        }
      })
    }

    const handleGeoSelect = (point) => {
      navigateToRoute({
        path: '/accession-map',
        query: {
          region: point.region
        }
      })
    }

    onMounted(() => {
      loadDashboard()
    })

    return {
      dashboard,
      isLoading,
      loadError,
      featuredSpeciesCards,
      handleSearch,
      handleKeywordClick,
      handleSpeciesSelect,
      handleGeoSelect
    }
  }
}
</script>

<style scoped>
.dashboard-home {
  display: grid;
  gap: 28px;
}

.dashboard-error {
  padding: 18px 22px;
  border-radius: 20px;
  font-size: 15px;
}

.dashboard-error {
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.18);
  color: #b91c1c;
}

.dashboard-skeleton-grid,
.dashboard-section,
.distribution-grid {
  display: grid;
  gap: 22px;
}

.dashboard-skeleton-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-skeleton-card {
  min-height: 260px;
  border-radius: 28px;
  background: linear-gradient(90deg, #e2e8f0 25%, #f8fafc 37%, #e2e8f0 63%);
  background-size: 400% 100%;
  animation: dashboardShimmer 1.4s ease infinite;
}

.distribution-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@keyframes dashboardShimmer {
  0% {
    background-position: 100% 0;
  }

  100% {
    background-position: -100% 0;
  }
}

@media (max-width: 960px) {
  .dashboard-skeleton-grid,
  .distribution-grid {
    grid-template-columns: 1fr;
  }
}
</style>

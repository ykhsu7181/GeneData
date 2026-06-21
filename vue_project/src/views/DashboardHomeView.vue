<template>
  <div class="dashboard-home">
    <DashboardHero
      :summary="dashboard.summary"
      :hot-keywords="dashboard.hot_keywords"
      @search="handleSearch"
      @keyword-click="handleKeywordClick"
    />

    <div class="dashboard-content-shell">
      <div v-if="loadError" class="dashboard-error">{{ loadError }}</div>

      <template v-else>
        <section v-if="isLoading" class="dashboard-skeleton-grid dashboard-overlap">
          <div v-for="index in 4" :key="index" class="dashboard-skeleton-card"></div>
        </section>

        <section :class="['species-entry-section', { 'dashboard-overlap': hasFeaturedSpeciesCards }]">
          <SpeciesCardGrid
            :cards="featuredSpeciesCards"
            @select="handleSpeciesSelect"
            @browse-all="handleBrowseAll"
          />
        </section>

        <section class="section-lead">
          <p class="lead-kicker">Distribution insights</p>
          <h2>分布概览</h2>
          <p class="lead-description">
            从亚群、分组、数据集类型与文件角色四个维度，快速了解数据仓库的整体构成。
          </p>
        </section>

        <section v-if="isLoading" class="distribution-grid">
          <div class="panel-skeleton"></div>
          <div class="panel-skeleton"></div>
        </section>

        <section v-else class="distribution-grid">
          <DistributionPanel
            title="亚群分布"
            kicker="Subpopulation"
            :items="dashboard.sub_population_distribution"
            value-key="accession_count"
            empty-text="暂无分布数据"
          />

          <DistributionPanel
            title="群体分组"
            kicker="Grouping summary"
            :items="dashboard.xi_distribution"
            value-key="accession_count"
            empty-text="暂无群体分组统计数据"
          />
        </section>

        <section class="distribution-grid">
          <DistributionPanel
            title="数据集类型分布"
            kicker="Dataset types"
            :items="dashboard.dataset_type_summary"
            label-key="dataset_type"
            value-key="dataset_count"
            empty-text="暂无数据集类型分布"
          />

          <DistributionPanel
            title="文件角色分布"
            kicker="File roles"
            :items="dashboard.file_role_summary"
            label-key="file_role"
            value-key="datafile_count"
            empty-text="暂无文件角色统计数据"
          />
        </section>

        <section class="dashboard-map-section">
          <GeoMapPanel
            :points="dashboard.geo_distribution"
            @select="handleGeoSelect"
          />
        </section>
      </template>
    </div>
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
    const hasFeaturedSpeciesCards = computed(() => featuredSpeciesCards.value.length > 0)

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

    const handleBrowseAll = () => {
      navigateToRoute('/data-overview')
    }

    onMounted(() => {
      loadDashboard()
    })

    return {
      dashboard,
      isLoading,
      loadError,
      featuredSpeciesCards,
      hasFeaturedSpeciesCards,
      handleSearch,
      handleKeywordClick,
      handleSpeciesSelect,
      handleGeoSelect,
      handleBrowseAll
    }
  }
}
</script>

<style scoped>
.dashboard-home {
  display: grid;
  gap: 0;
  padding-bottom: 34px;
}

.dashboard-content-shell {
  width: min(1680px, calc(100% - 40px));
  margin: 0 auto;
  display: grid;
  gap: 30px;
  position: relative;
}

.dashboard-overlap {
  margin-top: -78px;
  position: relative;
  z-index: 2;
}

.species-entry-section {
  position: relative;
  z-index: 2;
}

.dashboard-content-shell::before {
  content: '';
  position: absolute;
  top: 140px;
  left: -80px;
  width: 260px;
  height: 260px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.1), transparent 68%);
  pointer-events: none;
}

.dashboard-content-shell::after {
  content: '';
  position: absolute;
  top: 760px;
  right: -60px;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(16, 185, 129, 0.08), transparent 68%);
  pointer-events: none;
}

.distribution-grid,
.dashboard-map-section,
.dashboard-skeleton-grid,
.dashboard-error,
.section-lead {
  width: 100%;
}

@keyframes dashboardShimmer {
  0% {
    background-position: 100% 0;
  }

  100% {
    background-position: -100% 0;
  }
}

.dashboard-error {
  margin-top: 26px;
  padding: 18px 22px;
  border-radius: 20px;
  font-size: 15px;
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.18);
  color: #b91c1c;
}

.dashboard-skeleton-grid {
  display: grid;
  gap: 24px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-skeleton-card {
  min-height: 285px;
  border-radius: 28px;
  background: linear-gradient(90deg, #dde7f3 25%, #f8fbff 37%, #dde7f3 63%);
  background-size: 400% 100%;
  animation: dashboardShimmer 1.4s ease infinite;
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.08);
}

.panel-skeleton {
  min-height: 360px;
  border-radius: 26px;
  background: linear-gradient(90deg, #dde7f3 25%, #f8fbff 37%, #dde7f3 63%);
  background-size: 400% 100%;
  animation: dashboardShimmer 1.4s ease infinite;
}

.section-lead {
  padding: 6px 4px 0;
  position: relative;
  z-index: 1;
}

.lead-kicker {
  margin: 0 0 8px;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.section-lead h2 {
  margin: 0;
  color: #0f172a;
  font-size: 34px;
}

.lead-description {
  margin: 10px 0 0;
  color: #607085;
  font-size: 15px;
  line-height: 1.7;
  max-width: 780px;
}

.distribution-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

@media (max-width: 960px) {
  .dashboard-content-shell {
    width: min(100%, calc(100% - 24px));
    gap: 22px;
  }

  .dashboard-content-shell::before,
  .dashboard-content-shell::after {
    display: none;
  }

  .dashboard-overlap {
    margin-top: -48px;
  }

  .dashboard-skeleton-grid,
  .distribution-grid {
    grid-template-columns: 1fr;
  }

  .section-lead h2 {
    font-size: 28px;
  }

  .lead-description {
    font-size: 14px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dashboard-skeleton-card,
  .panel-skeleton {
    animation: none;
    background-position: 50% 0;
  }
}
</style>

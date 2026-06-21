<template>
  <div class="dashboard-home">
    <DashboardHero
      :summary="dashboard.summary"
      :hot-keywords="dashboard.hot_keywords"
      @search="handleSearch"
      @keyword-click="handleKeywordClick"
    />

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

    const featuredSpeciesCards = computed(() => dashboard.value.species_cards.slice(0, 4))

    const loadDashboard = async () => {
      try {
        dashboard.value = await fetchDashboardData()
      } catch (error) {
        console.error('Failed to load dashboard data', error)
        ElMessage.error('首页统计加载失败')
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

.dashboard-section,
.distribution-grid {
  display: grid;
  gap: 22px;
}

.distribution-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 960px) {
  .distribution-grid {
    grid-template-columns: 1fr;
  }
}
</style>

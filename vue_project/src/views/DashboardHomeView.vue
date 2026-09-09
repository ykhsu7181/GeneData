<template>
  <div class="dashboard-home">
    <DashboardHero
      :summary="dashboard.summary"
      :hot-keywords="dashboard.hot_keywords"
      @search="handleSearch"
      @keyword-click="handleKeywordClick"
    />

    <div class="dashboard-content-shell">
      <template v-if="isLoading">
        <section class="dashboard-skeleton-grid dashboard-overlap">
          <div v-for="index in 4" :key="index" class="dashboard-skeleton-card"></div>
        </section>

        <section class="resource-distribution-row">
          <div class="panel-skeleton"></div>
          <div class="panel-skeleton"></div>
        </section>
      </template>

      <div v-else-if="loadError" class="dashboard-error">{{ loadError }}</div>

      <template v-else>
        <section :class="['species-entry-section', { 'dashboard-overlap': hasFeaturedSpeciesCards }]">
          <SpeciesCardGrid
            :cards="featuredSpeciesCards"
            @select="handleSpeciesSelect"
            @browse-all="handleBrowseAll"
          />
        </section>

        <section class="resource-distribution-row">
          <DataResourceSummary
            :items="dashboard.resource_summary"
            @navigate="navigateToRoute"
          />

          <div ref="distributionLazyRef" class="distribution-lazy-slot">
            <DistributionPanel
              v-if="shouldRenderDistribution"
              title="亚群分布"
              kicker="Subpopulation"
              :items="dashboard.sub_population_distribution"
              value-key="accession_count"
              empty-text="暂无分布数据"
            />
            <section v-else class="dashboard-lazy-placeholder">
              <span class="lazy-dot"></span>
              <strong>亚群分布将在滚动到此区域后加载</strong>
              <p>先展示首页主内容，降低首屏 ECharts 初始化压力。</p>
            </section>
          </div>
        </section>

        <section class="dashboard-map-section">
          <div ref="geoLazyRef">
            <GeoMapPanel
              v-if="shouldRenderGeoMap"
              :points="dashboard.geo_distribution"
              @select="handleGeoSelect"
            />
            <section v-else class="dashboard-lazy-placeholder dashboard-map-placeholder">
              <span class="lazy-dot"></span>
              <strong>地理分布地图将在滚动到此区域后加载</strong>
              <p>地图 GeoJSON 与 ECharts 地图模块会延后请求，避免拖慢首页首屏。</p>
            </section>
          </div>
          <RecentUpdatesBar
            :items="dashboard.recent_updates"
            @navigate="navigateToRoute"
          />
        </section>
      </template>
    </div>
  </div>
</template>

<script>
import { computed, defineAsyncComponent, h, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import DataResourceSummary from '@/components/DataResourceSummary.vue'
import DashboardHero from '@/components/DashboardHero.vue'
import RecentUpdatesBar from '@/components/RecentUpdatesBar.vue'
import SpeciesCardGrid from '@/components/SpeciesCardGrid.vue'
import { keywordToRoute, resolveDashboardSearch } from '@/config/dashboardSearch'
import { emptyDashboardPayload, fetchDashboardData } from '@/services/dashboard'

const AsyncLoadingBlock = {
  name: 'DashboardAsyncLoadingBlock',
  render() {
    return h('section', { class: 'dashboard-lazy-placeholder' }, [
      h('span', { class: 'lazy-dot' }),
      h('strong', '模块加载中'),
      h('p', '正在按需加载图表资源。')
    ])
  }
}

const DistributionPanel = defineAsyncComponent({
  loader: () => import('@/components/DistributionPanel.vue'),
  loadingComponent: AsyncLoadingBlock,
  delay: 120
})

const GeoMapPanel = defineAsyncComponent({
  loader: () => import('@/components/GeoMapPanel.vue'),
  loadingComponent: AsyncLoadingBlock,
  delay: 120
})

export default {
  name: 'DashboardHomeView',
  components: {
    DashboardHero,
    SpeciesCardGrid,
    DataResourceSummary,
    DistributionPanel,
    GeoMapPanel,
    RecentUpdatesBar
  },
  setup() {
    const router = useRouter()
    const dashboard = ref(emptyDashboardPayload())
    const isLoading = ref(true)
    const loadError = ref('')
    const distributionLazyRef = ref(null)
    const geoLazyRef = ref(null)
    const shouldRenderDistribution = ref(false)
    const shouldRenderGeoMap = ref(false)
    const lazyObservers = []

    const featuredSpeciesCards = computed(() => dashboard.value.species_cards.slice(0, 4))
    const hasFeaturedSpeciesCards = computed(() => featuredSpeciesCards.value.length > 0)

    const stopLazyObservers = () => {
      while (lazyObservers.length) {
        const observer = lazyObservers.pop()
        observer.disconnect()
      }
    }

    const observeLazySection = (targetRef, renderFlag) => {
      if (renderFlag.value || !targetRef.value) {
        return
      }

      if (!('IntersectionObserver' in window)) {
        renderFlag.value = true
        return
      }

      const observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) {
            renderFlag.value = true
            observer.disconnect()
          }
        },
        {
          rootMargin: '280px 0px',
          threshold: 0.01
        }
      )

      observer.observe(targetRef.value)
      lazyObservers.push(observer)
    }

    const setupLazySections = async () => {
      await nextTick()
      observeLazySection(distributionLazyRef, shouldRenderDistribution)
      observeLazySection(geoLazyRef, shouldRenderGeoMap)
    }

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
        setupLazySections()
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

    onBeforeUnmount(() => {
      stopLazyObservers()
    })

    return {
      dashboard,
      isLoading,
      loadError,
      distributionLazyRef,
      geoLazyRef,
      shouldRenderDistribution,
      shouldRenderGeoMap,
      featuredSpeciesCards,
      hasFeaturedSpeciesCards,
      navigateToRoute,
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
  margin-top: -28px;
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

.resource-distribution-row,
.dashboard-map-section,
.dashboard-skeleton-grid,
.dashboard-error {
  width: 100%;
}

.dashboard-map-section {
  display: grid;
  gap: 16px;
}

.distribution-lazy-slot {
  min-width: 0;
}

.dashboard-lazy-placeholder {
  min-height: 360px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  padding: 28px;
  border-radius: 28px;
  border: 1px solid rgba(210, 221, 236, 0.9);
  background:
    radial-gradient(circle at 50% 36%, rgba(37, 99, 235, 0.08), transparent 42%),
    linear-gradient(180deg, #ffffff, #f7fbff);
  color: #607085;
  text-align: center;
  box-shadow: 0 18px 40px rgba(14, 30, 66, 0.06);
}

.dashboard-map-placeholder {
  min-height: 540px;
}

.dashboard-lazy-placeholder strong {
  color: #18315f;
  font-size: 16px;
}

.dashboard-lazy-placeholder p {
  max-width: 420px;
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}

.lazy-dot {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  border: 3px solid rgba(37, 99, 235, 0.18);
  border-top-color: #2563eb;
  animation: lazySpin 0.8s linear infinite;
}

@keyframes lazySpin {
  to {
    transform: rotate(360deg);
  }
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

.resource-distribution-row {
  display: grid;
  grid-template-columns: minmax(420px, 0.92fr) minmax(520px, 1.08fr);
  gap: 24px;
  align-items: stretch;
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
    margin-top: 0;
  }

  .dashboard-skeleton-grid,
  .resource-distribution-row {
    grid-template-columns: 1fr;
  }

}

@media (prefers-reduced-motion: reduce) {
  .dashboard-skeleton-card,
  .panel-skeleton,
  .lazy-dot {
    animation: none;
    background-position: 50% 0;
  }
}
</style>

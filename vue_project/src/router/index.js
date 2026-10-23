import { createRouter, createWebHashHistory } from 'vue-router'
import axios from 'axios'

const EmptyComponent = {
  template: '<div class="empty-page"><h2>{{ $t("page.placeholder.developing") }}</h2></div>'
}

const routes = [
  {
    path: '/login',
    redirect: '/dashboard'
  },
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'dashboard-home',
    component: () => import('../views/DashboardHomeView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/assembly',
    name: 'assembly',
    component: () => import('../views/AssemblyPortalView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/assembly/:assemblyId/browser',
    name: 'assembly-browser',
    component: () => import('../views/GenomeBrowserView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/assembly/:assemblyId',
    name: 'assembly-detail',
    component: () => import('../views/AssemblyView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/data',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/transcriptome',
    name: 'transcriptome',
    component: () => import('../views/TranscriptomeView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/data-chart',
    name: 'data-chart',
    component: () => import('../views/DataChartView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/data-overview',
    name: 'data-overview',
    component: () => import('../views/DataOverviewView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/raw-data',
    name: 'raw-data',
    component: () => import('../views/RawDataView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/transcriptome-overview',
    name: 'transcriptome-overview',
    component: () => import('../views/TranscriptomeOverviewView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/accession-map',
    name: 'accession-map',
    component: () => import('../views/AccessionMapView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/genome-card',
    name: 'genome-card',
    redirect: (to) => {
      const firstQueryValue = (value) => Array.isArray(value) ? value[0] : value
      const assemblyId = String(firstQueryValue(to.query.assembly) || '').trim()
      const accession = String(
        firstQueryValue(to.query.accession) || firstQueryValue(to.query.organism) || ''
      ).trim()

      if (/^\d+$/.test(assemblyId)) {
        return { name: 'assembly-detail', params: { assemblyId } }
      }
      if (accession) {
        return { name: 'accession-detail', query: { accession } }
      }
      return { name: 'accession-card' }
    },
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/annotation',
    name: 'annotation',
    component: () => import('../views/AnnotationView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/annotation-card',
    name: 'annotation-card',
    component: () => import('../views/AnnotationView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/core-variable-blocks',
    name: 'core-variable-blocks',
    component: () => import('../views/CoreVariableBlocks.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/core-variable-blocks-card',
    name: 'core-variable-blocks-card',
    component: () => import('../views/CoreVariableBlocks.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/codon-card',
    name: 'codon-card',
    component: () => import('../views/CodonCard.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/accession-card',
    name: 'accession-card',
    component: () => import('../views/AccessionCard.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/accession-detail',
    name: 'accession-detail',
    component: () => import('../views/AccessionDetailTableView.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/tools/codonw',
    name: 'tools-codonw',
    component: () => import('../views/CodonWTool.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/placeholder',
    name: 'placeholder',
    component: EmptyComponent,
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/admin/login',
    name: 'admin-login',
    component: () => import('../views/AdminLogin.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/admin/dashboard',
    name: 'admin-dashboard',
    component: () => import('../views/AdminDashboard.vue'),
    meta: {
      requiresAdminAuth: true
    }
  },
  {
    path: '/admin',
    redirect: '/admin/dashboard'
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

const hasAdminSession = async () => {
  try {
    const response = await axios.get('/admin/session/')
    return response.data.authenticated === true && response.data.user?.is_staff === true
  } catch (error) {
    return false
  }
}

router.beforeEach(async (to, from, next) => {
  if (to.matched.some((record) => record.meta.requiresAdminAuth)) {
    if (!(await hasAdminSession())) {
      next('/admin/login')
      return
    }
  }

  if (to.path === '/admin/login' && await hasAdminSession()) {
    next('/admin/dashboard')
    return
  }

  next()
})

export default router

import { createRouter, createWebHashHistory } from 'vue-router'

// 创建空白页面组件
const EmptyComponent = {
  template: '<div class="empty-page"><h2>功能开发中，敬请期待...</h2></div>'
}

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue')
  },
  {
    path: '/',
    redirect: '/data'
  },
  {
    path: '/data',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { 
      requiresAuth: true,
      parent: 'download' 
    }
  },
  {
    path: '/transcriptome',
    name: 'transcriptome',
    component: () => import('../views/TranscriptomeView.vue'),
    meta: { 
      requiresAuth: true,
      parent: 'download' 
    }
  },
  {
    path: '/data-chart',
    name: 'data-chart',
    component: () => import('../views/DataChartView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/data-overview',
    name: 'data-overview',
    component: () => import('../views/DataOverviewView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/transcriptome-overview',
    name: 'transcriptome-overview',
    component: () => import('../views/TranscriptomeOverviewView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/accession-map',
    name: 'accession-map',
    component: () => import('../views/AccessionMapView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/accession-card',
    name: 'accession-card',
    component: EmptyComponent,
    meta: { 
      requiresAuth: true
    }
  },
  {
    path: '/genome-card',
    name: 'genome-card',
    component: () => import('../views/GenomeCard.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/annotation',
    name: 'annotation',
    component: () => import('../views/AnnotationView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/annotation-card',
    name: 'annotation-card',
    component: () => import('../views/AnnotationView.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/core-variable-blocks',
    name: 'core-variable-blocks',
    component: () => import('../views/CoreVariableBlocks.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/core-variable-blocks-card',
    name: 'core-variable-blocks-card',
    component: () => import('../views/CoreVariableBlocks.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/codon-card',
    name: 'codon-card',
    component: () => import('../views/CodonCard.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/accession-card',
    name: 'accession-card',
    component: () => import('../views/AccessionCard.vue'),
    meta: {
      requiresAuth: true
    }
  },

  {
    path: '/tools/codonw',
    name: 'tools-codonw',
    component: () => import('../views/CodonWTool.vue'),
    meta: {
      requiresAuth: true,
      parent: 'tools'
    }
  },

  // 管理后台路由
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

// 导航守卫
router.beforeEach((to, from, next) => {
  const isLoggedIn = localStorage.getItem('isLoggedIn') === 'true'
  const adminToken = localStorage.getItem('admin_token')

  // 检查管理员认证
  if (to.matched.some(record => record.meta.requiresAdminAuth)) {
    if (!adminToken) {
      next('/admin/login')
      return
    }
  }

  // 如果需要普通用户登录但未登录，则重定向到登录页
  if (to.matched.some(record => record.meta.requiresAuth) && !isLoggedIn) {
    next('/login')
  } else {
    // 如果已登录且尝试访问登录页，则重定向到首页
    if (to.path === '/login' && isLoggedIn) {
      next('/data')
    } else if (to.path === '/admin/login' && adminToken) {
      // 如果已有管理员token且尝试访问管理员登录页，则重定向到管理后台
      next('/admin/dashboard')
    } else {
      next()
    }
  }
})

export default router 
<template>
  <div class="app-container">
    <!-- 登录页面和管理后台页面不显示主布局 -->
    <router-view v-if="$route.path === '/login' || $route.path.startsWith('/admin')" />

    <el-container v-else>
      <el-aside width="220px">
        <div class="logo">
          <h2>{{ currentLanguage === 'zh' ? '基因数据管理系统' : 'Gene Data Management' }}</h2>
        </div>
        <el-menu
          router
          :default-active="activeMenu"
          :default-openeds="defaultOpeneds"
          class="sidebar-menu">
          
          <el-menu-item index="/data-chart">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.dataChart') }}</span>
          </el-menu-item>

          <el-menu-item index="/data-overview">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.dataOverview') }}</span>
          </el-menu-item>

          <el-menu-item index="/transcriptome-overview">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.transcriptomeOverview') }}</span>
          </el-menu-item>

          <el-menu-item index="/accession-map">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.accessionMap') }}</span>
          </el-menu-item>

          <el-menu-item index="/accession-card">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.accession') }}</span>
          </el-menu-item>

          <el-menu-item index="/genome-card">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.genome') }}</span>
          </el-menu-item>

          <el-menu-item index="/annotation">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.annotation') }}</span>
          </el-menu-item>

          <el-menu-item index="/core-variable-blocks">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.coreVariableBlocks') }}</span>
          </el-menu-item>

          <el-menu-item index="/codon-card">
            <el-icon><menu /></el-icon>
            <span>{{ $t('nav.codon') }}</span>
          </el-menu-item>
          
          <el-sub-menu index="tools">
            <template #title>
              <el-icon><collection /></el-icon>
              <span>{{ $t('nav.tools') }}</span>
            </template>
            <el-menu-item index="/tools/codonw">
              <span>{{ $t('nav.codonw') }}</span>
            </el-menu-item>
          </el-sub-menu>


          <el-sub-menu index="download">
            <template #title>
              <el-icon><download /></el-icon>
              <span>{{ $t('nav.download') }}</span>
            </template>
            <el-menu-item index="/data">
              <span>{{ $t('nav.allData') }}</span>
            </el-menu-item>
            <el-menu-item index="/transcriptome">
              <span>{{ $t('nav.transcriptome') }}</span>
            </el-menu-item>
          </el-sub-menu>
          
        </el-menu>
        <div class="sidebar-footer">
          <p>{{ $t('footer.copyright') }}</p>
        </div>
      </el-aside>
      
      <el-container>
        <el-header height="60px">
          <div class="header-content">
            <div class="breadcrumb">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item :to="{ path: '/home' }">{{ $t('nav.home') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-if="activeMenu === '/data-chart'">{{ $t('nav.dataChart') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/data-overview'">{{ $t('nav.dataOverview') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/transcriptome-overview'">{{ $t('nav.transcriptomeOverview') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/accession-map'">{{ $t('nav.accessionMap') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/accession-card'">{{ $t('nav.accession') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/genome-card'">{{ $t('nav.genome') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/annotation'">{{ $t('nav.annotation') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/core-variable-blocks'">{{ $t('nav.coreVariableBlocks') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/codon-card'">{{ $t('nav.codon') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/tools/blast' || activeMenu === '/tools/primer' || activeMenu === '/tools/sequence' || activeMenu === '/tools/codonw'">{{ $t('nav.tools') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/data' || activeMenu === '/transcriptome'">{{ $t('nav.download') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-if="activeMenu === '/tools/codonw'">{{ $t('nav.codonw') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/transcriptome'">{{ $t('nav.transcriptome') }}</el-breadcrumb-item>
                <el-breadcrumb-item v-else-if="activeMenu === '/data'">{{ $t('nav.allData') }}</el-breadcrumb-item>
              </el-breadcrumb>
            </div>
            <div class="user-info">
              <!-- 语言选择器 -->
              <el-dropdown @command="handleLanguageChange" class="language-selector">
                <el-button size="small" text>
                  <el-icon><Switch /></el-icon>
                  <span>{{ currentLanguage === 'zh' ? '中文' : 'English' }}</span>
                  <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="zh" :class="{ 'is-active': currentLanguage === 'zh' }">
                      中文
                    </el-dropdown-item>
                    <el-dropdown-item command="en" :class="{ 'is-active': currentLanguage === 'en' }">
                      English
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>

              <span class="username">{{ $t('common.currentUser') }}: root</span>
              <el-button type="danger" size="small" @click="handleLogout" plain>{{ $t('common.logout') }}</el-button>
            </div>
          </div>
        </el-header>
        <el-main>
          <router-view />
        </el-main>
        <el-footer height="40px">
          <div class="footer-content">
            <span>{{ $t('footer.version') }}</span>
          </div>
        </el-footer>
      </el-container>
    </el-container>
  </div>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Document, Menu, Download, Collection, DataAnalysis, Connection, Switch, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

export default {
  name: 'App',
  components: {
    Document,
    Menu,
    Download,
    Collection,
    DataAnalysis,
    Connection,
    Switch,
    ArrowDown
  },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const { locale } = useI18n()

    // 当前语言
    const currentLanguage = ref(locale.value)

    // 监听语言变化
    watch(locale, (newLocale) => {
      currentLanguage.value = newLocale
    })

    // 计算当前激活的菜单
    const activeMenu = computed(() => {
      // 如果当前路由有父菜单，且当前路径是子菜单，则返回当前路径
      // 否则如果路由元信息中有parent属性，则返回parent值作为激活的父菜单
      if (route.meta.parent === 'download' && (route.path === '/data' || route.path === '/transcriptome')) {
        return route.path;
      }
      if (route.meta.parent === 'tools' && (route.path.startsWith('/tools/'))) {
        return route.path;
      }
      return route.meta.parent || route.path;
    })
    
    // 默认展开的子菜单
    const defaultOpeneds = computed(() => {
      // 如果当前路由有父菜单，则默认展开该父菜单
      if (route.meta.parent) {
        return [route.meta.parent];
      }
      return [];
    })
    
    // 处理语言切换
    const handleLanguageChange = (language) => {
      console.log('切换语言到:', language)
      locale.value = language
      currentLanguage.value = language
      localStorage.setItem('language', language)

      ElMessage({
        message: language === 'zh' ? '已切换到中文' : 'Switched to English',
        type: 'success'
      })
    }

    // 处理退出登录
    const handleLogout = () => {
      // 清除登录状态
      localStorage.removeItem('isLoggedIn')

      // 显示退出成功提示
      ElMessage({
        message: currentLanguage.value === 'zh' ? '已退出登录' : 'Logged out successfully',
        type: 'success'
      })

      // 跳转到登录页
      router.push('/login')
    }

    return {
      activeMenu,
      defaultOpeneds,
      currentLanguage,
      handleLanguageChange,
      handleLogout
    }
  }
}
</script>

<style>


* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', Arial, sans-serif;
  color: #2c3e50;
  background-color: #f9fafb;
}

#app {
  width: 100vw;
  height: 100vh;
}

.app-container {
  width: 100%;
  height: 100%;
}

.el-container {
  width: 100%;
  height: 100%;
}

.el-aside {
  background-color: #001529;
  color: #fff;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background-color: #002140;
}

.logo h2 {
  font-size: 18px;
  color: #fff;
  font-weight: bold;
}

.sidebar-menu {
  border-right: none;
  background-color: #001529;
}

.el-menu {
  border-right: none !important;
  background-color: transparent !important;
}

.el-menu-item {
  color: rgba(255, 255, 255, 0.65) !important;
}

.el-menu-item.is-active {
  color: #fff !important;
  background-color: #1890ff !important;
}

.el-menu-item:hover {
  color: #fff !important;
  background-color: #1890ff !important;
}

/* 子菜单样式 */
.el-sub-menu__title {
  color: rgba(255, 255, 255, 0.65) !important;
}

.el-sub-menu__title:hover {
  color: #fff !important;
  background-color: #1890ff !important;
}

.el-sub-menu.is-active .el-sub-menu__title {
  color: #fff !important;
}

.el-sub-menu .el-menu-item {
  min-width: auto !important;
  padding-left: 50px !important;
}

.sidebar-footer {
  margin-top: auto;
  padding: 15px;
  font-size: 12px;
  text-align: center;
  color: rgba(255, 255, 255, 0.45);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.el-header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  padding: 0 20px;
}

.header-content {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.breadcrumb {
  font-size: 14px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.language-selector {
  margin-right: 5px;
}

.language-selector .el-button {
  color: #606266;
  border: none;
  background: transparent;
  padding: 8px 12px;
}

.language-selector .el-button:hover {
  color: #1a56db;
  background-color: #f0f5ff;
}

.language-selector .el-dropdown-menu .el-dropdown-item.is-active {
  color: #1a56db;
  font-weight: 500;
}

.username {
  font-size: 14px;
  color: #606266;
}

.el-main {
  background-color: #f9fafb;
  padding: 20px;
  height: calc(100% - 100px);
}

.el-footer {
  background-color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #909399;
  border-top: 1px solid #e6e6e6;
}

.footer-content {
  text-align: center;
}

/* 空页面样式 */
.empty-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 24px;
}

.empty-page h2 {
  color: #909399;
  font-size: 24px;
  font-weight: 500;
}
</style>

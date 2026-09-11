<template>
  <div class="admin-dashboard">
    <!-- 顶部导航栏 -->
    <div class="admin-header">
      <div class="header-left">
        <h1>基因数据管理系统</h1>
      </div>
      <div class="header-right">
        <span class="user-info">欢迎，{{ userInfo.username }}</span>
        <el-button type="danger" size="small" @click="handleLogout">退出登录</el-button>
      </div>
    </div>
    
    <!-- 主要内容区域 -->
    <div class="admin-content">
      <!-- 侧边菜单 -->
      <div class="admin-sidebar">
        <el-menu
          :default-active="activeMenu"
          class="sidebar-menu"
          @select="handleMenuSelect"
        >
          <el-menu-item index="dashboard">
            <el-icon><DataBoard /></el-icon>
            <span>数据统计</span>
          </el-menu-item>
          <el-menu-item index="files">
            <el-icon><Document /></el-icon>
            <span>文件管理</span>
          </el-menu-item>
          <el-menu-item index="data-management">
            <el-icon><FolderOpened /></el-icon>
            <span>数据表格管理</span>
          </el-menu-item>
        </el-menu>
      </div>
      
      <!-- 主内容区 -->
      <div class="admin-main">
        <!-- 数据统计页面 -->
        <div v-if="activeMenu === 'dashboard'" class="dashboard-content">
          <h2>数据统计</h2>
          
          <div class="stats-cards" v-loading="statsLoading">
            <div class="stat-card">
              <div class="stat-icon">
                <el-icon><Document /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-number">{{ statistics.total_files || 0 }}</div>
                <div class="stat-label">总文件数</div>
              </div>
            </div>

            <div class="stat-card">
              <div class="stat-icon">
                <el-icon><FolderOpened /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-number">{{ statistics.total_size_mb || 0 }} MB</div>
                <div class="stat-label">总文件大小</div>
              </div>
            </div>
          </div>

          <!-- 亚群统计 -->
          <div class="subpopulation-stats">
            <h3>按亚群统计</h3>
            <div class="stats-table" v-loading="subpopStatsLoading">
              <div class="stats-header">
                <span class="stats-col-1">亚群</span>
                <span class="stats-col-2">Accession数量</span>
                <span class="stats-col-3">文件数</span>
                <span class="stats-col-4">文件总大小</span>
              </div>
              <div v-for="stat in subpopulationStats" :key="stat.subpopulation" class="stats-row">
                <span class="stats-col-1">{{ stat.subpopulation }}</span>
                <span class="stats-col-2">{{ stat.accession_count }}</span>
                <span class="stats-col-3">{{ stat.file_count }}</span>
                <span class="stats-col-4">{{ formatFileSize(stat.total_size) }}</span>
              </div>
            </div>
          </div>

          <!-- 分类统计 -->
          <div class="category-stats">
            <h3>按类别统计</h3>
            <div class="stats-table">
              <div class="stats-header">
                <span class="stats-col-1">类别</span>
                <span class="stats-col-2">Accession数量</span>
                <span class="stats-col-3">文件数</span>
                <span class="stats-col-4">文件总大小</span>
              </div>
              <div v-for="(stats, category) in statistics.category_stats" :key="category" class="stats-row">
                <span class="stats-col-1">{{ category }}</span>
                <span class="stats-col-2">{{ formatAccessionCount(stats.accession_count) }}</span>
                <span class="stats-col-3">{{ stats.file_count }}</span>
                <span class="stats-col-4">{{ formatFileSize(stats.total_size) }}</span>
              </div>
            </div>
          </div>
          

        </div>

        <!-- 文件管理页面 -->
        <AdminFileManager v-if="activeMenu === 'files'" @refresh-stats="loadStatistics" />

        <!-- 数据表格管理页面 -->
        <AdminDataManager v-if="activeMenu === 'data-management'" />
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { 
  DataBoard, Document, FolderOpened, Check, Close 
} from '@element-plus/icons-vue'
import axios from 'axios'
import AdminFileManager from './AdminFileManager.vue'
import AdminDataManager from './AdminDataManager.vue'

export default {
  name: 'AdminDashboard',
  components: {
    AdminFileManager,
    AdminDataManager,
    DataBoard,
    Document,
    FolderOpened,
    Check,
    Close
  },
  setup() {
    const router = useRouter()
    const activeMenu = ref('dashboard')
    const statsLoading = ref(false)
    const subpopStatsLoading = ref(false)

    const userInfo = reactive({
      username: 'root'
    })

    const statistics = reactive({
      total_files: 0,
      total_size_mb: 0,
      existing_files: 0,
      missing_files: 0,
      category_stats: {},
      organism_stats: {}
    })

    const subpopulationStats = ref([])
    
    // 检查登录状态
    const checkAuth = async () => {
      try {
        const response = await axios.get('/admin/session/')
        if (!response.data.authenticated || !response.data.user?.is_staff) {
          router.push('/admin/login')
          return false
        }
        userInfo.username = response.data.user.username
      } catch (error) {
        router.push('/admin/login')
        return false
      }
      
      return true
    }
    
    // 加载统计信息
    const loadStatistics = async () => {
      try {
        statsLoading.value = true
        const response = await axios.get('/admin/statistics/')

        if (response.data.success) {
          Object.assign(statistics, response.data.data)
        }
      } catch (error) {
        console.error('加载统计信息失败:', error)
        ElMessage.error('加载统计信息失败')
      } finally {
        statsLoading.value = false
      }
    }

    // 加载亚群统计信息
    const loadSubpopulationStats = async () => {
      try {
        subpopStatsLoading.value = true
        const response = await axios.get('/admin/subpopulation-stats/')

        if (response.data.success) {
          subpopulationStats.value = response.data.data
        }
      } catch (error) {
        console.error('加载亚群统计失败:', error)
        ElMessage.error('加载亚群统计失败')
      } finally {
        subpopStatsLoading.value = false
      }
    }

    // 获取亚群样式类名
    const getSubPopulationClass = (subPopulation) => {
      const classMap = {
        'cA': 'sub-pop-ca',
        'cB': 'sub-pop-cb',
        'GJ': 'sub-pop-gj',
        'XI': 'sub-pop-xi',
        'WILD': 'sub-pop-wild',
        'O.glaberrima': 'sub-pop-glaberrima',
        '-': 'sub-pop-unknown'
      }
      return classMap[subPopulation] || 'sub-pop-default'
    }

    // 格式化文件大小
    const formatFileSize = (bytes) => {
      if (!bytes || bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
    
    // 菜单选择
    const handleMenuSelect = (index) => {
      activeMenu.value = index
    }
    
    // 退出登录
    const handleLogout = async () => {
      try {
        await axios.post('/admin/logout/')
      } catch (error) {
        console.error('退出管理员会话失败:', error)
      } finally {
        ElMessage.success('已退出登录')
        router.push('/admin/login')
      }
    }
    
    // 格式化Accession数量显示
    const formatAccessionCount = (count) => {
      return (count !== null && count !== undefined) ? count : '-'
    }

    onMounted(async () => {
      if (await checkAuth()) {
        loadStatistics()
        loadSubpopulationStats()
      }
    })

    return {
      activeMenu,
      userInfo,
      statistics,
      statsLoading,
      subpopulationStats,
      subpopStatsLoading,
      handleMenuSelect,
      handleLogout,
      loadStatistics,
      loadSubpopulationStats,
      getSubPopulationClass,
      formatFileSize,
      formatAccessionCount
    }
  }
}
</script>

<style scoped>
.admin-dashboard {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.admin-header {
  height: 60px;
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header-left h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.user-info {
  font-size: 14px;
}

.admin-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.admin-sidebar {
  width: 200px;
  background: #001529;
  border-right: 1px solid #e6e6e6;
}

.sidebar-menu {
  border: none;
  background: transparent;
}

/* 菜单项样式 */
.sidebar-menu .el-menu-item {
  color: rgba(255, 255, 255, 0.65) !important;
  background-color: transparent !important;
}

.sidebar-menu .el-menu-item:hover {
  color: #fff !important;
  background-color: #1890ff !important;
}

.sidebar-menu .el-menu-item.is-active {
  color: #fff !important;
  background-color: #1890ff !important;
}

.admin-main {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.dashboard-content h2 {
  margin-top: 0;
  margin-bottom: 20px;
  color: #333;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  background: #409eff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
}

.stat-number {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 5px;
}

.subpopulation-stats, .category-stats {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-bottom: 20px;
}

.subpopulation-stats h3, .category-stats h3 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
}

.stats-table {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.stats-header {
  display: flex;
  background: #f5f5f5;
  font-weight: bold;
  color: #333;
  border-bottom: 1px solid #e0e0e0;
}

.stats-row {
  display: flex;
  border-bottom: 1px solid #f0f0f0;
}

.stats-row:last-child {
  border-bottom: none;
}

.stats-row:hover {
  background: #f9f9f9;
}

/* 亚群统计的列宽 */
.subpopulation-stats .stats-header,
.subpopulation-stats .stats-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 0;
}

.subpopulation-stats .stats-col-1,
.subpopulation-stats .stats-col-2,
.subpopulation-stats .stats-col-3,
.subpopulation-stats .stats-col-4 {
  padding: 12px 15px;
  text-align: left;
  font-weight: 500;
}

.subpopulation-stats .stats-col-1 {
  color: #333;
}

.subpopulation-stats .stats-col-2,
.subpopulation-stats .stats-col-3 {
  color: #409eff;
}

.subpopulation-stats .stats-col-4 {
  color: #67c23a;
}

/* 类别统计的列宽 */
.category-stats .stats-header,
.category-stats .stats-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 0;
}

.category-stats .stats-col-1,
.category-stats .stats-col-2,
.category-stats .stats-col-3,
.category-stats .stats-col-4 {
  padding: 12px 15px;
  text-align: left;
  font-weight: 500;
}

.category-stats .stats-col-1 {
  color: #333;
}

.category-stats .stats-col-2,
.category-stats .stats-col-3 {
  color: #409eff;
}

.category-stats .stats-col-4 {
  color: #67c23a;
}
</style>

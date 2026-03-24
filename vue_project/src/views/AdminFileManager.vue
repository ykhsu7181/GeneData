<template>
  <div class="file-manager">
    <div class="page-header">
      <h2>文件管理</h2>
    </div>
    
    <!-- 操作工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchText"
          placeholder="搜索文件名"
          style="width: 200px; margin-right: 10px;"
          clearable
          @input="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-select
          v-model="filterCategory"
          placeholder="选择类别"
          style="width: 150px; margin-right: 10px;"
          clearable
          @change="loadFiles"
        >
          <el-option label="全部类别" value="" />
          <el-option
            v-for="category in categories"
            :key="category.value"
            :label="category.label"
            :value="category.value"
          />
        </el-select>

        <el-select
          v-model="filterOrganism"
          placeholder="选择生物体"
          style="width: 150px;"
          clearable
          @change="loadFiles"
        >
          <el-option label="全部生物体" value="" />
          <el-option
            v-for="organism in organisms"
            :key="organism"
            :label="organism"
            :value="organism"
          />
        </el-select>
      </div>

      <div class="toolbar-right">
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传文件
        </el-button>
        <el-button type="success" @click="showFolderUploadDialog = true">
          <el-icon><FolderOpened /></el-icon>
          上传文件夹
        </el-button>
        <el-button
          type="danger"
          :disabled="!selectedFiles || selectedFiles.length === 0"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedFiles ? selectedFiles.length : 0 }})
        </el-button>
        <el-button
          type="primary"
          :disabled="!selectedFiles || selectedFiles.length === 0"
          @click="handleBatchDownload"
        >
          <el-icon><Download /></el-icon>
          批量下载 ({{ selectedFiles ? selectedFiles.length : 0 }})
        </el-button>
        <el-button type="success" @click="handleRescan">
          <el-icon><Refresh /></el-icon>
          重新扫描
        </el-button>
      </div>
    </div>
    
    <!-- 文件列表表格 -->
    <div class="file-table">
      <el-table
        ref="fileTableRef"
        :data="files"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        stripe
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="name" label="文件名" min-width="200">
          <template #default="scope">
            <div class="file-name">
              <el-icon v-if="!scope.row.exists" class="missing-icon"><Warning /></el-icon>
              {{ scope.row.name }}
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="organism" label="生物体" width="120" />
        
        <el-table-column prop="category" label="类别" width="150">
          <template #default="scope">
            <el-tag size="small">{{ getCategoryLabel(scope.row.category) }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="file_type" label="文件类型" width="100" />
        
        <el-table-column prop="size" label="文件大小" width="120">
          <template #default="scope">
            {{ formatFileSize(scope.row.size) }}
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="创建时间" width="160" />
        
        <el-table-column label="状态" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.exists ? 'success' : 'danger'" size="small">
              {{ scope.row.exists ? '正常' : '缺失' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="scope">
            <el-button 
              type="primary" 
              size="small" 
              :disabled="!scope.row.exists"
              @click="handleDownload(scope.row)"
            >
              下载
            </el-button>
            <el-button 
              type="danger" 
              size="small"
              @click="handleDelete(scope.row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadFiles"
          @current-change="loadFiles"
        />
      </div>
    </div>
    
    <!-- 上传文件对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传文件"
      width="500px"
      @close="resetUpload"
    >
      <el-upload
        ref="uploadRef"
        :action="uploadUrl"
        :auto-upload="false"
        :on-change="handleFileChange"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :file-list="fileList"
        drag
        multiple
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持多文件上传，系统会自动识别文件类型和分类
          </div>
        </template>
      </el-upload>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showUploadDialog = false">取消</el-button>
          <el-button
            type="primary"
            :loading="uploading"
            @click="handleUpload"
          >
            {{ uploading ? '上传中...' : '开始上传' }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 上传文件夹对话框 -->
    <el-dialog
      v-model="showFolderUploadDialog"
      title="上传文件夹"
      width="500px"
      @close="resetFolderUpload"
    >
      <div class="folder-upload-area">
        <input
          ref="folderInputRef"
          type="file"
          webkitdirectory
          multiple
          style="display: none"
          @change="handleFolderSelect"
        />
        <div
          class="folder-drop-zone"
          @click="selectFolder"
        >
          <el-icon class="folder-icon"><FolderOpened /></el-icon>
          <div class="folder-upload-text">
            点击选择文件夹
          </div>
          <div class="folder-upload-tip">
            将上传文件夹中的所有文件
          </div>
        </div>

        <div v-if="folderFiles.length > 0" class="folder-files-preview">
          <h4>将要上传的文件 ({{ folderFiles.length }} 个):</h4>
          <div class="files-list">
            <div
              v-for="file in folderFiles.slice(0, 10)"
              :key="file.name"
              class="file-item"
            >
              {{ file.webkitRelativePath || file.name }}
            </div>
            <div v-if="folderFiles.length > 10" class="more-files">
              ... 还有 {{ folderFiles.length - 10 }} 个文件
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showFolderUploadDialog = false">取消</el-button>
          <el-button
            type="primary"
            :loading="uploading"
            :disabled="folderFiles.length === 0"
            @click="handleFolderUpload"
          >
            {{ uploading ? '上传中...' : `开始上传 (${folderFiles.length} 个文件)` }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, Delete, Download, Refresh, Search, Warning, UploadFilled, FolderOpened
} from '@element-plus/icons-vue'
import axios from 'axios'

export default {
  name: 'AdminFileManager',
  components: {
    Upload,
    Delete,
    Download,
    Refresh,
    Search,
    Warning,
    UploadFilled,
    FolderOpened
  },
  emits: ['refresh-stats'],
  setup(props, { emit }) {
    const loading = ref(false)
    const uploading = ref(false)
    const showUploadDialog = ref(false)
    const showFolderUploadDialog = ref(false)
    const uploadRef = ref(null)
    const folderInputRef = ref(null)
    const fileTableRef = ref(null)
    const fileList = ref([])
    const folderFiles = ref([])

    const files = ref([])
    const selectedFiles = ref([])
    const currentPage = ref(1)
    const pageSize = ref(20)
    const total = ref(0)
    
    const searchText = ref('')
    const filterCategory = ref('')
    const filterOrganism = ref('')
    
    const organisms = ref([])
    
    // 文件类别选项
    const categories = [
      { value: 'genome', label: '基因组序列' },
      { value: 'transcriptome.all', label: '转录组-All' },
      { value: 'transcriptome.root', label: '转录组-Root' },
      { value: 'transcriptome.stem', label: '转录组-Stem' },
      { value: 'transcriptome.leaf', label: '转录组-Leaf' },
      { value: 'transcriptome.panicles', label: '转录组-Panicles' },
      { value: 'transcriptome.shoot', label: '转录组-Shoot' },
      { value: 'miRNA', label: '微RNA' },
      { value: 'tRNA', label: '转运RNA' },
      { value: 'rRNA', label: '核糖体RNA' },
      { value: 'codon', label: '密码子' },
      { value: 'centromere', label: '着丝粒' },
      { value: 'TEs', label: '转座子' },
      { value: 'annotation', label: '基因注释' },
      { value: 'coreBlocks', label: '核心区块' },
      { value: 'other', label: '其他' }
    ]
    
    const uploadUrl = computed(() => {
      return '/admin/files/upload/'
    })
    
    // 获取类别标签
    const getCategoryLabel = (value) => {
      const category = categories.find(c => c.value === value)
      return category ? category.label : value
    }
    
    // 格式化文件大小
    const formatFileSize = (bytes) => {
      if (!bytes) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
    
    // 加载所有生物体列表
    const loadOrganisms = async () => {
      try {
        // 获取所有文件的生物体列表（不带过滤条件）
        const response = await axios.get('/admin/files/', {
          params: { page: 1, page_size: 1000 } // 获取足够多的数据来提取生物体
        })

        if (response.data.success) {
          const uniqueOrganisms = [...new Set(response.data.data.map(f => f.organism))]
          organisms.value = uniqueOrganisms.filter(o => o && o !== 'unknown')
        }
      } catch (error) {
        console.error('加载生物体列表失败:', error)
      }
    }

    // 加载文件列表
    const loadFiles = async () => {
      try {
        loading.value = true
        const params = {
          page: currentPage.value,
          page_size: pageSize.value,
          search: searchText.value,
          category: filterCategory.value,
          organism: filterOrganism.value
        }

        const response = await axios.get('/admin/files/', { params })

        if (response.data.success) {
          files.value = response.data.data
          total.value = response.data.total
        }
      } catch (error) {
        console.error('加载文件列表失败:', error)
        ElMessage.error('加载文件列表失败')
      } finally {
        loading.value = false
      }
    }

    // 搜索处理
    const handleSearch = () => {
      currentPage.value = 1
      loadFiles()
    }

    // 选择变化处理
    const handleSelectionChange = (selection) => {
      selectedFiles.value = selection || []
    }

    // 下载文件
    const handleDownload = (file) => {
      const downloadUrl = `/gd/api/manual_download/${file.name}`
      window.open(downloadUrl, '_blank')
    }

    // 删除单个文件
    const handleDelete = async (file) => {
      try {
        await ElMessageBox.confirm(
          `确定要删除文件 "${file.name}" 吗？此操作不可恢复。`,
          '确认删除',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )

        const response = await axios.delete(`/admin/files/${file.id}/delete/`)

        if (response.data.success) {
          ElMessage.success(response.data.message)
          loadFiles()
          emit('refresh-stats')
        } else {
          ElMessage.error(response.data.message)
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除文件失败:', error)
          ElMessage.error('删除文件失败')
        }
      }
    }

    // 批量删除
    const handleBatchDelete = async () => {
      if (!selectedFiles.value || selectedFiles.value.length === 0) {
        ElMessage.warning('请选择要删除的文件')
        return
      }

      try {
        await ElMessageBox.confirm(
          `确定要删除选中的 ${selectedFiles.value.length} 个文件吗？此操作不可恢复。`,
          '确认批量删除',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )

        const fileIds = selectedFiles.value.map(f => f.id)
        const response = await axios.post('/admin/files/batch-delete/', {
          file_ids: fileIds
        })

        if (response.data.success) {
          ElMessage.success(response.data.message)
          selectedFiles.value = []
          // 清除表格选择状态
          if (fileTableRef.value) {
            fileTableRef.value.clearSelection()
          }
          loadFiles()
          emit('refresh-stats')
        } else {
          ElMessage.error(response.data.message)
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('批量删除失败:', error)
          ElMessage.error('批量删除失败')
        }
      }
    }

    // 批量下载
    const handleBatchDownload = async () => {
      if (!selectedFiles.value || selectedFiles.value.length === 0) {
        ElMessage.warning('请选择要下载的文件')
        return
      }

      try {
        const fileIds = selectedFiles.value.map(f => f.id)
        const response = await axios.post('/admin/files/batch-download/', {
          file_ids: fileIds
        }, {
          responseType: 'blob'
        })

        // 创建下载链接
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url

        // 从响应头获取文件名，如果没有则使用默认名称
        const contentDisposition = response.headers['content-disposition']
        let filename = 'batch_download.zip'
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename="(.+)"/)
          if (filenameMatch) {
            filename = filenameMatch[1]
          }
        }

        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)

        ElMessage.success(`成功下载 ${selectedFiles.value.length} 个文件`)
        selectedFiles.value = []
        // 清除表格选择状态
        if (fileTableRef.value) {
          fileTableRef.value.clearSelection()
        }

      } catch (error) {
        console.error('批量下载失败:', error)
        ElMessage.error('批量下载失败')
      }
    }

    // 重新扫描
    const handleRescan = async () => {
      try {
        loading.value = true
        const response = await axios.post('/admin/rescan/')

        if (response.data.success) {
          ElMessage.success(response.data.message)
          loadFiles()
          emit('refresh-stats')
        } else {
          ElMessage.error(response.data.message)
        }
      } catch (error) {
        console.error('重新扫描失败:', error)
        ElMessage.error('重新扫描失败')
      } finally {
        loading.value = false
      }
    }

    // 文件变化处理
    const handleFileChange = (file, uploadFileList) => {
      fileList.value = uploadFileList
      console.log('文件列表更新:', fileList.value)
    }

    // 获取CSRF token
    const getCsrfToken = () => {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')
      return csrfToken ? csrfToken.value : ''
    }

    // 上传处理
    const handleUpload = async () => {
      console.log('开始上传，文件列表:', fileList.value)

      if (!fileList.value || fileList.value.length === 0) {
        ElMessage.warning('请选择要上传的文件')
        return
      }

      try {
        uploading.value = true

        // 逐个上传文件
        for (const file of fileList.value) {
          const formData = new FormData()
          formData.append('file', file.raw)

          const headers = {
            'Content-Type': 'multipart/form-data'
          }

          // 添加CSRF token（如果存在）
          const csrfToken = getCsrfToken()
          if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken
          }

          console.log('上传文件:', file.name)
          await axios.post('/admin/files/upload/', formData, { headers })
        }

        ElMessage.success('所有文件上传成功')
        showUploadDialog.value = false
        resetUpload()
        loadFiles()
        emit('refresh-stats')

      } catch (error) {
        console.error('上传失败:', error)
        if (error.response && error.response.data && error.response.data.message) {
          ElMessage.error(error.response.data.message)
        } else {
          ElMessage.error('上传失败，请检查网络连接')
        }
      } finally {
        uploading.value = false
      }
    }

    // 上传成功处理
    const handleUploadSuccess = (response, file) => {
      ElMessage.success(`文件 ${file.name} 上传成功`)
    }

    // 上传失败处理
    const handleUploadError = (error, file) => {
      ElMessage.error(`文件 ${file.name} 上传失败`)
    }

    // 选择文件夹
    const selectFolder = () => {
      if (folderInputRef.value) {
        folderInputRef.value.click()
      }
    }

    // 处理文件夹选择
    const handleFolderSelect = (event) => {
      const files = Array.from(event.target.files)
      folderFiles.value = files
      console.log('选择的文件夹文件:', files)
    }

    // 文件夹上传处理
    const handleFolderUpload = async () => {
      if (folderFiles.value.length === 0) {
        ElMessage.warning('请选择要上传的文件夹')
        return
      }

      try {
        uploading.value = true
        let successCount = 0
        let failCount = 0

        // 逐个上传文件
        for (const file of folderFiles.value) {
          try {
            const formData = new FormData()
            formData.append('file', file)

            const headers = {
              'Content-Type': 'multipart/form-data'
            }

            // 添加CSRF token（如果存在）
            const csrfToken = getCsrfToken()
            if (csrfToken) {
              headers['X-CSRFToken'] = csrfToken
            }

            console.log('上传文件:', file.name)
            await axios.post('/admin/files/upload/', formData, { headers })
            successCount++
          } catch (error) {
            console.error(`文件 ${file.name} 上传失败:`, error)
            failCount++
          }
        }

        if (successCount > 0) {
          ElMessage.success(`成功上传 ${successCount} 个文件${failCount > 0 ? `，${failCount} 个文件失败` : ''}`)
          showFolderUploadDialog.value = false
          resetFolderUpload()
          loadFiles()
          emit('refresh-stats')
        } else {
          ElMessage.error('所有文件上传失败')
        }

      } catch (error) {
        console.error('文件夹上传失败:', error)
        ElMessage.error('文件夹上传失败')
      } finally {
        uploading.value = false
      }
    }

    // 重置文件夹上传
    const resetFolderUpload = () => {
      folderFiles.value = []
      if (folderInputRef.value) {
        folderInputRef.value.value = ''
      }
    }

    // 重置上传
    const resetUpload = () => {
      fileList.value = []
      if (uploadRef.value) {
        uploadRef.value.clearFiles()
      }
    }

    onMounted(() => {
      loadFiles()
      loadOrganisms()
    })

    return {
      loading,
      uploading,
      showUploadDialog,
      showFolderUploadDialog,
      uploadRef,
      folderInputRef,
      fileTableRef,
      fileList,
      folderFiles,
      files,
      selectedFiles,
      currentPage,
      pageSize,
      total,
      searchText,
      filterCategory,
      filterOrganism,
      organisms,
      categories,
      uploadUrl,
      getCategoryLabel,
      formatFileSize,
      loadFiles,
      loadOrganisms,
      handleSearch,
      handleSelectionChange,
      handleDownload,
      handleDelete,
      handleBatchDelete,
      handleBatchDownload,
      handleRescan,
      handleFileChange,
      handleUpload,
      handleUploadSuccess,
      handleUploadError,
      selectFolder,
      handleFolderSelect,
      handleFolderUpload,
      resetUpload,
      resetFolderUpload
    }
  }
}
</script>

<style scoped>
.file-manager h2 {
  margin-top: 0;
  margin-bottom: 20px;
  color: #333;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.toolbar-left {
  display: flex;
  gap: 10px;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.file-table {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  overflow: hidden;
}

.file-name {
  display: flex;
  align-items: center;
  gap: 5px;
}

.missing-icon {
  color: #f56c6c;
}

.pagination {
  padding: 20px;
  text-align: right;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 文件夹上传样式 */
.folder-upload-area {
  padding: 20px 0;
}

.folder-drop-zone {
  border: 2px dashed #d9d9d9;
  border-radius: 6px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.3s;
}

.folder-drop-zone:hover {
  border-color: #409eff;
}

.folder-icon {
  font-size: 48px;
  color: #c0c4cc;
  margin-bottom: 16px;
}

.folder-upload-text {
  font-size: 16px;
  color: #606266;
  margin-bottom: 8px;
}

.folder-upload-tip {
  font-size: 14px;
  color: #909399;
}

.folder-files-preview {
  margin-top: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.folder-files-preview h4 {
  margin: 0 0 12px 0;
  color: #303133;
  font-size: 14px;
}

.files-list {
  max-height: 200px;
  overflow-y: auto;
}

.file-item {
  padding: 4px 0;
  font-size: 13px;
  color: #606266;
  border-bottom: 1px solid #ebeef5;
}

.file-item:last-child {
  border-bottom: none;
}

.more-files {
  padding: 8px 0;
  font-size: 13px;
  color: #909399;
  font-style: italic;
}

/* 页面标题样式 */
.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 10px 0;
  color: #1a56db;
  font-size: 24px;
  font-weight: 600;
}
</style>

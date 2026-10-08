<template>
  <div class="file-manager">
    <div class="page-header">
      <h2>{{ $t('page.admin.fileManagement') }}</h2>
    </div>
    
    <!-- 操作工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchText"
          :placeholder="$t('page.admin.searchFileName')"
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
          :placeholder="$t('page.admin.selectCategory')"
          style="width: 150px; margin-right: 10px;"
          clearable
          @change="loadFiles"
        >
          <el-option :label="$t('page.admin.allCategories')" value="" />
          <el-option
            v-for="category in categories"
            :key="category.value"
            :label="category.label"
            :value="category.value"
          />
        </el-select>

        <el-select
          v-model="filterOrganism"
          :placeholder="$t('page.admin.selectOrganism')"
          style="width: 150px;"
          clearable
          @change="loadFiles"
        >
          <el-option :label="$t('page.admin.allOrganisms')" value="" />
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
          {{ $t('page.admin.uploadFile') }}
        </el-button>
        <el-button type="success" @click="showFolderUploadDialog = true">
          <el-icon><FolderOpened /></el-icon>
          {{ $t('page.admin.uploadFolder') }}
        </el-button>
        <el-button
          type="danger"
          :disabled="!selectedFiles || selectedFiles.length === 0"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          {{ $t('page.admin.batchDelete', { count: selectedFiles ? selectedFiles.length : 0 }) }}
        </el-button>
        <el-button
          type="primary"
          :disabled="!selectedFiles || selectedFiles.length === 0"
          @click="handleBatchDownload"
        >
          <el-icon><Download /></el-icon>
          {{ $t('page.admin.batchDownload', { count: selectedFiles ? selectedFiles.length : 0 }) }}
        </el-button>
        <el-button type="success" @click="handleRescan">
          <el-icon><Refresh /></el-icon>
          {{ $t('page.admin.rescan') }}
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
        
        <el-table-column prop="name" :label="$t('common.fileName')" min-width="200">
          <template #default="scope">
            <div class="file-name">
              <el-icon v-if="!scope.row.exists" class="missing-icon"><Warning /></el-icon>
              {{ scope.row.name }}
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="organism" :label="$t('page.admin.organism')" width="120" />
        
        <el-table-column prop="category" :label="$t('page.admin.category')" width="150">
          <template #default="scope">
            <el-tag size="small">{{ getCategoryLabel(scope.row.category) }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="file_type" :label="$t('common.fileType')" width="100" />
        
        <el-table-column prop="size" :label="$t('common.fileSize')" width="120">
          <template #default="scope">
            {{ formatFileSize(scope.row.size) }}
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" :label="$t('page.admin.createdAt')" width="160" />
        
        <el-table-column :label="$t('page.rawData.columns.status')" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.exists ? 'success' : 'danger'" size="small">
              {{ scope.row.exists ? $t('page.admin.normal') : $t('page.admin.missing') }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column :label="$t('common.actions')" width="150" fixed="right">
          <template #default="scope">
            <el-button 
              type="primary" 
              size="small" 
              :disabled="!scope.row.exists"
              @click="handleDownload(scope.row)"
            >
              {{ $t('common.download') }}
            </el-button>
            <el-button 
              type="danger" 
              size="small"
              @click="handleDelete(scope.row)"
            >
              {{ $t('common.delete') }}
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
      :title="$t('page.admin.uploadFile')"
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
          {{ $t('page.admin.dragFiles') }}<em>{{ $t('page.admin.clickUpload') }}</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            {{ $t('page.admin.uploadTip') }}
          </div>
        </template>
      </el-upload>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showUploadDialog = false">{{ $t('common.cancel') }}</el-button>
          <el-button
            type="primary"
            :loading="uploading"
            @click="handleUpload"
          >
            {{ uploading ? $t('page.admin.uploading') : $t('page.admin.startUpload') }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 上传文件夹对话框 -->
    <el-dialog
      v-model="showFolderUploadDialog"
      :title="$t('page.admin.uploadFolder')"
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
            {{ $t('page.admin.selectFolder') }}
          </div>
          <div class="folder-upload-tip">
            {{ $t('page.admin.folderTip') }}
          </div>
        </div>

        <div v-if="folderFiles.length > 0" class="folder-files-preview">
          <h4>{{ $t('page.admin.pendingFiles', { count: folderFiles.length }) }}</h4>
          <div class="files-list">
            <div
              v-for="file in folderFiles.slice(0, 10)"
              :key="file.name"
              class="file-item"
            >
              {{ file.webkitRelativePath || file.name }}
            </div>
            <div v-if="folderFiles.length > 10" class="more-files">
              ... {{ $t('page.admin.moreFiles', { count: folderFiles.length - 10 }) }}
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showFolderUploadDialog = false">{{ $t('common.cancel') }}</el-button>
          <el-button
            type="primary"
            :loading="uploading"
            :disabled="folderFiles.length === 0"
            @click="handleFolderUpload"
          >
            {{ uploading ? $t('page.admin.uploading') : $t('page.admin.startFolderUpload', { count: folderFiles.length }) }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, Delete, Download, Refresh, Search, Warning, UploadFilled, FolderOpened
} from '@element-plus/icons-vue'
import axios from 'axios'
import { useI18n } from 'vue-i18n'

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
    const { t } = useI18n()
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
    const categories = computed(() => [
      { value: 'genome', label: t('nav.genome') },
      { value: 'transcriptome.all', label: `${t('nav.transcriptome')}-All` },
      { value: 'transcriptome.root', label: `${t('nav.transcriptome')}-Root` },
      { value: 'transcriptome.stem', label: `${t('nav.transcriptome')}-Stem` },
      { value: 'transcriptome.leaf', label: `${t('nav.transcriptome')}-Leaf` },
      { value: 'transcriptome.panicles', label: `${t('nav.transcriptome')}-Panicles` },
      { value: 'transcriptome.shoot', label: `${t('nav.transcriptome')}-Shoot` },
      { value: 'miRNA', label: 'miRNA' },
      { value: 'tRNA', label: 'tRNA' },
      { value: 'rRNA', label: 'rRNA' },
      { value: 'codon', label: t('nav.codon') },
      { value: 'centromere', label: 'Centromere' },
      { value: 'TEs', label: 'TEs' },
      { value: 'annotation', label: t('nav.annotation') },
      { value: 'coreBlocks', label: t('nav.coreVariableBlocks') },
      { value: 'other', label: t('page.admin.otherFiles') }
    ])
    
    const uploadUrl = computed(() => {
      return '/admin/files/upload/'
    })
    
    // 获取类别标签
    const getCategoryLabel = (value) => {
      const category = categories.value.find(c => c.value === value)
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
        ElMessage.error(t('page.admin.fileListLoadFailed'))
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
          t('page.admin.deleteFileConfirm', { name: file.name }),
          t('page.admin.deleteConfirmTitle'),
          {
            confirmButtonText: t('common.confirm'),
            cancelButtonText: t('common.cancel'),
            type: 'warning'
          }
        )

        const response = await axios.delete(`/admin/files/${file.id}/delete/`)

        if (response.data.success) {
          ElMessage.success(t('page.admin.deleteSuccess'))
          loadFiles()
          emit('refresh-stats')
        } else {
          ElMessage.error(t('page.admin.deleteFileFailed'))
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除文件失败:', error)
          ElMessage.error(t('page.admin.deleteFileFailed'))
        }
      }
    }

    // 批量删除
    const handleBatchDelete = async () => {
      if (!selectedFiles.value || selectedFiles.value.length === 0) {
        ElMessage.warning(t('page.admin.selectFilesToDelete'))
        return
      }

      try {
        await ElMessageBox.confirm(
          t('page.admin.batchDeleteConfirm', { count: selectedFiles.value.length }),
          t('page.admin.batchDeleteTitle'),
          {
            confirmButtonText: t('common.confirm'),
            cancelButtonText: t('common.cancel'),
            type: 'warning'
          }
        )

        const fileIds = selectedFiles.value.map(f => f.id)
        const response = await axios.post('/admin/files/batch-delete/', {
          file_ids: fileIds
        })

        if (response.data.success) {
          ElMessage.success(t('page.admin.deleteSuccess'))
          selectedFiles.value = []
          // 清除表格选择状态
          if (fileTableRef.value) {
            fileTableRef.value.clearSelection()
          }
          loadFiles()
          emit('refresh-stats')
        } else {
          ElMessage.error(t('page.admin.batchDeleteFailed'))
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('批量删除失败:', error)
          ElMessage.error(t('page.admin.batchDeleteFailed'))
        }
      }
    }

    // 批量下载
    const handleBatchDownload = async () => {
      if (!selectedFiles.value || selectedFiles.value.length === 0) {
        ElMessage.warning(t('page.admin.selectFilesToDownload'))
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

        ElMessage.success(t('page.admin.batchDownloaded', { count: selectedFiles.value.length }))
        selectedFiles.value = []
        // 清除表格选择状态
        if (fileTableRef.value) {
          fileTableRef.value.clearSelection()
        }

      } catch (error) {
        console.error('批量下载失败:', error)
        ElMessage.error(t('page.admin.batchDownloadFailed'))
      }
    }

    // 重新扫描
    const handleRescan = async () => {
      try {
        loading.value = true
        const response = await axios.post('/admin/rescan/')

        if (response.data.success) {
          ElMessage.success(t('messages.dataRefreshed'))
          loadFiles()
          emit('refresh-stats')
        } else {
          ElMessage.error(t('page.admin.rescanFailed'))
        }
      } catch (error) {
        console.error('重新扫描失败:', error)
        ElMessage.error(t('page.admin.rescanFailed'))
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
        ElMessage.warning(t('page.admin.selectFilesToUpload'))
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

        ElMessage.success(t('page.admin.allFilesUploaded'))
        showUploadDialog.value = false
        resetUpload()
        loadFiles()
        emit('refresh-stats')

      } catch (error) {
        console.error('上传失败:', error)
        if (error.response && error.response.data && error.response.data.message) {
          ElMessage.error(t('page.admin.uploadNetworkFailed'))
        } else {
          ElMessage.error(t('page.admin.uploadNetworkFailed'))
        }
      } finally {
        uploading.value = false
      }
    }

    // 上传成功处理
    const handleUploadSuccess = (response, file) => {
      ElMessage.success(t('page.admin.fileUploadSuccess', { name: file.name }))
    }

    // 上传失败处理
    const handleUploadError = (error, file) => {
      ElMessage.error(t('page.admin.fileUploadFailed', { name: file.name }))
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
        ElMessage.warning(t('page.admin.selectFolderWarning'))
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
          ElMessage.success(t('page.admin.folderUploadResult', { success: successCount, failed: failCount }))
          showFolderUploadDialog.value = false
          resetFolderUpload()
          loadFiles()
          emit('refresh-stats')
        } else {
          ElMessage.error(t('page.admin.allUploadsFailed'))
        }

      } catch (error) {
        console.error('文件夹上传失败:', error)
        ElMessage.error(t('page.admin.folderUploadFailed'))
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

<template>
  <el-drawer :model-value="modelValue" :title="$t('page.dataOverview.detail.title')" size="min(560px, 92vw)" @close="$emit('close')">
    <div v-loading="loading" class="detail-content" :aria-busy="loading">
      <el-result v-if="error && !loading" icon="error" :title="$t('page.dataOverview.detail.loadFailed')">
        <template #extra><el-button type="primary" @click="$emit('retry')">{{ $t('common.retry') }}</el-button></template>
      </el-result>
      <template v-else-if="detail">
        <section class="detail-section">
          <h3>{{ $t('page.dataOverview.detail.basic') }}</h3>
          <dl class="detail-grid">
            <div><dt>{{ $t('common.fileName') }}</dt><dd>{{ detail.file_name || '-' }}</dd></div>
            <div><dt>{{ $t('page.dataOverview.columns.originalName') }}</dt><dd>{{ detail.original_name || '-' }}</dd></div>
            <div><dt>{{ $t('page.dataOverview.columns.fileCode') }}</dt><dd>{{ detail.file_code || '-' }}</dd></div>
            <div><dt>{{ $t('common.dataType') }}</dt><dd>{{ categoryLabel(detail.category) }}</dd></div>
            <div><dt>{{ $t('common.fileType') }}</dt><dd>{{ detail.file_type || '-' }}</dd></div>
            <div><dt>{{ $t('common.fileSize') }}</dt><dd>{{ detail.file_size_display || '-' }}</dd></div>
            <div class="wide"><dt>{{ $t('page.dataOverview.columns.description') }}</dt><dd>{{ detail.description || '-' }}</dd></div>
          </dl>
        </section>
        <section class="detail-section">
          <h3>{{ $t('page.dataOverview.detail.relationship') }}</h3>
          <dl class="detail-grid">
            <div><dt>{{ $t('common.species') }}</dt><dd>{{ join(detail.species) }}</dd></div>
            <div><dt>{{ $t('page.dataOverview.accession') }}</dt><dd>{{ join(detail.accessions) }}</dd></div>
            <div><dt>{{ $t('page.dataOverview.columns.dataset') }}</dt><dd>{{ detail.dataset?.dataset_name || detail.dataset?.dataset_code || '-' }}</dd></div>
            <div><dt>{{ $t('page.dataOverview.columns.dataSource') }}</dt><dd>{{ detail.data_source || '-' }}</dd></div>
          </dl>
          <div class="relation-list">
            <div v-for="(relation, index) in detail.relations" :key="`${relation.related_type}-${index}`" class="relation-row">
              <span>{{ relation.related_type }}</span><strong>{{ relation.related_code || '-' }}</strong><span>{{ relation.file_role_display || relation.file_role }}</span><el-tag v-if="relation.is_primary" size="small">{{ $t('page.dataOverview.detail.primary') }}</el-tag>
            </div>
          </div>
        </section>
        <section class="detail-section">
          <h3>{{ $t('page.dataOverview.detail.integrity') }}</h3>
          <dl class="detail-grid">
            <div class="wide"><dt>MD5</dt><dd class="checksum">{{ detail.md5 || '-' }}</dd></div>
            <div><dt>{{ $t('page.dataOverview.detail.createdAt') }}</dt><dd>{{ formatDate(detail.created_at) }}</dd></div>
            <div><dt>{{ $t('page.dataOverview.columns.updatedAt') }}</dt><dd>{{ formatDate(detail.updated_at) }}</dd></div>
          </dl>
        </section>
        <footer class="drawer-actions">
          <el-button :disabled="!detail.md5" @click="copyMd5"><el-icon><CopyDocument /></el-icon>{{ $t('page.dataOverview.detail.copyMd5') }}</el-button>
          <el-button type="primary" tag="a" :href="detail.download_url"><el-icon><Download /></el-icon>{{ $t('common.download') }}</el-button>
        </footer>
      </template>
      <el-empty v-else-if="!loading" :description="$t('page.dataOverview.detail.empty')" />
    </div>
  </el-drawer>
</template>

<script setup>
/* global defineProps, defineEmits */
import { CopyDocument, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
const props = defineProps({ modelValue: Boolean, loading: Boolean, error: Boolean, detail: { type: Object, default: null }, categoryLabel: { type: Function, required: true } })
defineEmits(['close', 'retry'])
const { t } = useI18n()
const join = values => values?.length ? values.join(', ') : '-'
const formatDate = value => value ? String(value).replace('T', ' ').slice(0, 19) : '-'
const copyMd5 = async () => {
  if (!props.detail?.md5) return
  try {
    await navigator.clipboard.writeText(props.detail.md5)
    ElMessage.success(t('page.dataOverview.detail.copySuccess'))
  } catch (_) {
    ElMessage.error(t('page.dataOverview.detail.copyFailed'))
  }
}
</script>

<style scoped>
.detail-content{min-height:240px}.detail-section{margin-bottom:22px}.detail-section h3{margin:0 0 12px;padding-bottom:9px;border-bottom:1px solid #e1eaf5;color:#0966d9;font-size:16px}.detail-grid{display:grid;grid-template-columns:1fr 1fr;margin:0;border:1px solid #e1e9f4;border-radius:10px;overflow:hidden}.detail-grid>div{display:grid;grid-template-columns:105px 1fr;min-height:43px;padding:0 11px;align-items:center;border-right:1px solid #e7edf5;border-bottom:1px solid #e7edf5}.detail-grid .wide{grid-column:1/-1}.detail-grid dt{color:#6b7c95;font-size:12px}.detail-grid dd{min-width:0;margin:0;color:#17375f;overflow-wrap:anywhere}.relation-list{margin-top:10px}.relation-row{display:grid;grid-template-columns:90px minmax(80px,1fr) minmax(120px,1.4fr) auto;gap:8px;align-items:center;padding:9px;border-bottom:1px solid #e7edf5;color:#526985;font-size:12px}.checksum{font-family:monospace}.drawer-actions{display:flex;justify-content:flex-end;gap:8px;padding-top:4px}@media(max-width:600px){.detail-grid{grid-template-columns:1fr}.detail-grid .wide{grid-column:auto}.relation-row{grid-template-columns:1fr 1fr}.drawer-actions{align-items:stretch;flex-direction:column-reverse}.drawer-actions :deep(.el-button){width:100%;margin-left:0}}
</style>

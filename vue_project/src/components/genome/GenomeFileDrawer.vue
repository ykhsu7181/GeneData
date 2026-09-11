<template>
  <el-drawer
    :model-value="modelValue"
    :title="title"
    size="440px"
    class="genome-file-drawer"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-loading="loading">
      <div class="drawer-meta">
        <p>Accession：{{ meta.accession || '-' }}</p>
        <p>Assembly：{{ meta.assembly_name || '-' }}</p>
        <p>下载入口：DataFile download</p>
      </div>
      <el-table :data="files" size="small" empty-text="暂无关联文件">
        <el-table-column prop="file_name" label="文件名" min-width="170" />
        <el-table-column prop="file_role_display" label="文件角色" min-width="130" />
        <el-table-column prop="file_size_display" label="大小" width="90" />
        <el-table-column label="操作" width="78">
          <template #default="{ row }">
            <button type="button" class="drawer-download" @click="$emit('download', row)">下载</button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-drawer>
</template>

<script>
export default {
  name: 'GenomeFileDrawer',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    meta: { type: Object, default: () => ({}) },
    files: { type: Array, default: () => [] }
  },
  emits: ['update:modelValue', 'download']
};
</script>

<style scoped>
.drawer-meta { margin-bottom: 14px; padding: 12px 14px; border-radius: 8px; background: #f2f7ff; color: #536781; font-size: 13px; font-weight: 800; }
.drawer-meta p { margin: 4px 0; }
.drawer-download { border: 0; background: transparent; color: #1768f2; font-weight: 900; cursor: pointer; }
</style>

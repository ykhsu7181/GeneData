<template>
  <el-popover placement="bottom-end" :width="260" trigger="click">
    <template #reference>
      <el-button class="column-button"><el-icon><Setting /></el-icon>{{ $t('page.dataOverview.columnSettings') }}</el-button>
    </template>
    <div class="column-title">{{ $t('page.dataOverview.chooseColumns') }}</div>
    <el-checkbox-group :model-value="modelValue" class="column-options" @change="$emit('update:modelValue', $event)">
      <el-checkbox v-for="column in columns" :key="column.key" :label="column.key" :disabled="column.required">
        {{ column.label }}
      </el-checkbox>
    </el-checkbox-group>
  </el-popover>
</template>

<script setup>
/* global defineProps, defineEmits */
import { Setting } from '@element-plus/icons-vue'
defineProps({ modelValue: { type: Array, required: true }, columns: { type: Array, required: true } })
defineEmits(['update:modelValue'])
</script>

<style scoped>
.column-title{margin-bottom:10px;color:#173b70;font-weight:700}.column-options{display:grid;grid-template-columns:1fr 1fr;gap:4px}.column-button{border-color:#c9dcf5;color:#1558b6;font-weight:700}
</style>

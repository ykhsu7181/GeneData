<template>
  <el-popover placement="bottom-end" :width="260" trigger="click">
    <template #reference>
      <el-button class="column-button" text :aria-label="$t('page.dataOverview.chooseColumns')" aria-haspopup="dialog">
        {{ $t('page.dataOverview.moreColumns') }}
        <el-icon aria-hidden="true"><ArrowDown /></el-icon>
      </el-button>
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
import { ArrowDown } from '@element-plus/icons-vue'
defineProps({ modelValue: { type: Array, required: true }, columns: { type: Array, required: true } })
defineEmits(['update:modelValue'])
</script>

<style scoped>
.column-title{margin-bottom:10px;color:#173b70;font-weight:700}.column-options{display:grid;grid-template-columns:1fr 1fr;gap:4px}.column-button{padding:5px 7px;color:#1760e8;font-weight:700}
</style>

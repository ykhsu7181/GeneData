<template>
  <span class="species-name">
    <template v-if="commonText && commonText !== scientificText">
      <span>{{ commonText }}</span>
      <template v-if="scientificText"> (<em>{{ scientificText }}</em>)</template>
    </template>
    <em v-else-if="scientificText">{{ scientificText }}</em>
    <span v-else>{{ commonText || emptyText }}</span>
  </span>
</template>

<script>
import { computed } from 'vue';

export default {
  name: 'SpeciesName',
  props: {
    commonName: { type: [String, Number], default: '' },
    scientificName: { type: [String, Number], default: '' },
    emptyText: { type: String, default: '-' }
  },
  setup(props) {
    const normalize = value => (
      value === null || value === undefined ? '' : String(value).trim()
    );
    const commonText = computed(() => normalize(props.commonName));
    const scientificText = computed(() => normalize(props.scientificName));
    return { commonText, scientificText };
  }
};
</script>

<style scoped>
.species-name em { font-style:italic; }
</style>

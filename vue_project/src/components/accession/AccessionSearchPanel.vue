<template>
  <section class="search-panel" :aria-labelledby="searchTitleId">
    <h2 :id="searchTitleId">{{ $t('page.accessionPortal.searchTitle') }}</h2>

    <form class="search-form" role="search" @submit.prevent="submitSearch">
      <div class="combobox-shell">
        <el-icon class="search-icon" aria-hidden="true"><Search /></el-icon>
        <input
          ref="searchInput"
          v-model="searchTerm"
          type="search"
          autocomplete="off"
          role="combobox"
          :aria-label="$t('page.accessionPortal.searchTitle')"
          :aria-controls="listboxId"
          :aria-expanded="suggestionsOpen"
          :aria-activedescendant="activeOptionId"
          :placeholder="$t('page.accessionPortal.searchPlaceholder')"
          @input="handleInput"
          @focus="handleFocus"
          @blur="handleBlur"
          @keydown="handleKeydown"
        >
        <span v-if="loading" class="search-status" aria-live="polite">
          {{ $t('page.accessionPortal.searching') }}
        </span>

        <ul
          v-if="suggestionsOpen"
          :id="listboxId"
          class="suggestion-list"
          role="listbox"
        >
          <li
            v-for="(item, index) in options"
            :id="optionId(index)"
            :key="item"
            role="option"
            :aria-selected="index === activeIndex"
            :class="{ active: index === activeIndex }"
            @mousedown.prevent="selectOption(item)"
            @mouseenter="activeIndex = index"
          >
            {{ item }}
          </li>
          <li v-if="!loading && !options.length" class="empty-option" role="status">
            {{ $t('page.accessionPortal.noSearchResults') }}
          </li>
        </ul>
      </div>

      <button class="search-button" type="submit" :disabled="searchTerm.trim().length < 2 || loading">
        {{ $t('common.search') }}
      </button>
    </form>

    <p v-if="searchError" class="search-error" role="alert">
      {{ $t('page.accessionPortal.searchError') }}
    </p>

    <div class="examples">
      <span>{{ $t('page.accessionPortal.examples') }}:</span>
      <button
        v-for="example in examples"
        :key="example.value"
        type="button"
        @click="useExample(example)"
      >
        {{ example.label }}
      </button>
    </div>
  </section>
</template>

<script>
import { computed, onBeforeUnmount, ref } from 'vue';
import { Search } from '@element-plus/icons-vue';
import axios from 'axios';

const DEBOUNCE_MS = 275;
const MIN_SEARCH_LENGTH = 2;

export default {
  name: 'AccessionSearchPanel',
  components: { Search },
  emits: ['select'],
  setup(_, { emit }) {
    const searchTerm = ref('');
    const searchInput = ref(null);
    const options = ref([]);
    const loading = ref(false);
    const searchError = ref(false);
    const suggestionsOpen = ref(false);
    const activeIndex = ref(-1);
    const searchTitleId = 'accession-search-title';
    const listboxId = 'accession-search-options';
    const examples = [
      { label: '02428', value: '02428' },
      { label: 'IR64', value: 'IR64' }
    ];
    let debounceTimer = null;
    let activeController = null;
    let requestSequence = 0;
    let blurTimer = null;

    const activeOptionId = computed(() => (
      activeIndex.value >= 0 ? `${listboxId}-${activeIndex.value}` : undefined
    ));
    const optionId = (index) => `${listboxId}-${index}`;

    const cancelPendingRequest = () => {
      if (activeController) activeController.abort();
      activeController = null;
    };

    const clearSuggestions = () => {
      cancelPendingRequest();
      options.value = [];
      activeIndex.value = -1;
      suggestionsOpen.value = false;
      loading.value = false;
    };

    const fetchSuggestions = async (query) => {
      const keyword = String(query || '').trim();
      if (keyword.length < MIN_SEARCH_LENGTH) {
        clearSuggestions();
        searchError.value = false;
        return [];
      }

      cancelPendingRequest();
      const controller = new AbortController();
      activeController = controller;
      const sequence = ++requestSequence;
      loading.value = true;
      searchError.value = false;

      try {
        const response = await axios.get('/files/query/organisms/', {
          params: { search: keyword, limit: 20 },
          signal: controller.signal
        });
        if (sequence !== requestSequence) return [];
        options.value = Array.from(new Set(
          (Array.isArray(response.data) ? response.data : [])
            .map((item) => String(item || '').trim())
            .filter(Boolean)
        ));
        activeIndex.value = options.value.length ? 0 : -1;
        suggestionsOpen.value = true;
        return options.value;
      } catch (error) {
        if (error?.name === 'CanceledError' || error?.name === 'AbortError' || axios.isCancel(error)) return [];
        if (sequence === requestSequence) {
          options.value = [];
          activeIndex.value = -1;
          suggestionsOpen.value = false;
          searchError.value = true;
        }
        return [];
      } finally {
        if (sequence === requestSequence) {
          loading.value = false;
          if (activeController === controller) activeController = null;
        }
      }
    };

    const scheduleSearch = () => {
      clearTimeout(debounceTimer);
      const keyword = searchTerm.value.trim();
      if (keyword.length < MIN_SEARCH_LENGTH) {
        clearSuggestions();
        searchError.value = false;
        return;
      }
      debounceTimer = setTimeout(() => fetchSuggestions(keyword), DEBOUNCE_MS);
    };

    const handleInput = () => {
      activeIndex.value = -1;
      scheduleSearch();
    };

    const handleFocus = () => {
      clearTimeout(blurTimer);
      if (options.value.length) suggestionsOpen.value = true;
    };

    const handleBlur = () => {
      blurTimer = setTimeout(() => { suggestionsOpen.value = false; }, 120);
    };

    const selectOption = (accession) => {
      searchTerm.value = accession;
      suggestionsOpen.value = false;
      emit('select', accession);
    };

    const submitSearch = async () => {
      const keyword = searchTerm.value.trim();
      if (keyword.length < MIN_SEARCH_LENGTH) return;
      const existingMatch = options.value.find(
        (item) => item.toLocaleLowerCase() === keyword.toLocaleLowerCase()
      );
      if (existingMatch) {
        selectOption(existingMatch);
        return;
      }
      clearTimeout(debounceTimer);
      await fetchSuggestions(keyword);
    };

    const useExample = (example) => emit('select', example.value);

    const handleKeydown = (event) => {
      if (event.key === 'Escape') {
        suggestionsOpen.value = false;
        return;
      }
      if (event.key === 'ArrowDown' && options.value.length) {
        event.preventDefault();
        suggestionsOpen.value = true;
        activeIndex.value = (activeIndex.value + 1) % options.value.length;
        return;
      }
      if (event.key === 'ArrowUp' && options.value.length) {
        event.preventDefault();
        suggestionsOpen.value = true;
        activeIndex.value = activeIndex.value <= 0 ? options.value.length - 1 : activeIndex.value - 1;
        return;
      }
      if (event.key === 'Enter' && suggestionsOpen.value && activeIndex.value >= 0) {
        event.preventDefault();
        selectOption(options.value[activeIndex.value]);
      }
    };

    onBeforeUnmount(() => {
      clearTimeout(debounceTimer);
      clearTimeout(blurTimer);
      cancelPendingRequest();
      requestSequence += 1;
    });

    return {
      activeIndex,
      activeOptionId,
      examples,
      handleBlur,
      handleFocus,
      handleInput,
      handleKeydown,
      listboxId,
      loading,
      optionId,
      options,
      searchError,
      searchInput,
      searchTerm,
      searchTitleId,
      selectOption,
      submitSearch,
      suggestionsOpen,
      useExample
    };
  }
};
</script>

<style scoped>
.search-panel { padding:16px 20px 14px; border:1px solid rgba(202,220,240,.9); border-radius:12px; background:rgba(255,255,255,.97); box-shadow:0 10px 28px rgba(49,93,147,.06); }
.search-panel h2 { margin:0; color:#086cde; font-size:17px; }
.search-form { display:grid; grid-template-columns:minmax(0,1fr) 134px; margin-top:12px; }
.combobox-shell { position:relative; display:flex; align-items:center; min-width:0; }
.search-icon { position:absolute; left:17px; z-index:2; color:#173f75; font-size:20px; pointer-events:none; }
.combobox-shell input { width:100%; height:46px; padding:0 118px 0 48px; border:1px solid #cbdcf1; border-right:0; border-radius:9px 0 0 9px; outline:0; color:#16385f; background:#fff; font:inherit; font-size:14px; }
.combobox-shell input:focus { border-color:#4c9df3; box-shadow:0 0 0 2px rgba(47,136,255,.12); }
.combobox-shell input::placeholder { color:#7d91ae; }
.search-status { position:absolute; right:14px; color:#6d83a3; font-size:12px; }
.search-button { border:0; border-radius:0 9px 9px 0; color:#fff; background:linear-gradient(180deg,#2e91f5,#0b71df); font-weight:700; cursor:pointer; }
.search-button:disabled { cursor:not-allowed; opacity:.55; }
.suggestion-list { position:absolute; z-index:20; top:calc(100% + 6px); left:0; right:0; max-height:240px; margin:0; padding:6px; overflow-y:auto; list-style:none; border:1px solid #d5e2f3; border-radius:9px; background:#fff; box-shadow:0 12px 28px rgba(32,68,119,.14); }
.suggestion-list li { padding:9px 12px; border-radius:6px; color:#24456f; font-size:13px; cursor:pointer; }
.suggestion-list li.active { color:#075fbf; background:#edf5ff; }
.suggestion-list .empty-option { color:#7a8da9; cursor:default; }
.search-error { margin:8px 0 0; color:#c2413a; font-size:12px; }
.examples { display:flex; justify-content:center; align-items:center; flex-wrap:wrap; gap:9px 15px; margin-top:9px; color:#637a9f; font-size:12px; }
.examples button { padding:0; border:0; background:transparent; color:#0874e9; font:inherit; font-weight:700; cursor:pointer; }
.examples button:hover,.examples button:focus-visible { text-decoration:underline; outline:none; }
@media (max-width:600px) {
  .search-panel { padding:16px; }
  .search-form { grid-template-columns:1fr; gap:8px; }
  .combobox-shell input { padding-right:105px; border-right:1px solid #cbdcf1; border-radius:9px; }
  .search-button { min-height:44px; border-radius:9px; }
}
</style>

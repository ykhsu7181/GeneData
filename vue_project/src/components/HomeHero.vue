<template>
  <div class="home-hero-content">
    <div class="dna-visual" aria-hidden="true">
      <svg viewBox="0 0 220 620">
        <g fill="none" stroke="currentColor" stroke-linecap="round">
          <path d="M42 4c92 82 92 156 0 238s-92 156 0 238 92 132 72 140" />
          <path d="M178 4c-92 82-92 156 0 238s92 156 0 238-92 132-72 140" />
          <path v-for="y in dnaRungs" :key="y" :d="`M58 ${y}h104`" class="dna-rung" />
        </g>
      </svg>
    </div>

    <div class="chromosome-visual" aria-hidden="true">
      <svg viewBox="0 0 390 180">
        <g fill="currentColor">
          <rect x="18" y="18" width="38" height="112" rx="19" transform="rotate(10 37 74)" />
          <rect x="58" y="18" width="38" height="112" rx="19" transform="rotate(10 77 74)" />
          <rect x="180" y="45" width="34" height="88" rx="17" transform="rotate(10 197 89)" />
          <rect x="216" y="45" width="34" height="88" rx="17" transform="rotate(10 233 89)" />
          <rect x="315" y="86" width="28" height="68" rx="14" transform="rotate(10 329 120)" />
          <rect x="345" y="86" width="28" height="68" rx="14" transform="rotate(10 359 120)" />
        </g>
      </svg>
    </div>

    <div class="network-visual" aria-hidden="true">
      <svg viewBox="0 0 380 220">
        <g fill="none" stroke="currentColor">
          <path d="M26 184 86 142l62 28 68-58 62 34 62-56M86 142l22-72 80-18 28 60m-28-60 92-6 60 44" />
        </g>
        <g fill="currentColor">
          <circle v-for="(point, index) in networkPoints" :key="index" :cx="point[0]" :cy="point[1]" r="5" />
        </g>
      </svg>
    </div>

    <div class="hero-copy">
      <h1>GeneData</h1>
      <h2>{{ $t('page.home.subtitle') }}</h2>
      <p class="tagline">{{ $t('page.home.tagline') }}</p>

      <form class="portal-search" role="search" @submit.prevent="submitSearch">
        <label class="search-field">
          <span class="sr-only">{{ $t('page.home.portalSearchLabel') }}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="11" cy="11" r="6"></circle>
            <path d="m16 16 4 4"></path>
          </svg>
          <input
            v-model="queryText"
            type="search"
            :placeholder="$t('page.home.portalSearchPlaceholder')"
            autocomplete="off"
          />
        </label>
        <button type="submit">{{ $t('common.search') }}</button>
      </form>

      <div class="search-examples" :aria-label="$t('page.home.searchExamplesLabel')">
        <span>{{ $t('common.examples') }}:</span>
        <button
          v-for="example in searchExamples"
          :key="example"
          type="button"
          @click="submitExample(example)"
        >
          {{ example }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

export default {
  name: 'HomeHero',
  emits: ['search'],
  setup(_, { emit }) {
    const { t } = useI18n()
    const queryText = ref('')
    const searchExamples = computed(() => [
      t('page.home.examples.accession'),
      t('page.home.examples.species'),
      t('page.home.examples.genome'),
      t('page.home.examples.annotation')
    ])
    const dnaRungs = [48, 92, 138, 184, 230, 276, 322, 368, 414, 460, 506, 552]
    const networkPoints = [
      [26, 184], [86, 142], [148, 170], [216, 112], [278, 146],
      [340, 90], [108, 70], [188, 52], [280, 46]
    ]

    const submitSearch = () => {
      const query = queryText.value.trim()
      if (query) emit('search', query)
    }

    const submitExample = (example) => {
      queryText.value = example
      submitSearch()
    }

    return {
      queryText,
      searchExamples,
      dnaRungs,
      networkPoints,
      submitSearch,
      submitExample
    }
  }
}
</script>

<style scoped>
.home-hero-content {
  position: relative;
  min-height: 420px;
  overflow: hidden;
  display: grid;
  place-items: start center;
  padding: 70px 24px 40px;
  color: #0c2346;
}

.hero-copy {
  position: relative;
  z-index: 2;
  width: min(840px, 100%);
  text-align: center;
}

h1 {
  margin: 0;
  font-size: clamp(3.5rem, 6vw, 5rem);
  line-height: 0.95;
  letter-spacing: -0.045em;
  font-weight: 800;
}

h2 {
  margin: 18px 0 0;
  color: #4e6a8d;
  font-size: clamp(1.65rem, 3vw, 2.35rem);
  line-height: 1.15;
  font-weight: 650;
  letter-spacing: -0.025em;
}

.tagline {
  margin: 18px 0 0;
  color: #536f91;
  font-size: 1.05rem;
}

.tagline span {
  margin: 0 7px;
  color: #7d9abb;
}

.portal-search {
  width: min(780px, 100%);
  min-height: 62px;
  margin: 44px auto 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 126px;
  overflow: hidden;
  border: 1px solid #c8daed;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 16px 36px rgba(33, 86, 145, 0.1);
}

.search-field {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 22px;
}

.search-field svg {
  width: 24px;
  flex: 0 0 24px;
  fill: none;
  stroke: #234b75;
  stroke-width: 2;
}

.search-field input {
  width: 100%;
  min-width: 0;
  height: 60px;
  padding: 0;
  border: 0;
  outline: 0;
  color: #173554;
  background: transparent;
  font: inherit;
  font-size: 1rem;
}

.search-field input::placeholder {
  color: #8b9eb6;
}

.portal-search:focus-within {
  border-color: #6da8e7;
  box-shadow: 0 16px 36px rgba(33, 86, 145, 0.12), 0 0 0 4px rgba(22, 119, 232, 0.12);
}

.portal-search > button {
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, #2385ef, #1268cc);
  font: inherit;
  font-size: 1rem;
  font-weight: 750;
  cursor: pointer;
}

.portal-search > button:hover,
.portal-search > button:focus-visible {
  background: linear-gradient(135deg, #1679df, #095ab9);
}

.search-examples {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px 18px;
  color: #657c98;
  font-size: 0.82rem;
}

.search-examples button {
  padding: 0;
  border: 0;
  background: transparent;
  color: #58728f;
  font: inherit;
  cursor: pointer;
}

.search-examples button:hover,
.search-examples button:focus-visible {
  color: #126fd8;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.dna-visual,
.chromosome-visual,
.network-visual {
  position: absolute;
  z-index: 1;
  pointer-events: none;
  user-select: none;
}

.dna-visual {
  left: -24px;
  top: -12px;
  width: 230px;
  color: #77b8ec;
  opacity: 0.38;
}

.dna-visual path:not(.dna-rung) {
  stroke-width: 12;
  opacity: 0.52;
}

.dna-rung {
  stroke-width: 6;
  opacity: 0.8;
}

.chromosome-visual {
  right: 50px;
  top: 16px;
  width: 390px;
  color: #8dc0ef;
  opacity: 0.25;
}

.network-visual {
  right: 20px;
  bottom: -40px;
  width: 350px;
  color: #5fa8e7;
  opacity: 0.32;
}

.network-visual path {
  stroke-width: 1.5;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 1200px) {
  .dna-visual { left: -90px; opacity: 0.24; }
  .chromosome-visual { right: -100px; opacity: 0.18; }
  .network-visual { right: -100px; opacity: 0.2; }
}

@media (max-width: 860px) {
  .home-hero-content { min-height: 390px; padding-top: 54px; }
  .dna-visual, .chromosome-visual, .network-visual { display: none; }
}

@media (max-width: 620px) {
  .home-hero-content { min-height: 370px; padding: 44px 12px 30px; }
  h1 { font-size: 3rem; }
  h2 { font-size: 1.45rem; }
  .tagline { font-size: 0.9rem; }
  .portal-search { grid-template-columns: minmax(0, 1fr) 92px; min-height: 56px; margin-top: 34px; }
  .search-field { padding: 0 14px; gap: 9px; }
  .search-field svg { width: 20px; flex-basis: 20px; }
  .search-field input { height: 54px; font-size: 0.88rem; }
}
</style>

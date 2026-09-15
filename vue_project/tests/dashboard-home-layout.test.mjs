import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const readSource = (...segments) => readFileSync(join(process.cwd(), ...segments), 'utf8')
const dashboardSource = readSource('src', 'views', 'DashboardHomeView.vue')
const heroSource = readSource('src', 'components', 'HomeHero.vue')
const featuredSource = readSource('src', 'components', 'FeaturedAccessions.vue')
const statsSource = readSource('src', 'components', 'HomeStatsBar.vue')

test('portal homepage composes the three focused homepage components', () => {
  assert.match(dashboardSource, /<HomeHero @search="handleSearch"/)
  assert.match(dashboardSource, /<FeaturedAccessions/)
  assert.match(dashboardSource, /<HomeStatsBar :summary="dashboard\.summary"/)
})

test('portal homepage removes the legacy dashboard runtime chain', () => {
  for (const legacyName of [
    'DashboardHero',
    'SpeciesCardGrid',
    'DataResourceSummary',
    'DistributionPanel',
    'GeoMapPanel',
    'RecentUpdatesBar',
    'IntersectionObserver',
    'defineAsyncComponent'
  ]) {
    assert.doesNotMatch(dashboardSource, new RegExp(legacyName))
  }
})

test('hero provides unified search and clickable examples', () => {
  assert.match(heroSource, /role="search"/)
  assert.match(heroSource, /@submit\.prevent="submitSearch"/)
  assert.match(heroSource, /page\.home\.portalSearchPlaceholder/)
  assert.match(heroSource, /v-for="example in searchExamples"/)
  assert.match(heroSource, /const query = queryText\.value\.trim\(\)/)
})

test('featured accessions use the canonical accession route query', () => {
  assert.match(dashboardSource, /name: 'accession-card', query: \{ accession: item\.accession \}/)
  assert.match(featuredSource, /page\.home\.featuredAccessions/)
  assert.match(featuredSource, /<th scope="col">Accession<\/th>/)
  assert.match(featuredSource, /@click="\$emit\('select', item\)"/)
})

test('stats bar exposes the agreed portal metrics', () => {
  for (const key of ['assemblies', 'species', 'annotations', 'accessions']) {
    assert.match(statsSource, new RegExp(`t\\('page\\.home\\.stats\\.${key}'\\)`))
  }
  assert.match(statsSource, /key: 'assembly_count'/)
  assert.match(statsSource, /return '—'/)
})

test('portal components include compact responsive behavior', () => {
  assert.match(heroSource, /@media \(max-width: 620px\)/)
  assert.match(featuredSource, /@media \(max-width: 680px\)/)
  assert.match(featuredSource, /td::before \{ content: attr\(data-label\)/)
  assert.match(statsSource, /grid-template-columns: repeat\(2, 1fr\)/)
})

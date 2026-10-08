import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const read = (path) => readFileSync(join(process.cwd(), path), 'utf8')
const routerSource = read('src/router/index.js')
const navSource = read('src/config/topNavConfig.mjs')
const searchSource = read('src/config/dashboardSearch.js')
const homeSource = read('src/views/HomeView.vue')
const chartSource = read('src/views/DataChartView.vue')

test('legacy Genome URL redirects by the most specific available context', () => {
  assert.match(routerSource, /path:\s*'\/genome-card'[\s\S]*?redirect:\s*\(to\)\s*=>/)
  assert.match(routerSource, /name:\s*'assembly-detail',\s*params:\s*\{\s*assemblyId\s*\}/)
  assert.match(routerSource, /name:\s*'accession-detail',\s*query:\s*\{\s*accession\s*\}/)
  assert.match(routerSource, /return \{ name: 'accession-card' \}/)
  assert.doesNotMatch(routerSource, /import\('\.\.\/views\/GenomeCard\.vue'\)/)
})

test('visible navigation and dashboard search no longer enter Genome', () => {
  assert.doesNotMatch(navSource, /path:\s*'\/genome-card'/)
  assert.doesNotMatch(searchSource, /path:\s*'\/genome-card'/)
  assert.match(searchSource, /keywords: \['genome', '基因组'\][\s\S]*?path: '\/accession-card'/)
})

test('remaining data entry points open Assembly details with an Accession fallback', () => {
  assert.match(homeSource, /:to="buildGenomeRoute\(scope\.row\)"/)
  assert.match(homeSource, /name:\s*'assembly-detail'[\s\S]*?assemblyId:\s*row\.default_assembly_id/)
  assert.match(homeSource, /name:\s*'accession-detail'[\s\S]*?accession:\s*row\.accession/)
  assert.match(chartSource, /moduleKey === 'genome'[\s\S]*?name:\s*'assembly-detail'/)
  assert.match(chartSource, /moduleKey === 'genome'[\s\S]*?name:\s*'accession-detail'/)
  assert.doesNotMatch(`${homeSource}\n${chartSource}`, /['"]\/genome-card['"]/)
})

test('retired Genome page implementation is removed', () => {
  for (const path of [
    'src/views/GenomeCard.vue',
    'src/components/genome/GenomeListPanel.vue',
    'src/components/genome/GenomeFileDrawer.vue'
  ]) {
    assert.equal(existsSync(join(process.cwd(), path)), false, `${path} should be removed`)
  }
})

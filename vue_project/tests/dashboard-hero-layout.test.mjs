import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const heroPath = join(process.cwd(), 'src', 'components', 'HomeHero.vue')
const source = readFileSync(heroPath, 'utf8')

test('portal hero uses the approved GeneData identity and search-first content', () => {
  assert.match(source, /<h1>GeneData<\/h1>/)
  assert.match(source, /\$t\('page\.home\.subtitle'\)/)
  assert.match(source, /\$t\('page\.home\.tagline'\)/)
  assert.match(source, /role="search"/)
})

test('portal hero trims input and ignores empty searches', () => {
  assert.match(source, /const query = queryText\.value\.trim\(\)/)
  assert.match(source, /if \(query\) emit\('search', query\)/)
  assert.match(source, /@submit\.prevent="submitSearch"/)
})

test('portal hero exposes only working search examples', () => {
  assert.match(source, /t\('page\.home\.examples\.accession'\)/)
  assert.match(source, /t\('page\.home\.examples\.species'\)/)
  assert.match(source, /t\('page\.home\.examples\.genome'\)/)
  assert.match(source, /t\('page\.home\.examples\.annotation'\)/)
  assert.match(source, /@click="submitExample\(example\)"/)
  assert.match(source, /queryText\.value = example/)
})

test('portal hero decoration is non-interactive and responsive', () => {
  assert.match(source, /class="dna-visual" aria-hidden="true"/)
  assert.match(source, /pointer-events: none;/)
  assert.match(source, /user-select: none;/)
  assert.match(source, /@media \(max-width: 860px\)[\s\S]*?display: none;/)
})

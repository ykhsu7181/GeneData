import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(join(process.cwd(), 'src', 'config', 'dashboardSearch.js'), 'utf8')

test('portal search no longer depends on legacy dashboard payload fields', () => {
  assert.doesNotMatch(
    source,
    /species_cards|sub_population_distribution|dataset_type_summary|geo_distribution/
  )
})

test('portal search routes scientific names to data search and accessions to accession page', () => {
  assert.match(source, /if \(\/\\s\/\.test\(trimmedQuery\)\)/)
  assert.match(source, /path: '\/data-overview'[\s\S]*?search: trimmedQuery/)
  assert.match(source, /path: '\/accession-card'[\s\S]*?accession: trimmedQuery/)
})

test('portal search keeps hidden tool mappings and does not invent an Assembly mapping', () => {
  assert.match(source, /keywords: \['codon', '密码子'\][\s\S]*?path: '\/codon-card'/)
  assert.match(source, /keywords: \['core', 'variable', '区块', '核心可变'\][\s\S]*?path: '\/core-variable-blocks'/)
  assert.doesNotMatch(source, /keywords:\s*\[[^\]]*assembly/i)
})

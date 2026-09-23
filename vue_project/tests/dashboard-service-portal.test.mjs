import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(join(process.cwd(), 'src', 'services', 'dashboard.js'), 'utf8')

test('empty dashboard payload exposes nullable portal metrics', () => {
  for (const key of ['assembly_count', 'species_count', 'annotation_count', 'accession_count']) {
    assert.match(source, new RegExp(`${key}: null`))
  }
  assert.match(source, /featured_accessions: \[\]/)
})

test('dashboard service no longer exposes legacy dashboard fields', () => {
  assert.doesNotMatch(source, /species_cards|resource_summary|geo_distribution/)
})

test('homepage keeps the established response key for popular accession compatibility', () => {
  assert.match(source, /featured_accessions: \[\]/)
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/views/TranscriptomeOverviewView.vue'), 'utf8')

assert.match(source, /page\.transcriptomeOverview\.title/, 'Transcriptome overview should use its localized title')
assert.match(source, /query\/transcriptome-list\//, 'Transcriptome list should load rows from transcriptome-list endpoint')
assert.match(source, /query\/transcriptome-files\//, 'Transcriptome list should load drawer files from transcriptome-files endpoint')
assert.match(source, /page\.transcriptomeOverview\.searchPlaceholder/, 'Transcriptome list should localize the search placeholder')
assert.match(source, /page\.transcriptomeOverview\.assembly/, 'Transcriptome filter/table should localize Assembly labels')
assert.match(source, /page\.transcriptomeOverview\.sampleType/, 'Transcriptome filter/table should localize sample-type labels')
assert.match(source, /page\.transcriptomeOverview\.dataSize/, 'Transcriptome table should localize data-size labels')
assert.match(source, /page\.transcriptomeOverview\.viewDetail/, 'Transcriptome rows should provide a localized detail action')
assert.match(source, /page\.transcriptomeOverview\.viewFiles/, 'Transcriptome rows should provide a localized view-files action')
assert.match(source, /fileDrawerVisible/, 'Transcriptome list should have a file drawer')
assert.match(source, /data-files/, 'Transcriptome downloads should use DataFile download URLs')

for (const matrixColumn of ['label="all"', 'label="leaf"', 'label="panicles"', 'label="shoot"', 'label="stem"', 'label="root"']) {
  assert.doesNotMatch(source, new RegExp(matrixColumn), `Transcriptome page must not keep old matrix column ${matrixColumn}`)
}

assert.doesNotMatch(source, /download-transcriptome/, 'Transcriptome page must not call the old transcriptome download endpoint')
assert.doesNotMatch(source, /\/gd\/api\/files\/genome-files\//, 'Transcriptome page must not reference old genome-files download URLs')
assert.doesNotMatch(source, /legacy_genomefile/, 'Transcriptome page must not reference legacy source names')
assert.doesNotMatch(source, /organism_fallback/, 'Transcriptome page must not reference organism fallback')

console.log('transcriptome list view source checks passed')

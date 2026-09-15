import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/views/GenomeCard.vue'), 'utf8')

assert.match(source, /await fetchChromosomesForCurrentContext\(\);/, 'Accession changes must reload chromosomes')
assert.match(source, /new AbortController\(\)/, 'Genome requests should cancel stale work')
assert.match(source, /visualizationRequestId/, 'Visualization responses must be scoped to their request')
assert.match(source, /buildVisualizationContextKey/, 'Visualization responses must be scoped to the current context')
assert.match(source, /await nextTick\(\);/, 'Drawing should wait for Vue DOM updates')
assert.doesNotMatch(source, /setTimeout\(\(\) => \{\s*drawChromosomeVisualization\(\);\s*\}, 100\)/, 'Drawing must not rely on a fixed 100ms delay')
assert.match(source, /watch\(\[selectedChromosome, contextAssemblyId\]/, 'The visualization watcher should not duplicate work on accession assignment')
assert.match(source, /Promise\.allSettled\(/, 'Optional visualization tracks should not block each other')
assert.match(source, /commitVisualizationResults/, 'Visualization results should be committed together after the context check')
assert.match(source, /showVisualizationEmptyState\(t\('page\.genomeCard\.chromosomeLengthMissing'\)\)/, 'Missing chromosome length must show a localized explicit empty state')
assert.match(source, /onBeforeUnmount\(/, 'Pending visualization requests should be cancelled on component unmount')
assert.match(source, /Genome visualization draw context/, 'Drawing diagnostics should include the active context')

console.log('genome accession to chromosome sync source checks passed')

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const repoRoot = process.cwd()
const viewSource = readFileSync(resolve(repoRoot, 'src/views/GenomeCard.vue'), 'utf8')
const listSource = readFileSync(resolve(repoRoot, 'src/components/genome/GenomeListPanel.vue'), 'utf8')
const drawerSource = readFileSync(resolve(repoRoot, 'src/components/genome/GenomeFileDrawer.vue'), 'utf8')
const source = `${viewSource}\n${listSource}\n${drawerSource}`

assert.match(viewSource, /GenomeListPanel/, 'GenomeCard should delegate list rendering to GenomeListPanel')
assert.match(viewSource, /GenomeFileDrawer/, 'GenomeCard should delegate file drawer rendering to GenomeFileDrawer')
assert.match(source, /page\.genomeCard\.visualizationView/, 'Genome page should keep a localized visualization switch')
assert.match(source, /page\.genomeCard\.dataList/, 'Genome page should keep a localized data-list switch')
assert.match(source, /activeView/, 'Genome page should switch between visualization and list views')
assert.match(viewSource, /v-model="contextAssemblyId"/, 'Genome visualization should require explicit Assembly context')
assert.match(viewSource, /selectUnambiguousAssembly/, 'Genome visualization must not guess among multiple assemblies')
assert.match(viewSource, /!selectedOrganism \|\| !contextAssemblyId \|\| !selectedChromosome/, 'Genome visualization should load only with complete context')
assert.match(source, /query\/genome-list\//, 'Genome list view should load rows from the genome-list endpoint')
assert.match(source, /query\/genome-files\//, 'Genome list view should load drawer files from the genome-files endpoint')
assert.match(source, /page\.genomeCard\.selectSpecies/, 'Genome list should localize its species selector')
assert.match(source, /page\.genomeCard\.selectAccession/, 'Genome list should localize its Accession selector')
assert.match(source, /page\.genomeCard\.selectAssemblyLevel/, 'Genome list should localize its assembly-level selector')
assert.match(source, /Chromosome/, 'Genome list should expose Chromosome assembly level')
assert.match(source, /Scaffold/, 'Genome list should expose Scaffold assembly level')
assert.match(source, /Contig/, 'Genome list should expose Contig assembly level')
assert.match(source, /page\.genomeCard\.viewFiles/, 'Genome list rows should provide a localized view-files action')
assert.match(source, /downloadGenomeRow/, 'Genome list rows should provide download behavior')
assert.match(source, /fileDrawerVisible/, 'Genome list should have a file drawer')
assert.match(source, /data-files/, 'Genome downloads should use DataFile download URLs')
assert.doesNotMatch(source, /\/gd\/api\/files\/genome-files\//, 'GenomeCard must not reference old genome-files download URLs')
assert.doesNotMatch(source, /legacy_genomefile/, 'GenomeCard must not reference legacy source names')
assert.doesNotMatch(source, /organism_fallback/, 'GenomeCard must not reference organism fallback')

console.log('genome list view source checks passed')

const MODULE_KEYWORDS = [
  { keywords: ['home', 'dashboard', '首页'], route: { path: '/dashboard' } },
  { keywords: ['accession', '品种', '材料'], route: { path: '/accession-card' } },
  { keywords: ['genome', '基因组'], route: { path: '/genome-card' } },
  { keywords: ['annotation', '注释'], route: { path: '/annotation' } },
  { keywords: ['transcriptome', '转录组'], route: { path: '/transcriptome-overview' } },
  { keywords: ['codon', '密码子'], route: { path: '/codon-card' } },
  { keywords: ['core', 'variable', '区块', '核心可变'], route: { path: '/core-variable-blocks' } },
  { keywords: ['map', 'geo', 'location', '地理', '地图'], route: { path: '/accession-map' } }
]

const normalize = (value) => (value || '').trim().toLowerCase()

export const resolveDashboardSearch = (query) => {
  const trimmedQuery = (query || '').trim()
  if (!trimmedQuery) {
    return null
  }

  const normalizedQuery = normalize(trimmedQuery)

  const moduleMatch = MODULE_KEYWORDS.find((item) =>
    item.keywords.some((keyword) => normalizedQuery.includes(normalize(keyword)))
  )
  if (moduleMatch) {
    return moduleMatch.route
  }

  // Scientific names contain whitespace and belong in the existing data search.
  if (/\s/.test(trimmedQuery)) {
    return {
      path: '/data-overview',
      query: {
        search: trimmedQuery
      }
    }
  }

  return {
    path: '/accession-card',
    query: {
      accession: trimmedQuery
    }
  }
}

export const topNavGroups = {
  home: {
    key: 'home',
    labelKey: 'nav.home',
    path: '/dashboard'
  },
  accession: {
    key: 'accession',
    labelKey: 'nav.accession',
    path: '/accession-card'
  },
  dataOverview: {
    key: 'dataOverview',
    labelKey: 'nav.dataResources',
    path: '/data-overview',
    children: [
      { labelKey: 'nav.rawData', path: '/raw-data' },
      { labelKey: 'nav.dataOverview', path: '/data-overview' },
      { labelKey: 'nav.genome', path: '/genome-card' },
      { labelKey: 'nav.annotation', path: '/annotation' },
      { labelKey: 'nav.transcriptomeOverview', path: '/transcriptome-overview' }
    ]
  },
  tools: {
    key: 'tools',
    labelKey: 'nav.tools',
    children: [
      { labelKey: 'nav.coreVariableBlocks', path: '/core-variable-blocks' },
      { labelKey: 'nav.codon', path: '/codon-card' },
      { labelKey: 'nav.codonw', path: '/tools/codonw' }
    ]
  }
}

const pathAliasMap = {
  '/': '/dashboard',
  '/annotation-card': '/annotation',
  '/core-variable-blocks-card': '/core-variable-blocks',
  '/accession-detail': '/accession-card'
}

const groupMatchers = {
  home: ['/dashboard'],
  accession: ['/accession-card', '/accession-detail', '/accession-map'],
  dataOverview: ['/raw-data', '/data-overview', '/genome-card', '/annotation', '/annotation-card', '/transcriptome-overview'],
  tools: ['/core-variable-blocks', '/core-variable-blocks-card', '/codon-card', '/tools/codonw']
}

export const normalizeTopNavPath = (path = '') => pathAliasMap[path] || path

export const getTopNavActiveGroup = (path = '') => {
  const normalizedPath = normalizeTopNavPath(path)

  return (
    Object.entries(groupMatchers).find(([, paths]) =>
      paths.some((matcherPath) => normalizedPath === matcherPath || normalizedPath.startsWith(`${matcherPath}/`))
    )?.[0] || null
  )
}

export const isTopNavGroupActive = (groupKey, path = '') => getTopNavActiveGroup(path) === groupKey

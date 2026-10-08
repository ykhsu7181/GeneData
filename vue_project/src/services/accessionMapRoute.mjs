const firstValue = (value) => Array.isArray(value) ? value[0] : value;
const cleanText = (value) => String(firstValue(value) || '').trim();

export const parseAccessionMapQuery = (query = {}) => {
  const subPopulations = cleanText(query.sub_population)
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  return {
    accession: cleanText(query.accession || query.organism),
    region: cleanText(query.region),
    subPopulations: Array.from(new Set(subPopulations)).sort((a, b) => a.localeCompare(b))
  };
};

export const serializeAccessionMapQuery = (filters = {}) => {
  const query = {};
  const accession = cleanText(filters.accession);
  const region = cleanText(filters.region);
  const subPopulations = Array.from(new Set(
    (Array.isArray(filters.subPopulations) ? filters.subPopulations : [])
      .map(cleanText)
      .filter(Boolean)
  )).sort((a, b) => a.localeCompare(b));

  if (accession) query.accession = accession;
  if (region) query.region = region;
  if (subPopulations.length) query.sub_population = subPopulations.join(',');
  return query;
};

export const normalizeAccessionMapReturnPath = (value) => {
  const candidate = cleanText(value);
  if (!candidate.startsWith('/accession-map')) return '';
  try {
    const parsed = new URL(candidate, 'https://genedata.local');
    if (parsed.origin !== 'https://genedata.local' || parsed.pathname !== '/accession-map') return '';
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return '';
  }
};

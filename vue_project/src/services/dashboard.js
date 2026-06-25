import axios from 'axios'

export const emptyDashboardPayload = () => ({
  summary: {
    species_count: 0,
    accession_count: 0,
    sample_count: 0,
    dataset_count: 0,
    datafile_count: 0,
    total_size: 0,
    total_size_display: '0 B'
  },
  species_cards: [],
  sub_population_distribution: [],
  xi_distribution: [],
  dataset_type_summary: [],
  file_role_summary: [],
  resource_summary: [],
  recent_updates: [],
  geo_distribution: [],
  hot_keywords: []
})

export const fetchDashboardData = async () => {
  const response = await axios.get('/warehouse/dashboard/')
  return {
    ...emptyDashboardPayload(),
    ...(response.data || {})
  }
}

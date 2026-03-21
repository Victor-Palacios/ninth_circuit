// Column metadata: human-readable labels, types, and grouping

// Compute min-width from the label text length
// ~8px per uppercase character at text-xs + tracking + padding on both sides
const CHAR_WIDTH = 8
const CELL_PADDING = 40 // px-5 on each side
const MIN_COL_WIDTH = 80

export function getColumnWidth(col) {
  const label = COLUMN_LABELS[col] || col.replace(/_/g, ' ')
  return Math.max(MIN_COL_WIDTH, label.length * CHAR_WIDTH + CELL_PADDING)
}

export const COLUMN_LABELS = {
  published_status: 'Status',
  date_filed: 'Date Filed',
  docket_no: 'Docket No.',
  char_count: 'Length',
  link: 'PDF',
  country_of_origin: 'Country',
  final_disposition: 'Disposition',
  asylum_requested: 'Asylum',
  withholding_requested: 'Withholding',
  CAT_requested: 'CAT',
  protected_ground_race: 'Race',
  protected_ground_religion: 'Religion',
  protected_ground_nationality: 'Nationality',
  protected_ground_political_opinion: 'Political Opinion',
  protected_ground_particular_social_group: 'Social Group',
  nexus_explicit_nexus_language: 'Explicit Language',
  nexus_nexus_strength: 'Nexus Strength',
  past_persecution_established: 'Established',
  past_persecution_physical_violence: 'Physical Violence',
  past_persecution_detention: 'Detention',
  past_persecution_sexual_violence: 'Sexual Violence',
  past_persecution_death_threats: 'Death Threats',
  past_persecution_harm_severity: 'Harm Severity',
  persecutor_government_actor: 'Gov. Actor',
  persecutor_non_state_actor: 'Non-State Actor',
  persecutor_government_unable_or_unwilling: 'Gov. Unable/Unwilling',
  future_fear_well_founded_fear: 'Well-Founded Fear',
  future_fear_internal_relocation_reasonable: 'Internal Relocation',
  future_fear_changed_country_conditions: 'Changed Conditions',
  credibility_credibility_finding: 'Credibility Finding',
  credibility_inconsistencies_central: 'Central Inconsistencies',
  credibility_corroboration_present: 'Corroboration',
  country_conditions_cited: 'Conditions Cited',
  bars_one_year_deadline_missed: 'One-Year Bar',
  bars_firm_resettlement: 'Firm Resettlement',
  bars_particularly_serious_crime: 'Serious Crime',
}

export const COLUMN_GROUPS = [
  {
    key: 'meta',
    label: 'Case Info',
    columns: ['published_status', 'date_filed', 'docket_no', 'char_count', 'link'],
  },
  {
    key: 'origin',
    label: 'Origin & Disposition',
    columns: ['country_of_origin', 'final_disposition'],
  },
  {
    key: 'claims',
    label: 'Claims',
    columns: ['asylum_requested', 'withholding_requested', 'CAT_requested'],
  },
  {
    key: 'grounds',
    label: 'Protected Grounds',
    columns: [
      'protected_ground_race', 'protected_ground_religion',
      'protected_ground_nationality', 'protected_ground_political_opinion',
      'protected_ground_particular_social_group',
    ],
  },
  {
    key: 'nexus',
    label: 'Nexus',
    columns: ['nexus_explicit_nexus_language', 'nexus_nexus_strength'],
  },
  {
    key: 'persecution',
    label: 'Past Persecution',
    columns: [
      'past_persecution_established', 'past_persecution_physical_violence',
      'past_persecution_detention', 'past_persecution_sexual_violence',
      'past_persecution_death_threats', 'past_persecution_harm_severity',
    ],
  },
  {
    key: 'persecutor',
    label: 'Persecutor',
    columns: [
      'persecutor_government_actor', 'persecutor_non_state_actor',
      'persecutor_government_unable_or_unwilling',
    ],
  },
  {
    key: 'future',
    label: 'Future Fear',
    columns: [
      'future_fear_well_founded_fear', 'future_fear_internal_relocation_reasonable',
      'future_fear_changed_country_conditions',
    ],
  },
  {
    key: 'credibility',
    label: 'Credibility',
    columns: [
      'credibility_credibility_finding', 'credibility_inconsistencies_central',
      'credibility_corroboration_present',
    ],
  },
  {
    key: 'country',
    label: 'Country Conditions',
    columns: ['country_conditions_cited'],
  },
  {
    key: 'bars',
    label: 'Bars',
    columns: [
      'bars_one_year_deadline_missed', 'bars_firm_resettlement',
      'bars_particularly_serious_crime',
    ],
  },
]

// Flat ordered list of visible columns (no evidence)
export const VISIBLE_COLUMNS = COLUMN_GROUPS.flatMap(g => g.columns)

// Columns that should not have filters
export const NO_FILTER_COLS = ['link']

// Binary dropdown columns
export const BINARY_COLS = { published_status: ['Published', 'Unpublished'] }

// Numeric columns
export const NUMERIC_COLS = ['char_count']

// Date columns
export const DATE_COLS = ['date_filed']

// Boolean columns
export const BOOLEAN_COLS = VISIBLE_COLUMNS.filter(col =>
  !['published_status', 'date_filed', 'docket_no', 'char_count', 'link',
    'country_of_origin', 'final_disposition'].includes(col)
)

// Column type detection
export function getFilterType(col) {
  if (NO_FILTER_COLS.includes(col)) return 'none'
  if (col in BINARY_COLS) return 'binary'
  if (DATE_COLS.includes(col)) return 'date'
  if (NUMERIC_COLS.includes(col)) return 'numeric'
  if (BOOLEAN_COLS.includes(col)) return 'boolean'
  return 'text'
}

// Get human-readable label for a column
export function getLabel(col) {
  return COLUMN_LABELS[col] || col.replace(/_/g, ' ')
}

// Get the evidence column name for a given boolean column
export function getEvidenceCol(col) {
  return `${col}_evidence`
}

// All evidence column names
export const EVIDENCE_COLUMNS = BOOLEAN_COLS.map(getEvidenceCol).concat([
  'country_of_origin_evidence',
  'final_disposition_evidence',
  'court_level_evidence',
])

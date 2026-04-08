/** Column header configuration for a single search-engine profile. */
export interface ColumnHeaderSet {
  name: string;
  glycan_composition: string;
  protein_accessions: string;
  position_in_protein: string;
  master_protein_descriptions: string;
  sequence: string;
  modifications: string;
  modifications_fallback: string;
  retention_time: string;
  fdr_prefix: string;
  engine_score_prefix: string;
  ppm_prefix: string;
  abundance_columns: string;
}

/** Pre-built Byonic defaults. */
export const BYONIC_HEADER_SET: ColumnHeaderSet = {
  name: "Byonic",
  glycan_composition: "Glycan Composition",
  protein_accessions: "Protein Accessions",
  position_in_protein: "Position in Protein",
  master_protein_descriptions: "Master Protein Descriptions",
  sequence: "Sequence",
  modifications: "Modifications (all possible sites)",
  modifications_fallback: "Modifications",
  retention_time: "Top Apex RT [min]",
  fdr_prefix: "FDR 2D (by Search Engine)",
  engine_score_prefix: "Byonic Score (",
  ppm_prefix: "DeltaM [ppm] ",
  abundance_columns: "Abundances (Grouped)*",
};

/** Customized set – defaults to Byonic values so users only edit what differs. */
export const CUSTOM_HEADER_SET: ColumnHeaderSet = {
  ...BYONIC_HEADER_SET,
  name: "Customized",
};

/** Pre-built MSFragger defaults (native column names). */
export const MSFRAGGER_HEADER_SET: ColumnHeaderSet = {
  name: "MSFragger",
  glycan_composition: "",
  protein_accessions: "Protein ID",
  position_in_protein: "",
  master_protein_descriptions: "Protein Description",
  sequence: "",
  modifications: "Assigned Modifications",
  modifications_fallback: "",
  retention_time: "",
  fdr_prefix: "Probability",
  engine_score_prefix: "",
  ppm_prefix: "",
  abundance_columns: "",
};

export interface AnalysisResponse {
  id: string;
  name: string;
  study_code: string | null;
  quant_method: string | null;
  note: string | null;
  created_at: string;
}

export interface AnalysisRunResult {
  analysis_id: number;
  output_file: string;
  site_to_rows: Record<string, unknown>;
  statistics: Record<string, unknown>;
  qc_output_file: string;
}

export interface UploadResponse {
  file_id: string;
  columns: string[];
  all_headers: string[];
}

export interface FoldChangeResult {
  glycan_list: string[];
  fc: number[];
  p_value: number[];
  anova: number[] | null;
}

export interface FcAvgResult {
  glycan_list: string[];
  mean: number[];
  p_value: number[];
  protein_mean: number[];
  mean_norm: number[];
  anova: number[] | null;
  has_protein_data: boolean;
}

export interface ClusterResult {
  heatmap_data: number[][];
  row_labels: string[];
  col_labels: string[];
  row_dendrogram: DendrogramData | null;
  col_dendrogram: DendrogramData | null;
  total_quantified: number;
  heatmap_count: number;
  zmid: number | null;
  colorbar_title: string;
}

export interface DendrogramData {
  icoord: number[][];
  dcoord: number[][];
  ivl: string[];
  leaves: number[];
}

export interface GlycanSitesResult {
  glycan_to_rows: Record<string, number[]>;
  site_list: string[];
  max_site_pos: number;
  glycan_to_pvalue?: Record<string, number[]>;
}

// ── Analysis detail types ───────────────────────────────────────────────────

export interface FilterParams {
  min_glycopeptides?: number;
  min_unique_glycans?: number;
  glycan_type?: string;
  normalization?: string;
  [key: string]: unknown;
}

export interface QcStats {
  total_proteins: number;
  total_peptides: number;
  total_glycopeptides: number;
  unique_glycans: number;
  total_sites: number;
}

export interface AnalysisDetail extends AnalysisResponse {
  conditions?: string[];
  filter_params?: FilterParams | null;
  qc_stats?: QcStats | null;
}

export interface SiteRow {
  gene: string;
  protein: string;
  accession: string;
  site: string;
  count: number;
}

/** Matches the shape expected by GlycanBarChart */
export interface AbundanceData {
  data: Record<string, number[]>;
  condition_names: string[];
  sample_names: string[];
  composite_scores?: Record<string, Record<string, number[]>>;
}

/** Re-export hook param type for convenience */
export type { RunAnalysisParams } from "../hooks/useApi";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import type {
  AnalysisResponse,
  AnalysisRunResult,
  AnalysisDetail,
  UploadResponse,
  FoldChangeResult,
  FcAvgResult,
  ClusterResult,
  SiteRow,
  AbundanceData,
  ColumnHeaderSet,
} from "../types";

export function useHeaderSets() {
  return useQuery<ColumnHeaderSet[]>({
    queryKey: ["headerSets"],
    queryFn: () => api.get("/settings/header-sets").then((r) => r.data),
  });
}

export function useSaveHeaderSets() {
  return useMutation<ColumnHeaderSet[], Error, ColumnHeaderSet[]>({
    mutationFn: (sets) =>
      api.put("/settings/header-sets", sets).then((r) => r.data),
  });
}

export function useAnalysisList() {
  return useQuery<AnalysisResponse[]>({
    queryKey: ["analyses"],
    queryFn: () => api.get("/analysis/list").then((r) => r.data),
  });
}

export function useDeleteAnalysis() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete(`/analysis/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analyses"] });
    },
  });
}

export function useAnalysis(id: string) {
  return useQuery<AnalysisDetail>({
    queryKey: ["analysis", id],
    queryFn: () => api.get(`/analysis/${id}`).then((r) => r.data),
    enabled: !!id,
  });
}

export interface RunAnalysisParams {
  file_id: string;
  name: string;
  conditions: Record<string, string>;
  fdr_threshold?: number;
  fdr_is_probability?: boolean;
  byonic_score?: number;
  ppm_threshold?: number;
  peptide_length?: number;
  min_count?: number;
  export_filter?: string;
  abundance_type?: string;
  study_code?: string;
  quant_method?: string;
  note?: string;
  w_depth?: number;
  w_conflict?: number;
  w_byonic?: number;
  column_header_sets?: ColumnHeaderSet[];
}

export function useRunAnalysis() {
  return useMutation<AnalysisRunResult, Error, RunAnalysisParams>({
    mutationFn: (params) =>
      api.post("/analysis/run", params).then((r) => r.data),
  });
}

export interface UploadDataFileParams {
  file: File;
  abundancePrefixes?: string[];
}

export function useUploadDataFile() {
  return useMutation<UploadResponse, Error, UploadDataFileParams>({
    mutationFn: ({ file, abundancePrefixes }: UploadDataFileParams) => {
      const formData = new FormData();
      formData.append("file", file);
      if (abundancePrefixes && abundancePrefixes.length > 0) {
        formData.append(
          "abundance_prefixes",
          JSON.stringify(abundancePrefixes),
        );
      }
      return api.post("/upload/data-file", formData).then((r) => r.data);
    },
  });
}

export function useFoldChange() {
  return useMutation<
    FoldChangeResult,
    Error,
    {
      analysis_id: string;
      reference_condition: string;
      comparison_condition: string;
    }
  >({
    mutationFn: (params) =>
      api.post("/foldchange/compute", params).then((r) => r.data),
  });
}

export function useFcAvg() {
  return useMutation<
    FcAvgResult,
    Error,
    {
      analysis_id: string;
      reference_condition: string;
      comparison_condition: string;
    }
  >({
    mutationFn: (params) =>
      api.post("/foldchange/fc-avg", params).then((r) => r.data),
  });
}

export function useCluster() {
  return useMutation<ClusterResult, Error, Record<string, unknown>>({
    mutationFn: (params) =>
      api.post("/heatmap/cluster", params).then((r) => r.data),
  });
}

export function useFastaList() {
  return useQuery<string[]>({
    queryKey: ["fasta"],
    queryFn: () => api.get("/fasta/list").then((r) => r.data),
  });
}

export function useAnalysisSites(id: string) {
  return useQuery<SiteRow[]>({
    queryKey: ["analysis", id, "sites"],
    queryFn: () => api.get(`/analysis/${id}/sites`).then((r) => r.data),
    enabled: !!id,
  });
}

export function useAbundanceData(
  id: string,
  params: { mode: string; metric: string },
) {
  return useQuery<AbundanceData>({
    queryKey: ["analysis", id, "abundance", params],
    queryFn: () =>
      api.get(`/analysis/${id}/abundance`, { params }).then((r) => r.data),
    enabled: !!id,
  });
}

/** Response from per-protein abundance API: keyed by peptide sequence */
export type ProteinAbundanceBySequence = Record<string, AbundanceData>;

export function useProteinAbundance(
  id: string,
  accession: string | null,
  site: string | null,
  params: { mode: string; metric: string },
) {
  return useQuery<ProteinAbundanceBySequence>({
    queryKey: ["analysis", id, "protein-abundance", accession, site, params],
    queryFn: () =>
      api
        .get(`/analysis/${id}/protein/${accession}/abundance`, {
          params: { ...params, ...(site ? { site } : {}) },
        })
        .then((r) => r.data),
    enabled: !!id && !!accession,
  });
}

export function useMultiSiteAbundance(
  id: string,
  sites: { accession: string; site: string }[],
  params: { mode: string; metric: string },
) {
  return useQuery<AbundanceData>({
    queryKey: ["analysis", id, "multi-site-abundance", sites, params],
    queryFn: () =>
      api
        .post(`/analysis/${id}/multi-site-abundance`, { sites }, { params })
        .then((r) => r.data),
    enabled: !!id && sites.length > 0,
  });
}

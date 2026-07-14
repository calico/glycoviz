import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileUploadDropzone } from "../components/upload/FileUploadDropzone";
import { DataTable, type Column } from "../components/tables/DataTable";
import { LoadingSpinner } from "../components/LoadingSpinner";
import {
  useUploadDataFile,
  useRunAnalysis,
  useAnalysisList,
  useDeleteAnalysis,
  useHeaderSets,
  useSaveHeaderSets,
} from "../hooks/useApi";
import type {
  AnalysisResponse,
  ColumnHeaderSet,
  UploadResponse,
} from "../types";
import {
  BYONIC_HEADER_SET,
  CUSTOM_HEADER_SET,
  MSFRAGGER_HEADER_SET,
} from "../types";

// ── Filter-controls defaults ────────────────────────────────────────────────
const DEFAULT_FDR = 0.01;
const DEFAULT_BYONIC = 10;
const DEFAULT_PPM = 10;
const DEFAULT_PEPTIDE_LEN = 7;
const DEFAULT_MIN_COUNT = 1;
const DEFAULT_W_DEPTH = 0.4;
const DEFAULT_W_CONFLICT = 0.4;
const DEFAULT_W_BYONIC = 0.2;
const EXPORT_OPTIONS = ["all", "glycan"] as const;

// ── Helper types ────────────────────────────────────────────────────────────

/** Row type for the saved-analyses DataTable */
interface AnalysisRow {
  id: string;
  name: string;
  study_code: string;
  quant_method: string;
  created_at: string;
  params: string; // placeholder for the "Parameter" link column
}

// ── Component ───────────────────────────────────────────────────────────────

export function HomePage() {
  const navigate = useNavigate();

  // ── Upload state ──────────────────────────────────────────────────────────
  const uploadMutation = useUploadDataFile();
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [matchedFormat, setMatchedFormat] = useState<string | null>(null);
  const [matchError, setMatchError] = useState<string | null>(null);

  // ── Condition-assignment state  (sample name → condition string) ───────────
  const [conditions, setConditions] = useState<Record<string, string>>({});

  // ── Filter controls ───────────────────────────────────────────────────────
  const [fdrThreshold, setFdrThreshold] = useState(DEFAULT_FDR);
  const [fdrIsProbability, setFdrIsProbability] = useState(false);
  const [byonicScore, setByonicScore] = useState(DEFAULT_BYONIC);
  const [ppmThreshold, setPpmThreshold] = useState(DEFAULT_PPM);
  const [peptideLength, setPeptideLength] = useState(DEFAULT_PEPTIDE_LEN);
  const [minCount, setMinCount] = useState(DEFAULT_MIN_COUNT);
  const [exportFilter, setExportFilter] =
    useState<(typeof EXPORT_OPTIONS)[number]>("all");
  const [wDepth, setWDepth] = useState(DEFAULT_W_DEPTH);
  const [wConflict, setWConflict] = useState(DEFAULT_W_CONFLICT);
  const [wByonic, setWByonic] = useState(DEFAULT_W_BYONIC);
  const [studyCode, setStudyCode] = useState("");
  const [note, setNote] = useState("");
  const [analysisName, setAnalysisName] = useState("");

  // ── Submission state ──────────────────────────────────────────────────────
  const runAnalysis = useRunAnalysis();
  const [validationError, setValidationError] = useState<string | null>(null);
  const [showColumnSettings, setShowColumnSettings] = useState(false);

  // ── Parameter modal state ────────────────────────────────────────────────
  const [paramsModalData, setParamsModalData] = useState<Record<
    string,
    unknown
  > | null>(null);

  // ── Delete analysis state ───────────────────────────────────────────────
  const deleteAnalysis = useDeleteAnalysis();
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [deleteInput, setDeleteInput] = useState("");

  // ── Column header sets (loaded from backend settings file) ──────────────
  const { data: remoteHeaderSets, isLoading: headerSetsLoading } =
    useHeaderSets();
  const saveHeaderSetsMutation = useSaveHeaderSets();

  const [headerSets, setHeaderSets] = useState<ColumnHeaderSet[]>([
    { ...BYONIC_HEADER_SET },
    { ...MSFRAGGER_HEADER_SET },
    { ...CUSTOM_HEADER_SET },
  ]);
  const [headerSetsSaved, setHeaderSetsSaved] = useState(true);

  // Sync from backend when data arrives
  useEffect(() => {
    if (!remoteHeaderSets || remoteHeaderSets.length === 0) return;
    setHeaderSets(remoteHeaderSets);
    setHeaderSetsSaved(true);
  }, [remoteHeaderSets]);

  const updateHeaderField = useCallback(
    (setIndex: number, field: keyof ColumnHeaderSet, value: string) => {
      setHeaderSets((prev) => {
        const copy = prev.map((hs) => ({ ...hs }));
        (copy[setIndex] as Record<string, string>)[field] = value;
        return copy;
      });
      setHeaderSetsSaved(false);
    },
    [],
  );

  const saveHeaderSets = useCallback(() => {
    saveHeaderSetsMutation.mutate([...headerSets], {
      onSuccess: () => setHeaderSetsSaved(true),
    });
  }, [headerSets, saveHeaderSetsMutation]);

  // Collect non-empty abundance patterns for upload
  const abundancePrefixes = useMemo(() => {
    const prefixes: string[] = [];
    for (const hs of headerSets) {
      if (hs.abundance_columns?.trim()) {
        // Strip wildcard to get the raw prefix/value for backend
        const raw = hs.abundance_columns.trim().replace(/\*/g, "").trim();
        if (raw) prefixes.push(raw);
      }
    }
    return prefixes.length > 0 ? prefixes : undefined;
  }, [headerSets]);

  // ── Saved analyses ────────────────────────────────────────────────────────
  const { data: analyses, isLoading: isLoadingAnalyses } = useAnalysisList();

  // ── Header set matching helper ──────────────────────────────────────────────
  const matchHeaderSets = useCallback(
    (allHeaders: string[]): { matched: string } | { error: string } => {
      const exactFields: (keyof ColumnHeaderSet)[] = [
        "glycan_composition",
        "protein_accessions",
        "position_in_protein",
        "master_protein_descriptions",
        "sequence",
        "modifications",
        "retention_time",
      ];
      const prefixFields: (keyof ColumnHeaderSet)[] = [
        "fdr_prefix",
        "engine_score_prefix",
        "ppm_prefix",
      ];
      const wildcardFields: (keyof ColumnHeaderSet)[] = ["abundance_columns"];

      let bestName = "";
      let bestMatchCount = -1;
      let bestMissing: string[] = [];

      for (const hs of headerSets) {
        const missing: string[] = [];
        let matchCount = 0;
        for (const f of exactFields) {
          const val = hs[f];
          if (!val) continue;
          if (allHeaders.includes(val)) {
            matchCount++;
          } else {
            missing.push(`"${val}" (${f})`);
          }
        }
        for (const f of prefixFields) {
          const val = hs[f];
          if (!val) continue;
          if (allHeaders.some((h) => h.startsWith(val))) {
            matchCount++;
          } else {
            missing.push(`"${val}..." (${f})`);
          }
        }
        for (const f of wildcardFields) {
          const val = hs[f];
          if (!val) continue;
          const hasMatch = (() => {
            if (!val.includes("*")) {
              return allHeaders.includes(val);
            } else if (val.startsWith("*")) {
              const suffix = val.slice(1).trimStart();
              return allHeaders.some((h) => h.endsWith(suffix));
            } else {
              const prefix = val.replace(/\*+$/, "");
              return allHeaders.some((h) => h.startsWith(prefix));
            }
          })();
          if (hasMatch) {
            matchCount++;
          } else {
            missing.push(`"${val}" (${f})`);
          }
        }
        if (missing.length === 0) return { matched: hs.name };
        if (matchCount > bestMatchCount) {
          bestMatchCount = matchCount;
          bestName = hs.name;
          bestMissing = missing;
        }
      }

      return {
        error:
          `No matching column header format found. Closest match: "${bestName}" ` +
          `(${bestMatchCount} columns matched). Missing columns: ${bestMissing.join(", ")}`,
      };
    },
    [headerSets],
  );

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleUpload = useCallback(
    async (file: File) => {
      setMatchedFormat(null);
      setMatchError(null);

      let result: UploadResponse;
      try {
        result = await uploadMutation.mutateAsync({
          file,
          abundancePrefixes,
        });
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? (err instanceof Error ? err.message : "Upload failed");
        setMatchError(msg);
        return;
      }
      setUploadResult(result);

      // Try to match file headers to a known header set
      if (result.all_headers && result.all_headers.length > 0) {
        const matchResult = matchHeaderSets(result.all_headers);
        if ("matched" in matchResult) {
          setMatchedFormat(matchResult.matched);
          // Auto-check "Probability" if the matched header set's FDR prefix contains "prob"
          const matched = headerSets.find(
            (hs) => hs.name === matchResult.matched,
          );
          setFdrIsProbability(
            !!matched?.fdr_prefix &&
              matched.fdr_prefix.toLowerCase().includes("prob"),
          );
        } else {
          setMatchError(matchResult.error);
        }
      }

      // Default analysis name to the file name (without extension)
      const baseName = file.name.replace(/\.[^/.]+$/, "");
      setAnalysisName(baseName);
      // Initialise conditions — default to "1" if only one column
      const initial: Record<string, string> = {};
      const defaultVal = result.columns.length === 1 ? "1" : "";
      result.columns.forEach((col) => {
        initial[col] = defaultVal;
      });
      setConditions(initial);
    },
    [uploadMutation, abundancePrefixes, matchHeaderSets],
  );

  const handleConditionChange = useCallback((sample: string, value: string) => {
    setConditions((prev) => ({ ...prev, [sample]: value }));
  }, []);

  const allConditionsAssigned = useMemo(
    () =>
      uploadResult !== null &&
      uploadResult.columns.length > 0 &&
      uploadResult.columns.every((col) => conditions[col]?.trim() !== ""),
    [uploadResult, conditions],
  );

  const handleSubmit = useCallback(async () => {
    setValidationError(null);

    if (!uploadResult) {
      setValidationError("Please upload a data file first.");
      return;
    }

    if (!analysisName.trim()) {
      setValidationError("Please provide an analysis name.");
      return;
    }

    if (!allConditionsAssigned) {
      setValidationError(
        "Please assign a condition to every sample before submitting.",
      );
      return;
    }

    try {
      const result = await runAnalysis.mutateAsync({
        file_id: uploadResult.file_id,
        name: analysisName.trim(),
        conditions,
        fdr_threshold: fdrThreshold,
        fdr_is_probability: fdrIsProbability,
        byonic_score: byonicScore,
        ppm_threshold: ppmThreshold,
        peptide_length: peptideLength,
        min_count: minCount,
        export_filter: exportFilter,
        abundance_type: "Abundances (Grouped)",
        study_code: studyCode || undefined,
        note: note || undefined,
        w_depth: wDepth,
        w_conflict: wConflict,
        w_byonic: wByonic,
        column_header_sets: headerSets,
      });
      navigate(`/analysis/${result.analysis_id}`);
    } catch {
      // Error is surfaced by react-query; we don't need to re-throw.
    }
  }, [
    uploadResult,
    analysisName,
    allConditionsAssigned,
    runAnalysis,
    conditions,
    fdrThreshold,
    byonicScore,
    ppmThreshold,
    peptideLength,
    minCount,
    exportFilter,
    studyCode,
    note,
    wDepth,
    wConflict,
    wByonic,
    headerSets,
    navigate,
  ]);

  // ── Saved-analyses table columns ──────────────────────────────────────────

  const fetchAndShowParams = useCallback(async (analysisId: string) => {
    try {
      const resp = await import("../api/client").then((m) =>
        m.default.get(`/analysis/${analysisId}/params`),
      );
      setParamsModalData(resp.data as Record<string, unknown>);
    } catch {
      setParamsModalData({ error: "Failed to load parameters." });
    }
  }, []);

  const analysisColumns: Column<AnalysisRow>[] = useMemo(
    () => [
      { key: "id", label: "ID" },
      { key: "name", label: "Name" },
      { key: "study_code", label: "Study Code" },
      { key: "quant_method", label: "Quant Method" },
      {
        key: "params",
        label: "Parameter",
        sortable: false,
        render: (_v, row) => (
          <a
            href="#"
            className="text-blue-600 hover:underline"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              fetchAndShowParams(row.id);
            }}
          >
            Parameter
          </a>
        ),
      },
      {
        key: "created_at",
        label: "Created At",
        render: (v) => {
          if (!v) return "—";
          return new Date(v as string).toLocaleString();
        },
      },
      {
        key: "id",
        label: "",
        sortable: false,
        render: (_v, row) => (
          <button
            className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-200"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteTarget({ id: row.id, name: row.name });
              setDeleteInput("");
            }}
          >
            Delete
          </button>
        ),
      },
    ],
    [fetchAndShowParams],
  );

  const analysisRows: AnalysisRow[] = useMemo(
    () =>
      (analyses ?? []).map((a: AnalysisResponse) => ({
        id: a.id,
        name: a.name,
        study_code: a.study_code ?? "—",
        quant_method: a.quant_method ?? "—",
        params: "",
        created_at: a.created_at,
      })),
    [analyses],
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-8">
      {/* ─── Section 1: File Upload ───────────────────────────────────────── */}
      <section className="rounded-lg bg-white p-6 shadow">
        <div className="mb-4 flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-800">
            Upload Data File
          </h2>
          <button
            type="button"
            onClick={() => setShowColumnSettings((v) => !v)}
            className="rounded-md border border-gray-300 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100"
          >
            {showColumnSettings ? "Hide" : "Column Settings"}
          </button>
        </div>

        {showColumnSettings && (
          <div className="mb-4 overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold text-gray-600">
                    Purpose
                  </th>
                  {headerSets.map((hs) => (
                    <th key={hs.name} className="px-4 py-2 text-left font-semibold text-gray-600">
                      {hs.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(
                  [
                    ["Glycan Composition", "glycan_composition"],
                    ["Protein Accessions", "protein_accessions"],
                    ["Position in Protein", "position_in_protein"],
                    [
                      "Master Protein Descriptions",
                      "master_protein_descriptions",
                    ],
                    ["Sequence", "sequence"],
                    ["Modifications", "modifications"],
                    ["Retention Time", "retention_time"],
                  ] as const
                ).map(([label, field]) => (
                  <tr key={field}>
                    <td
                      className={`px-4 py-2 text-xs ${["glycan_composition", "protein_accessions", "modifications"].includes(field) ? "font-semibold text-gray-700" : "text-gray-500"}`}
                    >
                      {label}
                      {field === "glycan_composition" && (
                        <span className="group relative ml-1 inline-flex cursor-help items-center rounded-full bg-gray-200 px-1 text-[10px] font-bold text-gray-500">
                          ?
                          <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-1 hidden -translate-y-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[11px] font-normal text-white shadow-lg group-hover:block">
                            Format: HexNAc(3)Hex(5) or HexNAc(2)Hex(5) %
                            1216.4229
                            <br />
                            Multiple glycans: separate with &quot;,&quot; or
                            &quot;;&quot;
                            <br />
                            If no header specified, glycan composition will be
                            derived from Modifications column.
                          </span>
                        </span>
                      )}
                      {field === "position_in_protein" && (
                        <span className="group relative ml-1 inline-flex cursor-help items-center rounded-full bg-gray-200 px-1 text-[10px] font-bold text-gray-500">
                          ?
                          <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-1 hidden -translate-y-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[11px] font-normal text-white shadow-lg group-hover:block">
                            When missing, a placeholder column is added with
                            default value 1.
                          </span>
                        </span>
                      )}
                      {field === "modifications" && (
                        <span className="group relative ml-1 inline-flex cursor-help items-center rounded-full bg-gray-200 px-1 text-[10px] font-bold text-gray-500">
                          ?
                          <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-1 hidden -translate-y-1/2 whitespace-pre-line rounded bg-gray-800 px-2 py-1 text-[11px] font-normal text-white shadow-lg group-hover:block">
                            If &quot;Glycan Composition&quot; is empty, glycans
                            are
                            <br />
                            parsed from this column. Supported formats:
                            <br />
                            • Masses: &quot;1234.56; 2345.67&quot; or
                            &quot;1234.56,2345.67&quot;
                            <br />
                            • Embedded: &quot;9N(1079.4017)&quot; or
                            &quot;6C(57.0215),2N(162.0528)&quot;
                            <br />
                            • Compositions: &quot;1xHexNAc(5)Hex(6)Fuc(1)
                            [N1]&quot;
                            <br />
                            <br />
                            Glycosylation site (N/S/T + position) is also
                            <br />
                            extracted from this column, e.g. N10 or 10N.
                            <br />
                            <br />
                            When missing, a placeholder column is added with
                            empty value.
                          </span>
                        </span>
                      )}
                    </td>
                    {headerSets.map((hs, idx) => (
                      <td key={hs.name} className="px-4 py-1">
                        <input
                          type="text"
                          value={hs[field]}
                          onChange={(e) =>
                            updateHeaderField(idx, field, e.target.value)
                          }
                          placeholder="(empty)"
                          className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-blue-400 focus:outline-none"
                        />
                      </td>
                    ))}
                  </tr>
                ))}

                <tr className="bg-gray-50">
                  <td
                    colSpan={4}
                    className="px-4 py-2 text-xs font-semibold uppercase text-gray-500"
                  >
                    Prefix-matched columns
                  </td>
                </tr>

                {(
                  [
                    ["FDR Prefix", "fdr_prefix"],
                    ["Engine Score Prefix", "engine_score_prefix"],
                    ["PPM Prefix", "ppm_prefix"],
                    ["Abundance Columns", "abundance_columns"],
                  ] as const
                ).map(([label, field]) => (
                  <tr key={field}>
                    <td
                      className="px-4 py-2 text-xs text-gray-500"
                    >
                      {label}
                      {field === "engine_score_prefix" && (
                        <span className="group relative ml-1 inline-flex cursor-help items-center rounded-full bg-gray-200 px-1 text-[10px] font-bold text-gray-500">
                          ?
                          <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-1 hidden -translate-y-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[11px] font-normal text-white shadow-lg group-hover:block">
                            When missing, a placeholder column is added with
                            default value 1000.
                          </span>
                        </span>
                      )}
                      {field === "fdr_prefix" && (
                        <span className="group relative ml-1 inline-flex cursor-help items-center rounded-full bg-gray-200 px-1 text-[10px] font-bold text-gray-500">
                          ?
                          <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-1 hidden -translate-y-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[11px] font-normal text-white shadow-lg group-hover:block">
                            When missing, a placeholder column is added with
                            default value 0.
                          </span>
                        </span>
                      )}
                      {field === "ppm_prefix" && (
                        <span className="group relative ml-1 inline-flex cursor-help items-center rounded-full bg-gray-200 px-1 text-[10px] font-bold text-gray-500">
                          ?
                          <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-1 hidden -translate-y-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[11px] font-normal text-white shadow-lg group-hover:block">
                            When missing, a placeholder column is added with
                            default value 0.
                          </span>
                        </span>
                      )}
                      {field === "abundance_columns" && (
                        <span className="group relative ml-1 inline-flex cursor-help items-center rounded-full bg-gray-200 px-1 text-[10px] font-bold text-gray-500">
                          ?
                          <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-1 hidden -translate-y-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[11px] font-normal text-white shadow-lg group-hover:block">
                            Optional. When empty, a placeholder column with
                            value 1 is added for all rows.
                            <br />
                            <br />
                            Use * as wildcard.
                            <br />
                            Abundances (Grouped)* = prefix match
                            <br />
                            * Intensity = suffix match
                            <br />
                            Intensity = exact match
                          </span>
                        </span>
                      )}
                    </td>
                    {headerSets.map((hs, idx) => (
                      <td key={hs.name} className="px-4 py-1">
                        <input
                          type="text"
                          value={hs[field]}
                          onChange={(e) =>
                            updateHeaderField(idx, field, e.target.value)
                          }
                          placeholder="(empty)"
                          className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs focus:border-blue-400 focus:outline-none"
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center gap-3 border-t border-gray-200 bg-gray-50 px-4 py-2">
              <button
                type="button"
                onClick={saveHeaderSets}
                className={`rounded-md px-4 py-1.5 text-xs font-medium text-white shadow-sm ${
                  headerSetsSaved
                    ? "cursor-default bg-gray-400"
                    : "bg-blue-600 hover:bg-blue-700"
                }`}
              >
                {headerSetsSaved ? "Saved" : "Save"}
              </button>
              {!headerSetsSaved && (
                <span className="text-xs text-amber-600">Unsaved changes</span>
              )}
            </div>
          </div>
        )}
        <p className="mb-4 text-sm text-gray-500">
          Upload an <code>.xlsx</code>, <code>.tsv</code>, or <code>.csv</code>{" "}
          file to begin a new analysis. (example file:{" "}
          <a
            href="/api/example-data/example_input_byonic.xlsx"
            download
            className="text-blue-600 underline hover:text-blue-800"
          >
            byonic
          </a>
          ,{" "}
          <a
            href="/api/example-data/example_input_msfragger_psm.tsv"
            download
            className="text-blue-600 underline hover:text-blue-800"
          >
            msfragger_psm
          </a>
          ,{" "}
          <a
            href="/api/example-data/example_input_msfragger_combined_ion.tsv"
            download
            className="text-blue-600 underline hover:text-blue-800"
          >
            msfragger_combined_ion
          </a>
          )
        </p>
        <FileUploadDropzone
          accept=".xlsx,.tsv,.csv"
          onUpload={handleUpload}
          label="Drag & drop your data file here, or click to browse"
        />
        {matchedFormat && (
          <div className="mt-3 rounded-md border border-green-300 bg-green-50 px-4 py-2 text-sm text-green-800">
            ✓ Detected format: <strong>{matchedFormat}</strong>
          </div>
        )}
        {matchError && (
          <div className="mt-3 rounded-md border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800">
            ✗ {matchError}
          </div>
        )}
      </section>

      {/* ─── Section 2: Condition Assignment Table ────────────────────────── */}
      {uploadResult && (
        <section className="rounded-lg bg-white p-6 shadow">
          {/* Analysis Name (mandatory) */}
          <label className="mb-6 block">
            <span className="text-sm font-medium text-gray-700">
              Analysis Name <span className="text-red-500">*</span>
            </span>
            <input
              type="text"
              value={analysisName}
              onChange={(e) => setAnalysisName(e.target.value)}
              placeholder="Enter a name for this analysis"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </label>

          <h2 className="mb-4 text-lg font-semibold text-gray-800">
            Assign Conditions
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            Assign a condition label (e.g.&nbsp;"Control",&nbsp;"Treatment") to
            each abundance column detected in your file.
          </p>

          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-1.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Sample Name
                  </th>
                  <th className="px-4 py-1.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Condition
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {uploadResult.columns.map((col) => (
                  <tr key={col}>
                    <td className="whitespace-nowrap px-4 py-1 text-sm text-gray-700">
                      {col}
                    </td>
                    <td className="px-4 py-1">
                      <input
                        type="text"
                        value={conditions[col] ?? ""}
                        onChange={(e) =>
                          handleConditionChange(col, e.target.value)
                        }
                        placeholder="e.g. Control"
                        className="w-full rounded-md border border-gray-300 px-3 py-1 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ─── Section 3: Filter Controls ───────────────────────────────────── */}
      {uploadResult && (
        <section className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold text-gray-800">
            Filter &amp; Analysis Settings
          </h2>

          <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* FDR-2D threshold */}
            <label className="block">
              <span className="text-sm font-medium text-gray-700">
                FDR Threshold
              </span>
              <input
                type="number"
                step="any"
                value={fdrThreshold}
                onChange={(e) => setFdrThreshold(Number(e.target.value))}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <label className="mt-1 inline-flex items-center gap-1.5 text-xs text-gray-600">
                <input
                  type="checkbox"
                  checked={fdrIsProbability}
                  onChange={(e) => setFdrIsProbability(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span>use Probability</span>
                <span className="group relative ml-0.5 inline-flex cursor-help items-center rounded-full bg-gray-200 px-1 text-[10px] font-bold text-gray-500">
                  ?
                  <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-1 hidden -translate-y-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[11px] font-normal text-white shadow-lg group-hover:block">
                    If checked, will use 1 − ColumnValue for filter
                  </span>
                </span>
              </label>
            </label>

            {/* Engine Score threshold */}
            <label className="block">
              <span className="text-sm font-medium text-gray-700">
                Engine Score Threshold
              </span>
              <input
                type="number"
                step="any"
                value={byonicScore}
                onChange={(e) => setByonicScore(Number(e.target.value))}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </label>

            {/* ppm threshold */}
            <label className="block">
              <span className="text-sm font-medium text-gray-700">
                ppm Threshold
              </span>
              <input
                type="number"
                step="any"
                value={ppmThreshold}
                onChange={(e) => setPpmThreshold(Number(e.target.value))}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </label>

            {/* Peptide length threshold */}
            <label className="block">
              <span className="text-sm font-medium text-gray-700">
                Peptide Length Threshold
              </span>
              <input
                type="number"
                step="1"
                value={peptideLength}
                onChange={(e) => setPeptideLength(Number(e.target.value))}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </label>

            {/* Min count threshold */}
            <label className="block">
              <span className="text-sm font-medium text-gray-700">
                Min Count Threshold
              </span>
              <input
                type="number"
                step="1"
                value={minCount}
                onChange={(e) => setMinCount(Number(e.target.value))}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </label>
          </div>

          {/* Export filter (radio) */}
          <fieldset className="mt-5">
            <legend className="text-sm font-medium text-gray-700">
              Export Filter
            </legend>
            <div className="mt-2 flex items-center gap-6">
              {EXPORT_OPTIONS.map((opt) => (
                <label key={opt} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="exportFilter"
                    value={opt}
                    checked={exportFilter === opt}
                    onChange={() => setExportFilter(opt)}
                    className="h-4 w-4 border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  {opt}
                </label>
              ))}
            </div>
          </fieldset>

          {/* Composite Score Weights */}
          <fieldset className="mt-5">
            <legend className="text-sm font-medium text-gray-700">
              Composite Score Weights
            </legend>
            <p className="mt-1 mb-2 text-xs text-gray-400">
              Weights for depth, RT conflict, and Byonic score in the composite
              validation score (should sum to 1).
            </p>
            <div className="grid grid-cols-3 gap-4">
              <label className="block">
                <span className="text-xs text-gray-600">Depth</span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={wDepth}
                  onChange={(e) => setWDepth(Number(e.target.value))}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-gray-600">RT Conflict</span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={wConflict}
                  onChange={(e) => setWConflict(Number(e.target.value))}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-gray-600">Engine Score</span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={wByonic}
                  onChange={(e) => setWByonic(Number(e.target.value))}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </label>
            </div>
            {Math.abs(wDepth + wConflict + wByonic - 1) > 0.001 && (
              <p className="mt-1 text-xs text-amber-600">
                ⚠ Weights sum to {(wDepth + wConflict + wByonic).toFixed(2)} —
                they should sum to 1.0
              </p>
            )}
          </fieldset>

          {/* Study code & Note */}
          <div className="mt-5 grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-medium text-gray-700">
                Study Code{" "}
                <span className="font-normal text-gray-400">(optional)</span>
              </span>
              <input
                type="text"
                value={studyCode}
                onChange={(e) => setStudyCode(e.target.value)}
                placeholder="e.g. STUDY-2024-001"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium text-gray-700">
                Note{" "}
                <span className="font-normal text-gray-400">(optional)</span>
              </span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                placeholder="Any additional notes…"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </label>
          </div>
        </section>
      )}

      {/* ─── Section 4: Submit Button ─────────────────────────────────────── */}
      {uploadResult && (
        <section className="rounded-lg bg-white p-6 shadow">
          {validationError && (
            <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
              {validationError}
            </p>
          )}

          {runAnalysis.isError && (
            <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
              Analysis failed:{" "}
              {runAnalysis.error?.message ?? "Unknown error. Please try again."}
            </p>
          )}

          {runAnalysis.isPending ? (
            <LoadingSpinner message="Running analysis…" />
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!allConditionsAssigned}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Run Analysis
            </button>
          )}
        </section>
      )}

      {/* ─── Section 5: Saved Analyses Table ──────────────────────────────── */}
      <section className="rounded-lg bg-white p-6 shadow">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">
            Saved Analyses
          </h2>
          {analysisRows.length >= 2 && (
            <Link
              to="/compare"
              className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
            >
              Compare Two Analyses
            </Link>
          )}
        </div>

        {isLoadingAnalyses ? (
          <LoadingSpinner message="Loading analyses…" />
        ) : analysisRows.length === 0 ? (
          <p className="text-sm text-gray-500">No analyses yet.</p>
        ) : (
          <DataTable<AnalysisRow>
            columns={analysisColumns}
            data={analysisRows}
            onRowClick={(row) => navigate(`/analysis/${row.id}`)}
          />
        )}
      </section>

      {/* ─── Parameter Modal ─────────────────────────────────────────────── */}
      {paramsModalData && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setParamsModalData(null)}
        >
          <div
            className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-800">
                Analysis Parameters
              </h3>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600"
                onClick={() => setParamsModalData(null)}
              >
                ✕
              </button>
            </div>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-gray-100">
                {Object.entries(paramsModalData).map(([key, value]) => (
                  <tr key={key}>
                    <td className="py-2 pr-4 font-medium text-gray-600 align-top">
                      {key}
                    </td>
                    <td className="py-2 text-gray-800 break-all">
                      {typeof value === "object" && value !== null
                        ? JSON.stringify(value, null, 2)
                        : String(value ?? "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── Delete Confirmation Modal ────────────────────────────────────── */}
      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setDeleteTarget(null)}
        >
          <div
            className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-2 text-lg font-semibold text-gray-800">
              Delete Analysis
            </h3>
            <p className="mb-4 text-sm text-gray-600">
              This will permanently delete analysis{" "}
              <strong>#{deleteTarget.id}</strong> ({deleteTarget.name}) and all
              associated files.
            </p>
            <p className="mb-2 text-sm text-gray-600">
              Type <strong>DELETE</strong> to confirm:
            </p>
            <input
              type="text"
              value={deleteInput}
              onChange={(e) => setDeleteInput(e.target.value)}
              className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
              placeholder="DELETE"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100"
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleteInput !== "DELETE" || deleteAnalysis.isPending}
                className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-40"
                onClick={() => {
                  deleteAnalysis.mutate(deleteTarget.id, {
                    onSuccess: () => setDeleteTarget(null),
                  });
                }}
              >
                {deleteAnalysis.isPending ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

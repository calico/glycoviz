import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useAnalysis,
  useAnalysisSites,
  useAbundanceData,
  useProteinAbundance,
  useMultiSiteAbundance,
  useFoldChange,
  useFcAvg,
} from "../hooks/useApi";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { DataTable } from "../components/tables/DataTable";
import type { Column } from "../components/tables/DataTable";
import {
  GlycanBarChart,
  GlycanBarChartByReplicate,
} from "../components/charts/GlycanBarChart";
import { VolcanoPlot } from "../components/charts/VolcanoPlot";
import { FoldChangeSubplots } from "../components/charts/FoldChangeSubplots";
import type { SiteRow, FoldChangeResult, FcAvgResult } from "../types";

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Strip the longest common prefix from an array of strings (display only). */
function stripCommonPrefix(names: string[]): string[] {
  if (names.length <= 1) return names;
  let prefix = names[0];
  for (let i = 1; i < names.length; i++) {
    while (!names[i].startsWith(prefix)) {
      prefix = prefix.slice(0, -1);
    }
    if (!prefix) return names;
  }
  // Only strip up to the last separator so labels stay readable
  const sepIdx = Math.max(
    prefix.lastIndexOf(": "),
    prefix.lastIndexOf(" - "),
    prefix.lastIndexOf("_"),
  );
  if (sepIdx < 0) return names; // no separator found — don't strip
  const cutLen = sepIdx + (prefix[sepIdx] === "_" ? 1 : 2);
  return names.map((n) => n.slice(cutLen));
}

// ── Plot control types ──────────────────────────────────────────────────────

type PlotMode = "glycan" | "motif";
type ValueType = "abundance" | "count";
type DisplayType = "absolute" | "percentage";

// ── Filter summary helper ───────────────────────────────────────────────────

function FilterSummary({
  params,
}: {
  params: Record<string, unknown> | null | undefined;
}) {
  if (!params || Object.keys(params).length === 0) {
    return <span className="text-gray-400 italic">No filters applied</span>;
  }

  const items = Object.entries(params).filter(([, v]) => v != null && v !== "");

  return (
    <div className="flex flex-wrap gap-2">
      {items.map(([key, value]) => (
        <span
          key={key}
          className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700"
        >
          {key.replace(/_/g, " ")}: {String(value)}
        </span>
      ))}
    </div>
  );
}

// ── QC stat card ────────────────────────────────────────────────────────────

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
    </div>
  );
}

// ── Toggle button group ─────────────────────────────────────────────────────

function ToggleGroup<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
        {label}
      </span>
      <div className="inline-flex rounded-md shadow-sm">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`px-3 py-1.5 text-sm font-medium first:rounded-l-md last:rounded-r-md border
              ${
                value === opt.value
                  ? "bg-blue-600 text-white border-blue-600 z-10"
                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
              }
              -ml-px first:ml-0 focus:z-10 focus:outline-none focus:ring-2 focus:ring-blue-500`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Sites table columns ─────────────────────────────────────────────────────

function makeSiteColumns(
  analysisId: string,
  refCondition: string,
  compCondition: string,
): Column<SiteRow>[] {
  return [
    { key: "gene", label: "Gene", sortable: true },
    {
      key: "protein",
      label: "Protein",
      sortable: true,
      render: (_value, row) => (
        <Link
          to={`/interact?accession=${encodeURIComponent(row.accession)}&analysisId=${analysisId}&ref=${encodeURIComponent(refCondition)}&comp=${encodeURIComponent(compCondition)}`}
          className="text-blue-600 hover:text-blue-800 hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {row.protein}
        </Link>
      ),
    },
    { key: "site", label: "Site", sortable: true },
    { key: "count", label: "Count", sortable: true },
  ];
}

// ── Main component ──────────────────────────────────────────────────────────

export function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const analysisId = id ?? "";

  // ── Data fetching ───────────────────────────────────────────────────────
  const {
    data: analysis,
    isLoading: analysisLoading,
    error: analysisError,
  } = useAnalysis(analysisId);

  const { data: sites, isLoading: sitesLoading } = useAnalysisSites(analysisId);

  // ── Control state ───────────────────────────────────────────────────────
  const [plotMode, setPlotMode] = useState<PlotMode>("glycan");
  const [valueType, setValueType] = useState<ValueType>("abundance");
  const [displayType, setDisplayType] = useState<DisplayType>("absolute");
  const [refCondition, setRefCondition] = useState<string>("");
  const [compCondition, setCompCondition] = useState<string>("");

  // ── Composite score weight overrides ─────────────────────────────────
  const [wDepth, setWDepth] = useState<number>(0.4);
  const [wConflict, setWConflict] = useState<number>(0.4);
  const [wByonic, setWByonic] = useState<number>(0.2);

  // Initialise weights from the analysis's saved params once loaded
  useEffect(() => {
    const fp = analysis?.filter_params as Record<string, unknown> | undefined;
    if (fp) {
      if (typeof fp.w_depth === "number") setWDepth(fp.w_depth);
      if (typeof fp.w_conflict === "number") setWConflict(fp.w_conflict);
      if (typeof fp.w_byonic === "number") setWByonic(fp.w_byonic);
    }
  }, [analysis?.filter_params]);
  const [selectedSite, setSelectedSite] = useState<SiteRow | null>(null);
  const [checkedSites, setCheckedSites] = useState<SiteRow[]>([]);
  const [showCheckedPlots, setShowCheckedPlots] = useState(false);
  const [highlightedGlycan, setHighlightedGlycan] = useState<string | null>(
    null,
  );

  const siteColumns = useMemo(
    () => makeSiteColumns(analysisId, refCondition, compCondition),
    [analysisId, refCondition, compCondition],
  );

  // ── Abundance data ──────────────────────────────────────────────────────
  const abundanceParams = useMemo(
    () => ({ mode: plotMode, metric: valueType }),
    [plotMode, valueType],
  );

  const scoreWeights = useMemo(
    () => ({ w_depth: wDepth, w_conflict: wConflict, w_byonic: wByonic }),
    [wDepth, wConflict, wByonic],
  );

  const { data: globalAbundance } = useAbundanceData(
    analysisId,
    abundanceParams,
  );

  const { data: proteinAbundanceBySeq } = useProteinAbundance(
    analysisId,
    selectedSite?.accession ?? null,
    selectedSite?.site ?? null,
    abundanceParams,
    scoreWeights,
  );

  // Sequence selector for per-protein plots
  const sequenceKeys = useMemo(
    () => (proteinAbundanceBySeq ? Object.keys(proteinAbundanceBySeq) : []),
    [proteinAbundanceBySeq],
  );
  const [selectedSequence, setSelectedSequence] = useState<string>("");

  // Auto-select first sequence when data changes
  useEffect(() => {
    if (sequenceKeys.length > 0 && !sequenceKeys.includes(selectedSequence)) {
      setSelectedSequence(sequenceKeys[0]);
    }
  }, [sequenceKeys, selectedSequence]);

  const proteinAbundance = useMemo(
    () =>
      proteinAbundanceBySeq && selectedSequence !== undefined
        ? (proteinAbundanceBySeq[selectedSequence] ?? null)
        : null,
    [proteinAbundanceBySeq, selectedSequence],
  );

  const multiSiteQuerySites = useMemo(
    () =>
      showCheckedPlots
        ? checkedSites.map((s) => ({ accession: s.accession, site: s.site }))
        : [],
    [showCheckedPlots, checkedSites],
  );

  const { data: multiSiteAbundance } = useMultiSiteAbundance(
    analysisId,
    multiSiteQuerySites,
    abundanceParams,
    scoreWeights,
  );

  // ── Fold change ─────────────────────────────────────────────────────────
  const foldChangeMutation = useFoldChange();
  const fcAvgMutation = useFcAvg();
  const [volcanoData, setVolcanoData] = useState<FoldChangeResult | null>(null);
  const [fcAvgData, setFcAvgData] = useState<FcAvgResult | null>(null);

  const conditions = analysis?.conditions ?? [];

  // Auto-set default conditions when they load
  useMemo(() => {
    if (conditions.length >= 2 && !refCondition && !compCondition) {
      setRefCondition(conditions[0]);
      setCompCondition(conditions[1]);
    }
  }, [conditions, refCondition, compCondition]);

  // Auto-compute fold change + fc-avg whenever conditions change
  useEffect(() => {
    if (
      !analysisId ||
      !refCondition ||
      !compCondition ||
      refCondition === compCondition
    ) {
      setVolcanoData(null);
      setFcAvgData(null);
      return;
    }

    const params = {
      analysis_id: analysisId,
      reference_condition: refCondition,
      comparison_condition: compCondition,
    };

    foldChangeMutation.mutate(params, {
      onSuccess: (result) => {
        setVolcanoData(result);
      },
    });

    fcAvgMutation.mutate(params, {
      onSuccess: (result) => {
        setFcAvgData(result);
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId, refCondition, compCondition]);

  // ── Row click handler ───────────────────────────────────────────────────
  const handleSiteClick = useCallback((row: SiteRow) => {
    setSelectedSite(row);
    setShowCheckedPlots(false);
    setHighlightedGlycan(null);
  }, []);

  const handleSelectionChange = useCallback((selected: SiteRow[]) => {
    setCheckedSites(selected);
  }, []);

  const handleShowCheckedPlots = useCallback(() => {
    setSelectedSite(null);
    setShowCheckedPlots(true);
  }, []);

  // ── Volcano point click → highlight in chart ───────────────────────────
  const handleVolcanoPointClick = useCallback((glycan: string) => {
    setHighlightedGlycan(glycan);
  }, []);

  // ── Loading / error states ─────────────────────────────────────────────
  if (analysisLoading) {
    return <LoadingSpinner message="Loading analysis…" size="lg" />;
  }

  if (analysisError || !analysis) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-red-700 font-medium">Failed to load analysis</p>
        <p className="mt-1 text-sm text-red-500">
          {analysisError instanceof Error
            ? analysisError.message
            : "Analysis not found"}
        </p>
      </div>
    );
  }

  const qc = analysis.qc_stats;

  return (
    <div className="space-y-6">
      {/* ─── Section 1: Results Header ──────────────────────────────────── */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {analysis.name}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
              {analysis.study_code && (
                <span>
                  Study:{" "}
                  <span className="font-medium text-gray-700">
                    {analysis.study_code}
                  </span>
                </span>
              )}
              <span>
                Created:{" "}
                <time className="font-medium text-gray-700">
                  {new Date(analysis.created_at).toLocaleDateString()}
                </time>
              </span>
              {analysis.quant_method && (
                <span>
                  Method:{" "}
                  <span className="font-medium text-gray-700">
                    {analysis.quant_method}
                  </span>
                </span>
              )}
            </div>
          </div>

          {/* Export buttons */}
          <div className="flex shrink-0 gap-2">
            <a
              href={`/heatmap?analysisId=${analysisId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
              View Heatmap
            </a>
            <a
              href={`/api/export/${analysisId}/results`}
              className="inline-flex items-center gap-1.5 rounded-md bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-gray-300 hover:bg-gray-50"
              download
            >
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12m0 0l-4-4m4 4l4-4"
                />
              </svg>
              Export Results CSV
            </a>
            <a
              href={`/api/export/${analysisId}/zip`}
              className="inline-flex items-center gap-1.5 rounded-md bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-gray-300 hover:bg-gray-50"
              download
            >
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"
                />
              </svg>
              Export All (ZIP)
            </a>
          </div>
        </div>

        {/* Filter summary */}
        <div className="mt-4 border-t border-gray-100 pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500">
            Filters
          </p>
          <FilterSummary params={analysis.filter_params} />
        </div>

        {/* QC statistics */}
        {qc && (
          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-gray-100 pt-4 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Proteins" value={qc.total_proteins} />
            <StatCard label="Peptides" value={qc.total_peptides} />
            <StatCard label="Glycopeptides" value={qc.total_glycopeptides} />
            <StatCard label="Unique Glycans" value={qc.unique_glycans} />
            <StatCard label="Sites" value={qc.total_sites} />
          </div>
        )}
      </div>

      {/* ─── Section 2: Control Bar ─────────────────────────────────────── */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-4">
          {/* Condition selectors */}
          <div className="flex flex-wrap gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Reference
              </span>
              <select
                value={refCondition}
                onChange={(e) => setRefCondition(e.target.value)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Select…</option>
                {conditions.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Comparison
              </span>
              <select
                value={compCondition}
                onChange={(e) => setCompCondition(e.target.value)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Select…</option>
                {conditions.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Divider */}
          <div className="hidden h-8 w-px bg-gray-200 lg:block" />

          {/* Plot mode toggles */}
          <div className="flex flex-wrap gap-4">
            <ToggleGroup
              label="Type"
              options={[
                { value: "glycan" as PlotMode, label: "Glycan" },
                { value: "motif" as PlotMode, label: "Motif" },
              ]}
              value={plotMode}
              onChange={setPlotMode}
            />
            <ToggleGroup
              label="Metric"
              options={[
                { value: "abundance" as ValueType, label: "Abundance" },
                { value: "count" as ValueType, label: "Count" },
              ]}
              value={valueType}
              onChange={setValueType}
            />
            <ToggleGroup
              label="Scale"
              options={[
                { value: "absolute" as DisplayType, label: "Absolute" },
                { value: "percentage" as DisplayType, label: "%" },
              ]}
              value={displayType}
              onChange={setDisplayType}
            />
          </div>
        </div>
      </div>

      {/* ─── Section 3: Global Plots (full width, above table) ──────────── */}
      <div className="space-y-6">
        {/* Bar chart by replicate — global */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold text-gray-900">
            {`Global ${plotMode === "glycan" ? "Glycan" : "Motif"} ${valueType === "abundance" ? "Abundance" : "Count"}`}{" "}
            (by Replicate)
          </h2>

          {globalAbundance ? (
            <GlycanBarChartByReplicate
              data={globalAbundance.data}
              conditionNames={globalAbundance.condition_names}
              colNames={stripCommonPrefix(globalAbundance.sample_names)}
              mode={plotMode}
              valueType={valueType}
              displayType={displayType}
            />
          ) : (
            <div className="flex items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 py-16">
              <p className="text-sm text-gray-400">Loading abundance data…</p>
            </div>
          )}
        </div>

        {/* Bar chart by condition — global */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold text-gray-900">
            {`Global ${plotMode === "glycan" ? "Glycan" : "Motif"} ${valueType === "abundance" ? "Abundance" : "Count"}`}{" "}
            (by Condition)
          </h2>

          {globalAbundance ? (
            <GlycanBarChart
              data={globalAbundance.data}
              conditionNames={globalAbundance.condition_names}
              colNames={stripCommonPrefix(globalAbundance.sample_names)}
              mode={plotMode}
              valueType={valueType}
              displayType={displayType}
            />
          ) : (
            <div className="flex items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 py-16">
              <p className="text-sm text-gray-400">Loading abundance data…</p>
            </div>
          )}
        </div>

        {/* Volcano plot — global */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          {foldChangeMutation.isPending ? (
            <LoadingSpinner message="Computing fold changes…" />
          ) : volcanoData ? (
            <VolcanoPlot
              glycanList={volcanoData.glycan_list}
              fc={volcanoData.fc}
              pValue={volcanoData.p_value}
              referenceCondition={refCondition}
              comparisonCondition={compCondition}
              highlightedPoint={highlightedGlycan ?? undefined}
              onPointClick={handleVolcanoPointClick}
            />
          ) : (
            <div className="flex items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 py-16">
              <p className="text-sm text-gray-400">
                Select reference and comparison conditions
              </p>
            </div>
          )}

          {foldChangeMutation.isError && (
            <p className="mt-2 text-sm text-red-600">
              Error:{" "}
              {foldChangeMutation.error?.message ??
                "Fold change computation failed"}
            </p>
          )}
        </div>

        {/* Fold Change Subplots — only shown when protein-level FC data exists */}
        {fcAvgData?.has_protein_data && (
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <FoldChangeSubplots
              glycanList={fcAvgData.glycan_list}
              mean={fcAvgData.mean}
              proteinMean={fcAvgData.protein_mean}
              meanNorm={fcAvgData.mean_norm}
              pValue={fcAvgData.p_value}
              referenceCondition={refCondition}
              comparisonCondition={compCondition}
            />
          </div>
        )}
      </div>

      {/* ─── Section 4: Sites Table + Per-protein charts ────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_3fr]">
        {/* Left: Sites Table */}
        <div className="min-w-0 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-900">
              Glycosylation Sites
            </h2>
            <div className="flex items-center gap-1.5 text-[10px] text-gray-400">
              <span className="font-medium uppercase tracking-wider cursor-help" title="Composite validation score = D × Depth + RT × RT Conflict + ES × Engine Score. Set a weight to 0 to ignore that metric. Weights should sum to 1.">Weights</span>
              <label className="flex items-center gap-0.5" title="Depth percentile weight">
                <span>D</span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={wDepth}
                  onChange={(e) => setWDepth(Number(e.target.value))}
                  className="w-11 rounded border border-gray-300 px-1 py-0.5 text-[11px] focus:border-blue-500 focus:outline-none"
                />
              </label>
              <label className="flex items-center gap-0.5" title="RT conflict percentile weight">
                <span>RT</span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={wConflict}
                  onChange={(e) => setWConflict(Number(e.target.value))}
                  className="w-11 rounded border border-gray-300 px-1 py-0.5 text-[11px] focus:border-blue-500 focus:outline-none"
                />
              </label>
              <label className="flex items-center gap-0.5" title="Engine score percentile weight">
                <span>ES</span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={wByonic}
                  onChange={(e) => setWByonic(Number(e.target.value))}
                  className="w-11 rounded border border-gray-300 px-1 py-0.5 text-[11px] focus:border-blue-500 focus:outline-none"
                />
              </label>
            </div>
          </div>

          {sitesLoading ? (
            <LoadingSpinner message="Loading sites…" />
          ) : (
            <div className="max-h-[600px] overflow-y-auto">
              <DataTable<SiteRow>
                columns={siteColumns}
                data={sites ?? []}
                selectable
                onRowClick={handleSiteClick}
                onSelectionChange={handleSelectionChange}
                exportFilename={`${analysis.name}_sites.csv`}
              />
            </div>
          )}

          {checkedSites.length > 0 && (
            <button
              type="button"
              onClick={handleShowCheckedPlots}
              className="mt-3 w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Display figures for all checked rows ({checkedSites.length})
            </button>
          )}

          {selectedSite && (
            <div className="mt-3 rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-700">
              Viewing:{" "}
              <span className="font-medium">
                {selectedSite.protein} – {selectedSite.site}
              </span>
              <button
                type="button"
                onClick={() => setSelectedSite(null)}
                className="ml-2 text-blue-500 hover:text-blue-700 underline"
              >
                Clear
              </button>
            </div>
          )}
        </div>

        {/* Right: Per-protein charts (only shown when a site is selected) */}
        {selectedSite && (
          <div className="min-w-0 space-y-6">
            {/* Sequence selector */}
            {sequenceKeys.length > 1 && (
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700">
                  Peptide:
                </label>
                <select
                  value={selectedSequence}
                  onChange={(e) => setSelectedSequence(e.target.value)}
                  className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  {sequenceKeys.map((seq) => (
                    <option key={seq} value={seq}>
                      {seq || "(unknown)"}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {/* Per-protein bar chart by replicate */}
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-gray-900">
                {selectedSite.protein} – {selectedSite.site} (by Replicate)
              </h2>

              {proteinAbundance ? (
                <GlycanBarChartByReplicate
                  data={proteinAbundance.data}
                  conditionNames={proteinAbundance.condition_names}
                  colNames={stripCommonPrefix(proteinAbundance.sample_names)}
                  mode={plotMode}
                  valueType={valueType}
                  displayType={displayType}
                  compositeScores={proteinAbundance.composite_scores}
                  compact
                />
              ) : (
                <LoadingSpinner message="Loading protein data…" />
              )}
            </div>

            {/* Per-protein bar chart by condition */}
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-gray-900">
                {selectedSite.protein} – {selectedSite.site} (by Condition)
              </h2>

              {proteinAbundance ? (
                <GlycanBarChart
                  data={proteinAbundance.data}
                  conditionNames={proteinAbundance.condition_names}
                  colNames={stripCommonPrefix(proteinAbundance.sample_names)}
                  mode={plotMode}
                  valueType={valueType}
                  displayType={displayType}
                  compositeScores={proteinAbundance.composite_scores}
                  compact
                />
              ) : (
                <LoadingSpinner message="Loading protein data…" />
              )}
            </div>
          </div>
        )}

        {/* Right: Combined charts for all checked rows */}
        {showCheckedPlots && !selectedSite && (
          <div className="min-w-0 space-y-6">
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-gray-900">
                Combined Sites ({checkedSites.length} selected) — by Replicate
              </h2>

              {multiSiteAbundance ? (
                <GlycanBarChartByReplicate
                  data={multiSiteAbundance.data}
                  conditionNames={multiSiteAbundance.condition_names}
                  colNames={stripCommonPrefix(multiSiteAbundance.sample_names)}
                  mode={plotMode}
                  valueType={valueType}
                  displayType={displayType}
                  compositeScores={multiSiteAbundance.composite_scores}
                  compact
                />
              ) : (
                <LoadingSpinner message="Loading combined data…" />
              )}
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-gray-900">
                Combined Sites ({checkedSites.length} selected) — by Condition
              </h2>

              {multiSiteAbundance ? (
                <GlycanBarChart
                  data={multiSiteAbundance.data}
                  conditionNames={multiSiteAbundance.condition_names}
                  colNames={stripCommonPrefix(multiSiteAbundance.sample_names)}
                  mode={plotMode}
                  valueType={valueType}
                  displayType={displayType}
                  compositeScores={multiSiteAbundance.composite_scores}
                  compact
                />
              ) : (
                <LoadingSpinner message="Loading combined data…" />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

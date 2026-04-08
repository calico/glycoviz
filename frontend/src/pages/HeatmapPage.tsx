import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useCluster, useAnalysis } from "../hooks/useApi";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { HeatmapChart } from "../components/charts/HeatmapChart";

type DistanceMetric = "euclidean" | "manhattan" | "maximum" | "minkowski";
type LinkageMethod = "complete" | "single" | "average";

export function HeatmapPage() {
  const [searchParams] = useSearchParams();
  const analysisId = searchParams.get("analysisId") ?? "";

  const { data: analysis } = useAnalysis(analysisId);

  // ── Clustering controls state ──────────────────────────────────
  const [distance, setDistance] = useState<DistanceMetric>("euclidean");
  const [linkage, setLinkage] = useState<LinkageMethod>("complete");
  const [clusterByRow, setClusterByRow] = useState(true);
  const [clusterByColumn, setClusterByColumn] = useState(true);
  const [useKMeans, setUseKMeans] = useState(false);
  const [kClusters, setKClusters] = useState(3);
  const [clrTransform, setClrTransform] = useState(true);
  const [zScore, setZScore] = useState(false);
  const [foldChangeFilter, setFoldChangeFilter] = useState(true);
  const [foldChangeValue, setFoldChangeValue] = useState(4);
  const [orderByCondition, setOrderByCondition] = useState(false);

  const clusterMutation = useCluster();

  // Logic constraints matching legacy JS:
  // - If fold change filter is on, CLR must be on
  // - If CLR is off, fold change filter and z-score are forced off
  // - If z-score is on, CLR is forced on
  const handleClrChange = (checked: boolean) => {
    setClrTransform(checked);
    if (!checked) {
      setZScore(false);
      setFoldChangeFilter(false);
    }
  };
  const handleZScoreChange = (checked: boolean) => {
    setZScore(checked);
    if (checked) setClrTransform(true);
  };
  const handleFoldChangeFilterChange = (checked: boolean) => {
    setFoldChangeFilter(checked);
    if (checked) setClrTransform(true);
  };

  const handleGenerate = () => {
    if (!analysisId) return;
    clusterMutation.mutate({
      analysis_id: Number(analysisId),
      distance_metric: distance,
      linkage_method: linkage,
      cluster_by_row: clusterByRow,
      cluster_by_column: clusterByColumn,
      use_kmeans: useKMeans,
      k_clusters: useKMeans ? kClusters : undefined,
      clr_transform: clrTransform,
      zscore_transform: zScore,
      meaningful_change_cutoff: foldChangeFilter ? foldChangeValue : 0,
      order_by_condition: orderByCondition,
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <a
          href={`/analysis/${analysisId}`}
          className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
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
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to Analysis
        </a>
        <h1 className="text-2xl font-bold text-gray-900">
          Heatmap{analysis?.name ? ` — ${analysis.name}` : ""}
        </h1>
        {analysisId && (
          <span className="text-sm text-gray-500 font-mono">#{analysisId}</span>
        )}
      </div>

      {/* ── Controls panel (top, horizontal) ──────────────────────── */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-wrap items-end gap-4">
          {/* Cluster by */}
          <div>
            <span className="block text-xs font-medium text-gray-500 mb-1">
              Cluster by
            </span>
            <div className="flex items-center gap-3">
              <label className="inline-flex items-center gap-1.5 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={clusterByRow}
                  onChange={(e) => setClusterByRow(e.target.checked)}
                  disabled={useKMeans}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
                />
                Rows
              </label>
              <label className="inline-flex items-center gap-1.5 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={clusterByColumn}
                  onChange={(e) => setClusterByColumn(e.target.checked)}
                  disabled={useKMeans}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
                />
                Columns
              </label>
            </div>
          </div>

          <div className="w-px h-8 bg-gray-200" />

          {/* Distance */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Distance
            </label>
            <select
              value={distance}
              onChange={(e) => setDistance(e.target.value as DistanceMetric)}
              className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="euclidean">Euclidean</option>
              <option value="manhattan">Manhattan</option>
              <option value="maximum">Maximum</option>
              <option value="minkowski">Minkowski</option>
            </select>
          </div>

          {/* Linkage */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Linkage
            </label>
            <select
              value={linkage}
              onChange={(e) => setLinkage(e.target.value as LinkageMethod)}
              className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="complete">Complete</option>
              <option value="single">Single</option>
              <option value="average">Average</option>
            </select>
          </div>

          <div className="w-px h-8 bg-gray-200" />

          {/* K-Means */}
          <div className="flex items-center gap-2">
            <label className="inline-flex items-center gap-1.5 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={useKMeans}
                onChange={(e) => setUseKMeans(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
              />
              K-Means
            </label>
            {useKMeans && (
              <input
                type="number"
                min={2}
                max={20}
                value={kClusters}
                onChange={(e) => setKClusters(Number(e.target.value))}
                className="w-16 rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
            )}
          </div>

          <div className="w-px h-8 bg-gray-200" />

          {/* Transforms */}
          <div className="flex items-center gap-3">
            <label
              className="inline-flex items-center gap-1.5 text-sm text-gray-700"
              title="Centered Log Ratio — transforms proportions into log-ratio space centered around the geometric mean of each row."
            >
              <input
                type="checkbox"
                checked={clrTransform}
                onChange={(e) => handleClrChange(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
              />
              CLR
            </label>
            <label
              className="inline-flex items-center gap-1.5 text-sm text-gray-700"
              title="Per row, keeps rows where max |CLR value| > log(threshold). Applied after CLR, before Z-score."
            >
              <input
                type="checkbox"
                checked={foldChangeFilter}
                onChange={(e) => handleFoldChangeFilterChange(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
              />
              Fold Change ≥
            </label>
            {foldChangeFilter && (
              <input
                type="number"
                min={1}
                max={100}
                value={foldChangeValue}
                onChange={(e) => setFoldChangeValue(Number(e.target.value))}
                className="w-16 rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
            )}
            <label className="inline-flex items-center gap-1.5 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={zScore}
                onChange={(e) => handleZScoreChange(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
              />
              Z-score
            </label>
            <label className="inline-flex items-center gap-1.5 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={orderByCondition}
                onChange={(e) => setOrderByCondition(e.target.checked)}
                disabled={clusterByColumn}
                className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
              />
              Order by condition
            </label>
          </div>

          <div className="w-px h-8 bg-gray-200" />

          {/* Generate button */}
          <button
            type="button"
            onClick={handleGenerate}
            disabled={!analysisId || clusterMutation.isPending}
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {clusterMutation.isPending ? "Computing…" : "Generate Heatmap"}
          </button>

          {clusterMutation.isError && (
            <p className="text-xs text-red-600 self-center">
              {clusterMutation.error.message}
            </p>
          )}
        </div>
      </div>

      {/* ── Heatmap area (full width below) ──────────────────────── */}
      <div className="bg-white rounded-lg shadow p-4 min-h-[800px]">
        {clusterMutation.isPending && (
          <div className="flex items-center justify-center h-[500px]">
            <LoadingSpinner message="Clustering data…" size="lg" />
          </div>
        )}

        {clusterMutation.data && !clusterMutation.isPending && (
          <>
            <p className="text-sm text-gray-600 mb-2">
              Glycopeptides in Heatmap:{" "}
              <span className="font-semibold">
                {clusterMutation.data.heatmap_count}
              </span>{" "}
              /{" "}
              <span className="font-semibold">
                {clusterMutation.data.total_quantified}
              </span>{" "}
              total quantified
            </p>
            <HeatmapChart
              data={clusterMutation.data.heatmap_data}
              rowLabels={clusterMutation.data.row_labels}
              colLabels={clusterMutation.data.col_labels}
              rowDendrogram={clusterMutation.data.row_dendrogram}
              colDendrogram={clusterMutation.data.col_dendrogram}
              zmid={clusterMutation.data.zmid}
              colorbarTitle={clusterMutation.data.colorbar_title}
            />
          </>
        )}

        {!clusterMutation.data && !clusterMutation.isPending && (
          <div className="flex items-center justify-center h-[500px]">
            <p className="text-gray-400 text-sm text-center">
              Configure parameters and click <strong>Generate Heatmap</strong>{" "}
              to visualise the clustered data.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

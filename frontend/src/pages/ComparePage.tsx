import { useCallback, useMemo, useState } from "react";
import api from "../api/client";
import { useSearchParams } from "react-router-dom";
import {
  useAnalysis,
  useAnalysisSites,
  useAnalysisList,
  useAbundanceData,
  useProteinAbundance,
} from "../hooks/useApi";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { DataTable } from "../components/tables/DataTable";
import type { Column } from "../components/tables/DataTable";
import type { QcStats, AnalysisResponse } from "../types";

// ── QC comparison row ──────────────────────────────────────────────────────

interface QcRow {
  metric: string;
  analysis1: number | string;
  analysis2: number | string;
}

const QC_LABELS: [keyof QcStats, string][] = [
  ["total_proteins", "Proteins"],
  ["total_peptides", "Peptides"],
  ["total_glycopeptides", "Glycopeptides"],
  ["unique_glycans", "Unique Glycans"],
  ["total_sites", "Sites"],
];

const qcColumns: Column<QcRow>[] = [
  { key: "metric", label: "Metric", sortable: false },
  { key: "analysis1", label: "Analysis 1", sortable: false },
  { key: "analysis2", label: "Analysis 2", sortable: false },
];

// ── Glycan comparison row ──────────────────────────────────────────────────

interface GlycanCompareRow {
  glycan: string;
  in1: string;
  in2: string;
}

const glycanColumns: Column<GlycanCompareRow>[] = [
  { key: "glycan", label: "Glycan", sortable: true },
  { key: "in1", label: "Analysis 1", sortable: true },
  { key: "in2", label: "Analysis 2", sortable: true },
];

// ── Site comparison row ────────────────────────────────────────────────────

interface SiteCompareRow {
  gene: string;
  protein: string;
  accession: string;
  site: string;
  count1: number;
  count2: number;
}

const siteColumns: Column<SiteCompareRow>[] = [
  { key: "gene", label: "Gene", sortable: true },
  { key: "protein", label: "Protein", sortable: true },
  { key: "site", label: "Site", sortable: true },
  { key: "count1", label: "Analysis 1 Count", sortable: true },
  { key: "count2", label: "Analysis 2 Count", sortable: true },
];

// ── Main component ─────────────────────────────────────────────────────────

export function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selA1, setSelA1] = useState(searchParams.get("a1") ?? "");
  const [selA2, setSelA2] = useState(searchParams.get("a2") ?? "");
  const [selectedSite, setSelectedSite] = useState<SiteCompareRow | null>(null);
  const [showGlycans, setShowGlycans] = useState(false);
  const [paramsModalData, setParamsModalData] = useState<Record<string, unknown> | null>(null);

  const fetchAndShowParams = useCallback(async (analysisId: string) => {
    try {
      const resp = await api.get(`/analysis/${analysisId}/params`);
      setParamsModalData(resp.data as Record<string, unknown>);
    } catch {
      setParamsModalData({ error: "Failed to load parameters." });
    }
  }, []);

  const id1 = searchParams.get("a1") ?? "";
  const id2 = searchParams.get("a2") ?? "";

  const { data: analyses, isLoading: listLoading } = useAnalysisList();
  const { data: analysis1, isLoading: loading1 } = useAnalysis(id1);
  const { data: analysis2, isLoading: loading2 } = useAnalysis(id2);
  const { data: sites1, isLoading: sitesLoading1 } = useAnalysisSites(id1);
  const { data: sites2, isLoading: sitesLoading2 } = useAnalysisSites(id2);

  // Global glycan lists from abundance data
  const abundanceParams = useMemo(
    () => ({ mode: "glycan", metric: "abundance" }),
    [],
  );
  const { data: abd1 } = useAbundanceData(id1, abundanceParams);
  const { data: abd2 } = useAbundanceData(id2, abundanceParams);

  const isLoading = loading1 || loading2 || sitesLoading1 || sitesLoading2;

  const handleCompare = () => {
    if (selA1 && selA2 && selA1 !== selA2) {
      setSearchParams({ a1: selA1, a2: selA2 });
      setSelectedSite(null);
    }
  };

  // Build QC comparison rows
  const qcRows = useMemo<QcRow[]>(() => {
    const qc1 = analysis1?.qc_stats;
    const qc2 = analysis2?.qc_stats;
    const rows: QcRow[] = QC_LABELS.map(([key, label]) => ({
      metric: label,
      analysis1: qc1?.[key] ?? "—",
      analysis2: qc2?.[key] ?? "—",
    }));
    rows.push({
      metric: "Parameters",
      analysis1: "__params_link_1__",
      analysis2: "__params_link_2__",
    });
    return rows;
  }, [analysis1, analysis2]);

  // Build global glycan comparison rows
  const glycanRows = useMemo<GlycanCompareRow[]>(() => {
    const glycans1 = abd1 ? Object.keys(abd1.data) : [];
    const glycans2 = abd2 ? Object.keys(abd2.data) : [];
    const all = new Set([...glycans1, ...glycans2]);
    const set1 = new Set(glycans1);
    const set2 = new Set(glycans2);
    return [...all]
      .sort()
      .map((g) => ({
        glycan: g,
        in1: set1.has(g) ? "\u2713" : "",
        in2: set2.has(g) ? "\u2713" : "",
      }));
  }, [abd1, abd2]);

  // Build site comparison rows (union of both analyses)
  const siteRows = useMemo<SiteCompareRow[]>(() => {
    const map = new Map<string, SiteCompareRow>();

    for (const s of sites1 ?? []) {
      const key = `${s.accession}---${s.site}`;
      map.set(key, {
        gene: s.gene,
        protein: s.protein,
        accession: s.accession,
        site: s.site,
        count1: s.count,
        count2: 0,
      });
    }

    for (const s of sites2 ?? []) {
      const key = `${s.accession}---${s.site}`;
      const existing = map.get(key);
      if (existing) {
        existing.count2 = s.count;
      } else {
        map.set(key, {
          gene: s.gene,
          protein: s.protein,
          accession: s.accession,
          site: s.site,
          count1: 0,
          count2: s.count,
        });
      }
    }

    return [...map.values()];
  }, [sites1, sites2]);

  // Update column headers with analysis names
  const name1 = analysis1?.name ?? "Analysis 1";
  const name2 = analysis2?.name ?? "Analysis 2";

  const namedQcColumns = useMemo<Column<QcRow>[]>(
    () =>
      qcColumns.map((col) => {
        if (col.key === "analysis1")
          return {
            ...col,
            label: `#${id1}`,
            render: (v: QcRow[keyof QcRow]) =>
              v === "__params_link_1__" ? (
                <a
                  href="#"
                  className="text-blue-600 hover:underline"
                  onClick={(e) => {
                    e.preventDefault();
                    fetchAndShowParams(id1);
                  }}
                >
                  View
                </a>
              ) : (
                String(v ?? "")
              ),
          };
        if (col.key === "analysis2")
          return {
            ...col,
            label: `#${id2}`,
            render: (v: QcRow[keyof QcRow]) =>
              v === "__params_link_2__" ? (
                <a
                  href="#"
                  className="text-blue-600 hover:underline"
                  onClick={(e) => {
                    e.preventDefault();
                    fetchAndShowParams(id2);
                  }}
                >
                  View
                </a>
              ) : (
                String(v ?? "")
              ),
          };
        return col;
      }),
    [id1, id2],
  );

  const namedGlycanColumns = useMemo<Column<GlycanCompareRow>[]>(
    () =>
      glycanColumns.map((col) => {
        if (col.key === "in1") return { ...col, label: `#${id1}` };
        if (col.key === "in2") return { ...col, label: `#${id2}` };
        return col;
      }),
    [id1, id2],
  );

  const namedSiteColumns = useMemo<Column<SiteCompareRow>[]>(
    () =>
      siteColumns.map((col) => {
        if (col.key === "count1") return { ...col, label: `#${id1} Count` };
        if (col.key === "count2") return { ...col, label: `#${id2} Count` };
        return col;
      }),
    [id1, id2],
  );

  const handleSiteClick = useCallback((row: SiteCompareRow) => {
    setSelectedSite((prev) =>
      prev?.accession === row.accession && prev?.site === row.site ? null : row,
    );
  }, []);

  // Per-site glycan comparison via protein abundance endpoint
  const siteAbdParams = useMemo(
    () => ({ mode: "glycan" as const, metric: "abundance" as const }),
    [],
  );
  const { data: siteAbd1 } = useProteinAbundance(
    id1,
    selectedSite?.accession ?? null,
    selectedSite?.site ?? null,
    siteAbdParams,
  );
  const { data: siteAbd2 } = useProteinAbundance(
    id2,
    selectedSite?.accession ?? null,
    selectedSite?.site ?? null,
    siteAbdParams,
  );

  const siteGlycanRows = useMemo<GlycanCompareRow[]>(() => {
    if (!selectedSite || !siteAbd1 || !siteAbd2) return [];
    // Each response is keyed by sequence; collect all glycan names
    const glycans1 = new Set<string>();
    const glycans2 = new Set<string>();
    for (const seq of Object.values(siteAbd1) as Array<{ data: Record<string, unknown> }>) {
      for (const g of Object.keys(seq.data ?? {})) glycans1.add(g);
    }
    for (const seq of Object.values(siteAbd2) as Array<{ data: Record<string, unknown> }>) {
      for (const g of Object.keys(seq.data ?? {})) glycans2.add(g);
    }
    const all = new Set([...glycans1, ...glycans2]);
    return [...all].sort().map((g) => ({
      glycan: g,
      in1: glycans1.has(g) ? "\u2713" : "",
      in2: glycans2.has(g) ? "\u2713" : "",
    }));
  }, [selectedSite, siteAbd1, siteAbd2]);

  if (listLoading) {
    return <LoadingSpinner message="Loading analyses..." size="lg" />;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Compare Analyses</h1>

      {/* Analysis selectors */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selA1}
            onChange={(e) => setSelA1(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="">Select analysis 1</option>
            {(analyses ?? []).map((a: AnalysisResponse) => (
              <option key={a.id} value={a.id}>
                {a.id}: {a.name}
              </option>
            ))}
          </select>
          <span className="text-sm text-gray-400">vs</span>
          <select
            value={selA2}
            onChange={(e) => setSelA2(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="">Select analysis 2</option>
            {(analyses ?? []).map((a: AnalysisResponse) => (
              <option key={a.id} value={a.id}>
                {a.id}: {a.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!selA1 || !selA2 || selA1 === selA2}
            onClick={handleCompare}
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Compare
          </button>
        </div>
      </div>

      {isLoading && id1 && id2 && (
        <LoadingSpinner message="Loading comparison..." />
      )}

      {id1 && id2 && !isLoading && analysis1 && analysis2 && (
        <>
          {/* Global Statistics Comparison */}
          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-800">
              Global Statistics
            </h2>
            <DataTable<QcRow> columns={namedQcColumns} data={qcRows} />
          </section>

          {/* Global Glycan Comparison */}
          <label className="inline-flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={showGlycans}
              onChange={(e) => setShowGlycans(e.target.checked)}
              className="rounded border-gray-300"
            />
            Show Identified Glycans Table
          </label>
          {showGlycans && glycanRows.length > 0 && (
            <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-gray-800">
                Identified Glycans
              </h2>
              <DataTable<GlycanCompareRow>
                columns={namedGlycanColumns}
                data={glycanRows}
                exportFilename={`compare_${name1}_vs_${name2}_glycans.csv`}
              />
            </section>
          )}

          {/* Glycosylation Sites + Per-site glycan detail (side by side) */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
            <section className="min-w-0 overflow-x-auto rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="mb-2 text-lg font-semibold text-gray-800">
                Glycosylation Sites
              </h2>
              <div className="mb-3 text-xs text-gray-500 space-y-0.5">
                <div>Analysis #{id1}: {name1}</div>
                <div>Analysis #{id2}: {name2}</div>
              </div>
              <p className="mb-2 text-xs text-gray-400">
                Click a row to view glycans identified at that site.
              </p>
              <DataTable<SiteCompareRow>
                columns={namedSiteColumns}
                data={siteRows}
                onRowClick={handleSiteClick}
                exportFilename={`compare_${name1}_vs_${name2}_sites.csv`}
                pageSize={30}
                highlightRow={(row) =>
                  row.accession === selectedSite?.accession &&
                  row.site === selectedSite?.site
                }
              />
            </section>

            {/* Per-site glycan detail (right panel) */}
            {selectedSite && (
              <section className="min-w-0 rounded-lg border border-blue-200 bg-blue-50 p-6 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-blue-800">
                    Glycans at {selectedSite.protein} — {selectedSite.site}
                  </h3>
                  <button
                    type="button"
                    onClick={() => setSelectedSite(null)}
                    className="text-xs text-blue-500 hover:text-blue-700 underline"
                  >
                    Close
                  </button>
                </div>
                {siteGlycanRows.length > 0 ? (
                  <DataTable<GlycanCompareRow>
                    columns={namedGlycanColumns}
                    data={siteGlycanRows}
                  />
                ) : (
                  <p className="text-xs text-gray-400">Loading...</p>
                )}
              </section>
            )}
          </div>
        </>
      )}

      {/* Parameter Modal */}
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
    </div>
  );
}

import { useState, useCallback, useMemo, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import type { GlycanSitesResult } from "../types";

// ── UniProt known glycan sites ─────────────────────────────────────
interface UniProtFeature {
  type: string;
  location: { start: { value: number }; end: { value: number } };
  description: string;
  featureId?: string;
}

function extractUniProtId(accession: string): string {
  // "sp|P00738|HPT_HUMAN" → "P00738"
  if (accession.includes("|")) return accession.split("|")[1];
  return accession;
}

function useUniProtGlycanSites(accession: string) {
  const uniprotId = extractUniProtId(accession);
  return useQuery<UniProtFeature[]>({
    queryKey: ["uniprot-glycan", uniprotId],
    enabled: !!uniprotId,
    staleTime: Infinity,
    queryFn: async () => {
      const res = await fetch(
        `https://rest.uniprot.org/uniprotkb/search?query=accession:${encodeURIComponent(uniprotId)}&fields=ft_carbohyd`,
      );
      if (!res.ok) throw new Error(`UniProt API error: ${res.status}`);
      const json = await res.json();
      return json.results?.[0]?.features ?? [];
    },
  });
}

function KnownGlycanSitesTable({ accession }: { accession: string }) {
  const { data: features, isLoading, error } = useUniProtGlycanSites(accession);

  return (
    <div className="bg-white rounded-lg shadow p-4 text-sm">
      <h3 className="font-semibold text-gray-700 mb-2">
        Known Glycan Sites{" "}
        <span className="font-normal text-gray-400">(UniProt)</span>
      </h3>
      {isLoading && <p className="text-gray-400 text-xs">Loading…</p>}
      {error && <p className="text-red-500 text-xs">Failed to fetch</p>}
      {features && features.length === 0 && (
        <p className="text-gray-400 text-xs">
          No glycosylation sites found in UniProt.
        </p>
      )}
      {features && features.length > 0 && (
        <div className="max-h-64 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white">
              <tr className="border-b text-left text-gray-500">
                <th className="py-1 pr-3">Position</th>
                <th className="py-1">Description</th>
              </tr>
            </thead>
            <tbody>
              {features.map((f, i) => (
                <tr key={f.featureId ?? i} className="border-b border-gray-100">
                  <td className="py-1 pr-3 font-mono">
                    {f.location.start.value}
                  </td>
                  <td className="py-1 text-gray-600">{f.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Motif lookup (from legacy glycan_interact.js) ───────────────────
const GLYCAN_TO_MOTIF: Record<string, string> = {
  "HexNAc(1)": "Paucimannose",
  "HexNAc(2)": "Paucimannose",
  "HexNAc(2)Fuc(1)": "Paucimannose",
  "HexNAc(2)Hex(1)": "Paucimannose",
  "HexNAc(2)Hex(1)Fuc(1)": "Paucimannose",
  "HexNAc(2)Hex(2)": "Paucimannose",
  "HexNAc(2)Hex(2)Fuc(1)": "Paucimannose",
  "HexNAc(2)Hex(3)": "Paucimannose",
  "HexNAc(2)Hex(3)Fuc(1)": "Paucimannose",
  "HexNAc(2)Hex(12)": "High Mannose",
  "HexNAc(2)Hex(11)": "High Mannose",
  "HexNAc(2)Hex(10)": "High Mannose",
  "HexNAc(2)Hex(9)": "High Mannose",
  "HexNAc(2)Hex(8)": "High Mannose",
  "HexNAc(2)Hex(7)": "High Mannose",
  "HexNAc(2)Hex(6)": "High Mannose",
  "HexNAc(2)Hex(5)": "High Mannose",
  "HexNAc(2)Hex(4)": "High Mannose",
  "HexNAc(2)Hex(6)Phospho(1)": "High Mannose",
};

const MOTIF_COLORS: Record<string, string> = {
  Paucimannose: "#99ccff",
  "High Mannose": "#99ffcc",
  "Complex/Hybrid": "#ff9966",
  Fucosylated: "#ffffcc",
  Sialylated: "#0033cc",
};
const DEFAULT_MOTIF_COLOR = "#E5E7E9";

function getGlycanMotif(comp: string): string {
  if (comp in GLYCAN_TO_MOTIF) return GLYCAN_TO_MOTIF[comp];
  if (/NeuAc|NeuGc|Sg/.test(comp)) return "Sialylated";
  if (/Fuc\(/.test(comp)) return "Fucosylated";
  return comp; // unclassified — returns composition itself
}

function getMotifColor(motif: string): string {
  return MOTIF_COLORS[motif] ?? DEFAULT_MOTIF_COLOR;
}

// ── SVG constants ──────────────────────────────────────────────────
const SVG_WIDTH = 1000;
const SVG_BASE_HEIGHT = 60; // space below bar (ticks + labels + padding)
const BAR_HEIGHT = 20;
const BAR_PAD_X = 60;
const CIRCLE_R = 5;
const BUFFER_FACTOR = 1.02; // 2% buffer like legacy

// ── API hook ───────────────────────────────────────────────────────
function useGlycanSites() {
  return useMutation<
    GlycanSitesResult,
    Error,
    {
      accession: string;
      analysis_id: string;
      pvalue_threshold: number;
      ref_condition: string;
      comp_condition: string;
    }
  >({
    mutationFn: (params) =>
      api.post("/glycan/sites", params).then((r) => r.data),
  });
}

// ── Types ──────────────────────────────────────────────────────────
interface SiteCircle {
  pos: number;
  cx: number;
  motif: string;
  color: string;
  comp: string;
  glycanName: string;
  gene: string;
}

interface SiteGroup {
  pos: number;
  cx: number;
  circles: SiteCircle[];
}

function buildSiteGroups(data: GlycanSitesResult): SiteGroup[] {
  const { site_list, max_site_pos } = data;
  const proteinLength = Math.max(max_site_pos, 1) * BUFFER_FACTOR;
  const usableWidth = SVG_WIDTH - BAR_PAD_X * 2;

  // Parse each site_list entry and group by position
  const posMap = new Map<number, SiteCircle[]>();

  for (const entry of site_list) {
    // format: "Protein---Position---Gene:::GlycanName:::GlycanComp"
    const [sitePart, glycanName = "", glycanComp = ""] = entry.split(":::");
    const parts = sitePart.split("---");
    const posStr = parts[1] ?? "";
    const gene = parts[2] ?? "";
    const posMatch = posStr.match(/(\d+)/);
    if (!posMatch) continue;
    const pos = Number(posMatch[1]);
    const cx = BAR_PAD_X + (pos / proteinLength) * usableWidth;
    const motif = getGlycanMotif(glycanComp);
    const color = getMotifColor(motif);

    if (!posMap.has(pos)) posMap.set(pos, []);
    posMap
      .get(pos)!
      .push({ pos, cx, motif, color, comp: glycanComp, glycanName, gene });
  }

  // Sort by position
  const groups: SiteGroup[] = [];
  for (const [pos, circles] of [...posMap.entries()].sort(
    (a, b) => a[0] - b[0],
  )) {
    groups.push({
      pos,
      cx: circles[0].cx,
      circles: circles.sort((a, b) => a.color.localeCompare(b.color)),
    });
  }
  return groups;
}

// ── Single diagram SVG ──────────────────────────────────────────────
function ProteinDiagram({
  groups,
  label,
  maxSitePos,
}: {
  groups: SiteGroup[];
  label: string;
  maxSitePos: number;
}) {
  const [hoveredPos, setHoveredPos] = useState<number | null>(null);

  // Compute dynamic height based on tallest circle stack
  const maxStack = groups.reduce(
    (max, g) => Math.max(max, g.circles.length),
    0,
  );
  const circlesHeight = maxStack * (CIRCLE_R * 2) + 8; // stack height + gap to bar
  const topPadding = 10;
  const barY = topPadding + circlesHeight;
  const svgHeight = barY + BAR_HEIGHT + SVG_BASE_HEIGHT;

  return (
    <div className="bg-white rounded-lg shadow p-4 overflow-x-auto">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{label}</h3>
      <svg
        viewBox={`0 0 ${SVG_WIDTH} ${svgHeight}`}
        className="w-full"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Protein backbone bar */}
        <rect
          x={BAR_PAD_X}
          y={barY}
          width={SVG_WIDTH - BAR_PAD_X * 2}
          height={BAR_HEIGHT}
          rx={4}
          fill="#AAAAAA"
        />

        {/* N-term / C-term */}
        <text
          x={BAR_PAD_X - 8}
          y={barY + BAR_HEIGHT / 2 + 5}
          textAnchor="end"
          fontSize={12}
          fill="#555"
        >
          N
        </text>
        <text
          x={SVG_WIDTH - BAR_PAD_X + 8}
          y={barY + BAR_HEIGHT / 2 + 5}
          textAnchor="start"
          fontSize={12}
          fill="#555"
        >
          C
        </text>

        {/* Site position tick marks + labels on axis */}
        {groups.map((g) => (
          <g key={`tick-${g.pos}`}>
            <line
              x1={g.cx}
              y1={barY + BAR_HEIGHT}
              x2={g.cx}
              y2={barY + BAR_HEIGHT + 10}
              stroke="#666"
              strokeWidth={1}
            />
            <text
              x={g.cx}
              y={barY + BAR_HEIGHT + 22}
              textAnchor="middle"
              fontSize={9}
              fill="#666"
            >
              {g.pos}
            </text>
          </g>
        ))}

        {/* Circles per site */}
        {groups.map((g) => {
          return g.circles.map((c, ci) => {
            const cy = barY - 8 - ci * (CIRCLE_R * 2);
            return (
              <g
                key={`${g.pos}-${ci}`}
                onMouseEnter={() => setHoveredPos(g.pos)}
                onMouseLeave={() => setHoveredPos(null)}
                className="cursor-pointer"
              >
                <circle
                  cx={c.cx}
                  cy={cy}
                  r={CIRCLE_R}
                  fill={c.color}
                  stroke="#888"
                  strokeWidth={1}
                />
              </g>
            );
          });
        })}
      </svg>

      {/* Tooltip on hover */}
      {hoveredPos !== null &&
        (() => {
          const g = groups.find((x) => x.pos === hoveredPos);
          if (!g) return null;
          return (
            <div className="mt-1 text-xs text-gray-700 bg-gray-50 rounded p-2 border">
              <span className="font-semibold">Site {hoveredPos}</span>
              {" — "}
              {g.circles.map((c, i) => (
                <span key={i} className="inline-flex items-center gap-1 mr-3">
                  <span
                    className="inline-block w-3 h-3 rounded-full border"
                    style={{ backgroundColor: c.color }}
                  />
                  {c.glycanName || c.comp} ({c.motif})
                </span>
              ))}
            </div>
          );
        })()}
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────
export function InteractPage() {
  const [searchParams] = useSearchParams();
  const accession = searchParams.get("accession") ?? "";
  const analysisId = searchParams.get("analysisId") ?? "";
  const refCondition = searchParams.get("ref") ?? "";
  const compCondition = searchParams.get("comp") ?? "";

  const [pThreshold, setPThreshold] = useState(0.1);

  // Two separate mutations: unfiltered (p=1) and filtered
  const unfilteredMutation = useGlycanSites();
  const filteredMutation = useGlycanSites();

  const baseParams = useMemo(
    () => ({
      accession,
      analysis_id: analysisId,
      ref_condition: refCondition,
      comp_condition: compCondition,
    }),
    [accession, analysisId, refCondition, compCondition],
  );

  // Fetch unfiltered only once on mount
  useEffect(() => {
    if (accession && analysisId) {
      unfilteredMutation.mutate({ ...baseParams, pvalue_threshold: 1 });
      filteredMutation.mutate({ ...baseParams, pvalue_threshold: pThreshold });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accession, analysisId]);

  // Only re-fetch filtered plot on threshold change
  const handleThresholdChange = (value: number) => {
    setPThreshold(value);
    if (accession && analysisId) {
      filteredMutation.mutate({ ...baseParams, pvalue_threshold: value });
    }
  };

  // Build site groups for each diagram
  const unfilteredGroups = useMemo(
    () =>
      unfilteredMutation.data ? buildSiteGroups(unfilteredMutation.data) : [],
    [unfilteredMutation.data],
  );
  const filteredGroups = useMemo(
    () => (filteredMutation.data ? buildSiteGroups(filteredMutation.data) : []),
    [filteredMutation.data],
  );

  const maxSitePos =
    unfilteredMutation.data?.max_site_pos ??
    filteredMutation.data?.max_site_pos ??
    0;
  const isLoading = unfilteredMutation.isPending || filteredMutation.isPending;
  const error = unfilteredMutation.error || filteredMutation.error;

  return (
    <div className="space-y-6">
      {/* Header row: info left, known sites right */}
      <div className="flex gap-6 items-start">
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold text-gray-900">
            Protein Glycosylation Map
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Accession: <span className="font-mono">{accession || "—"}</span>
            {refCondition && compCondition && (
              <>
                {" · "}
                {refCondition} → {compCondition}
              </>
            )}
          </p>
        </div>
        {accession && (
          <div className="w-80 flex-shrink-0">
            <KnownGlycanSitesTable accession={accession} />
          </div>
        )}
      </div>

      {/* Colour legend */}
      <div className="flex flex-wrap gap-4 text-sm">
        {Object.entries(MOTIF_COLORS).map(([motif, color]) => (
          <span key={motif} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-full border"
              style={{ backgroundColor: color }}
            />
            {motif}
          </span>
        ))}
      </div>

      {/* Loading / error */}
      {isLoading && <LoadingSpinner message="Fetching glycan sites…" />}
      {error && <p className="text-red-600 text-sm">Error: {error.message}</p>}

      {/* Plot 1: All glycans (unfiltered) */}
      {unfilteredMutation.data && (
        <ProteinDiagram
          groups={unfilteredGroups}
          label="All Glycosylation Sites (no p-value filter)"
          maxSitePos={maxSitePos}
        />
      )}

      {/* P-value slider */}
      <div className="bg-white rounded-lg shadow p-4 flex items-center gap-6">
        <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
          P-value threshold
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={pThreshold}
          onChange={(e) => handleThresholdChange(Number(e.target.value))}
          className="flex-1 accent-blue-600"
        />
        <input
          type="number"
          min={0}
          max={1}
          step={0.01}
          value={pThreshold}
          onChange={(e) => handleThresholdChange(Number(e.target.value))}
          className="w-20 rounded border border-gray-300 px-2 py-1 text-sm text-right font-mono"
        />
      </div>

      {/* Plot 2: Filtered by p-value */}
      {filteredMutation.data && (
        <ProteinDiagram
          groups={filteredGroups}
          label={`Glycosylation Sites (p-value ≤ ${pThreshold.toFixed(2)})`}
          maxSitePos={maxSitePos}
        />
      )}

      {/* Empty state */}
      {!unfilteredMutation.data && !isLoading && (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
          No glycosylation data available. Ensure the analysis has been run and
          conditions are selected.
        </div>
      )}
    </div>
  );
}

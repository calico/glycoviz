import Plot from "react-plotly.js";
import type { Data, Layout, Config, PlotMouseEvent } from "plotly.js";

interface VolcanoPlotProps {
  glycanList: string[];
  fc: number[]; // log2 fold change
  pValue: number[]; // -log10 p-value
  referenceCondition?: string;
  comparisonCondition?: string;
  highlightedPoint?: string; // glycan to highlight
  onPointClick?: (glycan: string) => void;
}

/**
 * Format a raw glycan_list entry ("Glycan---Protein---Position---Gene")
 * into a readable hover label matching the legacy display.
 */
function formatGlycanLabel(raw: string): string {
  const parts = raw.split("---");
  if (parts.length >= 4) {
    return `<b>${parts[0]}</b><br>${parts[1]} ${parts[2]}<br>Gene: ${parts[3]}`;
  }
  return raw;
}

/**
 * Volcano plot: scatter of log2(fold change) vs -log10(p-value).
 *
 * Significance thresholds:
 *  - Horizontal dashed line at y = 1.3  (-log10(0.05))
 *  - Vertical dashed lines at x = -1 and x = 1
 *
 * Points are colored red when significant (p < 0.05 AND |fc| > 1), gray otherwise.
 * An optional highlighted point is rendered in a separate trace with a star marker.
 */
export function VolcanoPlot({
  glycanList,
  fc,
  pValue,
  referenceCondition,
  comparisonCondition,
  highlightedPoint,
  onPointClick,
}: VolcanoPlotProps) {
  // Partition points into significant / non-significant sets.
  const sigX: number[] = [];
  const sigY: number[] = [];
  const sigNames: string[] = [];
  const nsX: number[] = [];
  const nsY: number[] = [];
  const nsNames: string[] = [];

  for (let i = 0; i < glycanList.length; i++) {
    const raw = glycanList[i];
    // Skip entries with empty glycan or site info
    if (!raw || raw === "---") continue;

    const x = fc[i];
    const y = pValue[i];
    const label = formatGlycanLabel(raw);
    const isSignificant = y > 1.3 && Math.abs(x) > 1;

    if (isSignificant) {
      sigX.push(x);
      sigY.push(y);
      sigNames.push(label);
    } else {
      nsX.push(x);
      nsY.push(y);
      nsNames.push(label);
    }
  }

  const traces: Data[] = [
    // Non-significant points
    {
      type: "scatter" as const,
      mode: "markers" as const,
      name: "Not significant",
      x: nsX,
      y: nsY,
      text: nsNames,
      hovertemplate:
        "%{text}<br>Log2 FC: %{x:.2f}<br>-log10(P): %{y:.2f}<extra></extra>",
      marker: {
        color: "#BDBDBD",
        size: 7,
        opacity: 0.7,
      },
    },
    // Significant points
    {
      type: "scatter" as const,
      mode: "markers" as const,
      name: "Significant",
      x: sigX,
      y: sigY,
      text: sigNames,
      hovertemplate:
        "%{text}<br>Log2 FC: %{x:.2f}<br>-log10(P): %{y:.2f}<extra></extra>",
      marker: {
        color: "#EF553B",
        size: 7,
        opacity: 0.85,
      },
    },
  ];

  // Highlighted point trace
  if (highlightedPoint) {
    const idx = glycanList.indexOf(highlightedPoint);
    if (idx !== -1) {
      traces.push({
        type: "scatter" as const,
        mode: "markers" as const,
        name: highlightedPoint.split("---")[0] || highlightedPoint,
        x: [fc[idx]],
        y: [pValue[idx]],
        text: [formatGlycanLabel(highlightedPoint)],
        hovertemplate:
          "%{text}<br>Log2 FC: %{x:.2f}<br>-log10(P): %{y:.2f}<extra></extra>",
        marker: {
          color: "#AB63FA",
          size: 14,
          symbol: "star",
          line: { color: "#333", width: 1 },
        },
      });
    }
  }

  // Axis range with padding
  const xMax = Math.max(2, ...fc.map(Math.abs)) * 1.15;
  const yMax = Math.max(2, ...pValue) * 1.15;

  const plotTitle =
    comparisonCondition && referenceCondition
      ? `Volcano Plot for Condition <b>${comparisonCondition}</b><br>to Reference condition: <b>${referenceCondition}</b>`
      : "Volcano Plot";

  const layout: Partial<Layout> = {
    title: plotTitle,
    xaxis: {
      title: "Log2 Fold-change",
      zeroline: false,
      range: [-xMax, xMax],
      automargin: true,
    },
    yaxis: {
      title: "-log10(P-value)",
      rangemode: "tozero",
      range: [0, yMax],
      automargin: true,
    },
    shapes: [
      // Horizontal threshold line: p = 0.05 → -log10(0.05) ≈ 1.3
      {
        type: "line",
        x0: -xMax,
        x1: xMax,
        y0: 1.3,
        y1: 1.3,
        line: { color: "#888", width: 1.5, dash: "dash" },
      },
      // Left vertical threshold: fc = -1
      {
        type: "line",
        x0: -1,
        x1: -1,
        y0: 0,
        y1: yMax,
        line: { color: "#888", width: 1.5, dash: "dash" },
      },
      // Right vertical threshold: fc = 1
      {
        type: "line",
        x0: 1,
        x1: 1,
        y0: 0,
        y1: yMax,
        line: { color: "#888", width: 1.5, dash: "dash" },
      },
    ],
    legend: {
      orientation: "v",
      x: 1.02,
      xanchor: "left",
      y: 1,
      yanchor: "top",
    },
    autosize: true,
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    margin: { t: 50, r: 150, b: 60, l: 60 },
  };

  const config: Partial<Config> = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
  };

  const handleClick = (event: PlotMouseEvent) => {
    if (!onPointClick || !event.points.length) return;
    const pt = event.points[0];
    const name = (pt as unknown as { text: string }).text;
    if (name) onPointClick(name);
  };

  return (
    <Plot
      data={traces}
      layout={layout}
      config={config}
      useResizeHandler
      style={{ width: "100%", height: "450px" }}
      onClick={handleClick}
    />
  );
}

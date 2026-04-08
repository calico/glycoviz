import Plot from "react-plotly.js";
import type { Data, Layout, Config } from "plotly.js";

interface ProteinProportionPlotProps {
  data: Record<
    string,
    { estimate: number[]; upperLimit: number[]; lowerLimit: number[] }
  >;
  conditionNames: string[];
  proteinName: string;
}

const CONDITION_COLORS = [
  "#636EFA",
  "#EF553B",
  "#00CC96",
  "#AB63FA",
  "#FFA15A",
  "#19D3F3",
  "#FF6692",
  "#B6E880",
  "#FF97FF",
  "#FECB52",
];

/**
 * Box plot showing protein proportion estimates per condition with error bars
 * derived from upper / lower confidence limits.
 *
 * Each condition produces one box trace built from the `estimate` array.
 * Overlaid scatter points show individual estimates with asymmetric error bars
 * (upper − estimate, estimate − lower).
 */
export function ProteinProportionPlot({
  data,
  conditionNames,
  proteinName,
}: ProteinProportionPlotProps) {
  const traces: Data[] = [];

  conditionNames.forEach((condName, condIdx) => {
    const condData = data[condName];
    if (!condData) return;

    const { estimate, upperLimit, lowerLimit } = condData;
    const color = CONDITION_COLORS[condIdx % CONDITION_COLORS.length];

    // Box trace for the distribution of estimates
    traces.push({
      type: "box" as const,
      name: condName,
      y: estimate,
      boxpoints: false,
      marker: { color },
      line: { color },
      fillcolor: hexToRgba(color, 0.3),
      legendgroup: condName,
    });

    // Scatter with error bars overlaid on the box
    const errorAbove = estimate.map((v, i) => (upperLimit[i] ?? v) - v);
    const errorBelow = estimate.map((v, i) => v - (lowerLimit[i] ?? v));

    traces.push({
      type: "scatter" as const,
      mode: "markers" as const,
      name: `${condName} (CI)`,
      x: estimate.map(() => condName),
      y: estimate,
      error_y: {
        type: "data" as const,
        symmetric: false,
        array: errorAbove,
        arrayminus: errorBelow,
        visible: true,
        color: color,
        thickness: 1.5,
        width: 4,
      },
      marker: {
        color,
        size: 6,
        opacity: 0.8,
      },
      showlegend: false,
      legendgroup: condName,
      hovertemplate:
        `${condName}<br>` +
        "Estimate: %{y:.4f}<br>" +
        "Upper: %{customdata[0]:.4f}<br>" +
        "Lower: %{customdata[1]:.4f}<extra></extra>",
      customdata: estimate.map((_, i) => [upperLimit[i], lowerLimit[i]]),
    });
  });

  const layout: Partial<Layout> = {
    title: `Protein Proportion — ${proteinName}`,
    yaxis: {
      title: "Proportion Estimate",
      automargin: true,
    },
    xaxis: {
      title: "Condition",
      automargin: true,
    },
    boxmode: "group",
    autosize: true,
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    legend: {
      orientation: "h",
      y: -0.2,
      x: 0.5,
      xanchor: "center",
    },
    margin: { t: 50, r: 30, b: 60, l: 60 },
  };

  const config: Partial<Config> = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
  };

  return (
    <Plot
      data={traces}
      layout={layout}
      config={config}
      useResizeHandler
      style={{ width: "100%", height: "100%" }}
    />
  );
}

/** Convert a hex color (#RRGGBB) to rgba with the given alpha. */
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

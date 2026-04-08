import Plot from "react-plotly.js";
import type { Data, Layout, Config } from "plotly.js";

interface FoldChangeSubplotsProps {
  glycanList: string[];
  /** Glycan-level log2 fold change */
  mean: number[];
  /** Protein-level log2 fold change */
  proteinMean: number[];
  /** Normalized glycan FC = glycan FC - protein FC */
  meanNorm: number[];
  /** -log10(p-value) */
  pValue: number[];
  referenceCondition: string;
  comparisonCondition: string;
}

/**
 * Format a raw glycan_list entry ("Glycan---Protein---Position---Gene")
 * into a readable hover label.
 */
function formatLabel(raw: string): string {
  const parts = raw.split("---");
  if (parts.length >= 4) {
    return `<b>${parts[0]}</b><br>${parts[1]} ${parts[2]}<br>Gene: ${parts[3]}`;
  }
  return raw;
}

/**
 * Two-subplot fold change plot matching the legacy "precision plot":
 *
 * Top subplot: Mean Glycan Log2 FC (x) vs Mean Protein Log2 FC (y)
 * Bottom subplot: Normalized Glycan Log2 FC (x) vs -log10(P-value) (y)
 */
export function FoldChangeSubplots({
  glycanList,
  mean,
  proteinMean,
  meanNorm,
  pValue,
  referenceCondition,
  comparisonCondition,
}: FoldChangeSubplotsProps) {
  const textLabels = glycanList.map(formatLabel);

  // Filter out zero-only points for cleaner display
  const x1: number[] = [];
  const y1: number[] = [];
  const t1: string[] = [];
  const x2: number[] = [];
  const y2: number[] = [];
  const t2: string[] = [];

  for (let i = 0; i < glycanList.length; i++) {
    if (mean[i] !== 0 || proteinMean[i] !== 0) {
      x1.push(mean[i]);
      y1.push(proteinMean[i]);
      t1.push(textLabels[i]);
    }
    if (meanNorm[i] !== 0 || pValue[i] !== 0) {
      x2.push(meanNorm[i]);
      y2.push(pValue[i]);
      t2.push(textLabels[i]);
    }
  }

  const traces: Data[] = [
    // Top subplot: glycan FC vs protein FC
    {
      type: "scattergl" as const,
      mode: "markers" as const,
      x: x1,
      y: y1,
      text: t1,
      hovertemplate:
        "%{text}<br>Glycan FC: %{x:.3f}<br>Protein FC: %{y:.3f}<extra></extra>",
      marker: { color: "rgb(139,0,0)", size: 7 },
      xaxis: "x",
      yaxis: "y",
      showlegend: false,
    },
    // Bottom subplot: normalized FC vs -log10(p)
    {
      type: "scattergl" as const,
      mode: "markers" as const,
      x: x2,
      y: y2,
      text: t2,
      hovertemplate:
        "%{text}<br>Norm FC: %{x:.3f}<br>-log10(P): %{y:.3f}<extra></extra>",
      marker: { color: "rgb(139,0,0)", size: 7 },
      xaxis: "x2",
      yaxis: "y2",
      showlegend: false,
    },
  ];

  // Axis ranges
  const meanMax = Math.max(1, ...mean.map(Math.abs)) + 0.1;
  const proteinMax = Math.max(1, ...proteinMean.map(Math.abs)) + 0.1;
  const normMax = Math.max(1, ...meanNorm.map(Math.abs)) + 0.1;
  const pMax = Math.max(1, ...pValue) + 0.1;
  const orthogonalMax = Math.max(meanMax, proteinMax);

  const layout: Partial<Layout> = {
    title: `Fold Change: Condition <b>${comparisonCondition}</b> to Reference <b>${referenceCondition}</b>`,
    grid: { rows: 2, columns: 1, pattern: "independent" as const },
    xaxis: {
      title: "Mean of Glycan Log2 Fold-change",
      range: [-orthogonalMax, orthogonalMax],
      automargin: true,
      showgrid: true,
    },
    yaxis: {
      title: "Mean of protein Log2 Fold-change",
      range: [-proteinMax, proteinMax],
      automargin: true,
      showgrid: true,
    },
    xaxis2: {
      title: "Mean of normalized Glycan Log2 Fold-change",
      range: [-normMax, normMax],
      automargin: true,
      showgrid: true,
      showspikes: true,
    },
    yaxis2: {
      title: "-log10(P_value)",
      range: [0, pMax],
      automargin: true,
      showgrid: true,
      showspikes: true,
    },
    shapes: [
      // Diagonal y=x line on top subplot
      {
        type: "line",
        x0: -orthogonalMax,
        y0: -orthogonalMax,
        x1: orthogonalMax,
        y1: orthogonalMax,
        xref: "x",
        yref: "y",
        line: { color: "rgb(128,128,128)", width: 1, dash: "dot" },
      },
    ],
    autosize: true,
    paper_bgcolor: "white",
    plot_bgcolor: "rgb(245,245,245)",
    margin: { t: 60, r: 30, b: 60, l: 70 },
    hovermode: "closest",
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
      style={{ width: "100%", height: "700px" }}
    />
  );
}

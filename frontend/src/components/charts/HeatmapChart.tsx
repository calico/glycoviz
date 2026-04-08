import Plot from "react-plotly.js";
import type { Data, Layout, Config } from "plotly.js";
import type { DendrogramData } from "../../types";

interface HeatmapChartProps {
  data: number[][];
  rowLabels: string[];
  colLabels: string[];
  rowDendrogram?: DendrogramData | null;
  colDendrogram?: DendrogramData | null;
  colorScale?: Array<[string, string]> | string;
  zmid?: number | null;
  colorbarTitle?: string;
}

const DEFAULT_COLOR_SCALE: Array<[string, string]> = [
  ["0.0", "rgb(0,255,255)"],
  ["0.5", "rgb(0,0,0)"],
  ["1.0", "rgb(255,255,0)"],
];

/** Build customdata so hover shows full row/col labels even when axis ticks are hidden or truncated. */
function buildCustomData(
  rowLabels: string[],
  colLabels: string[],
  data: number[][],
): string[][][] {
  return data.map((row, ri) =>
    row.map((_val, ci) => [rowLabels[ri], colLabels[ci]]),
  );
}

export function HeatmapChart({
  data,
  rowLabels,
  colLabels,
  rowDendrogram,
  colDendrogram,
  colorScale = DEFAULT_COLOR_SCALE,
  zmid,
  colorbarTitle = "Proportion",
}: HeatmapChartProps) {
  const hasRowDendro = rowDendrogram != null;
  const hasColDendro = colDendrogram != null;

  const customData = buildCustomData(rowLabels, colLabels, data);

  if (!hasRowDendro && !hasColDendro) {
    return (
      <SimpleHeatmap
        data={data}
        rowLabels={rowLabels}
        colLabels={colLabels}
        colorScale={colorScale}
        customData={customData}
        zmid={zmid}
        colorbarTitle={colorbarTitle}
      />
    );
  }

  // Subplot domain helpers – allocate 15 % for each dendrogram axis.
  const dendroSize = 0.15;
  const gap = 0.01;

  const heatXDomain: [number, number] = hasRowDendro
    ? [dendroSize + gap, 1]
    : [0, 1];
  const heatYDomain: [number, number] = hasColDendro
    ? [0, 1 - dendroSize - gap]
    : [0, 1];

  const traces: Data[] = [];

  // Heatmap trace
  const heatTrace: Record<string, unknown> = {
    type: "heatmap" as const,
    z: data,
    x: colLabels,
    y: rowLabels,
    customdata: customData,
    hovertemplate:
      "Row: %{customdata[0]}<br>Col: %{customdata[1]}<br>Value: %{z:.4f}<extra></extra>",
    colorscale: colorScale,
    showscale: true,
    colorbar: {
      len: hasColDendro ? 1 - dendroSize - gap : 1,
      title: { text: colorbarTitle, side: "right" as const },
    },
    xaxis: "x",
    yaxis: "y",
  };
  if (zmid != null) heatTrace.zmid = zmid;
  traces.push(heatTrace as Data);

  // Column dendrogram (top)
  if (hasColDendro && colDendrogram) {
    for (let i = 0; i < colDendrogram.icoord.length; i++) {
      traces.push({
        type: "scatter" as const,
        mode: "lines" as const,
        x: colDendrogram.icoord[i],
        y: colDendrogram.dcoord[i],
        line: { color: "#636EFA", width: 1.5 },
        hoverinfo: "none" as const,
        showlegend: false,
        xaxis: "x2",
        yaxis: "y2",
      });
    }
  }

  // Row dendrogram (left, rotated)
  if (hasRowDendro && rowDendrogram) {
    for (let i = 0; i < rowDendrogram.icoord.length; i++) {
      traces.push({
        type: "scatter" as const,
        mode: "lines" as const,
        x: rowDendrogram.dcoord[i],
        y: rowDendrogram.icoord[i],
        line: { color: "#636EFA", width: 1.5 },
        hoverinfo: "none" as const,
        showlegend: false,
        xaxis: "x3",
        yaxis: "y3",
      });
    }
  }

  const layout: Partial<Layout> = {
    autosize: true,
    height: 800,
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    margin: { t: 30, r: 40, b: 80, l: 30 },
    showlegend: false,

    xaxis: {
      domain: heatXDomain,
      tickangle: -45,
      tickfont: { size: 9 },
      automargin: true,
    },
    yaxis: {
      domain: heatYDomain,
      showticklabels: false,
      automargin: true,
    },
  };

  if (hasColDendro) {
    Object.assign(layout, {
      xaxis2: {
        domain: heatXDomain,
        showticklabels: false,
        showgrid: false,
        zeroline: false,
        anchor: "y2",
      },
      yaxis2: {
        domain: [1 - dendroSize, 1] as [number, number],
        showticklabels: false,
        showgrid: false,
        zeroline: false,
        anchor: "x2",
      },
    });
  }

  if (hasRowDendro) {
    Object.assign(layout, {
      xaxis3: {
        domain: [0, dendroSize] as [number, number],
        showticklabels: false,
        showgrid: false,
        zeroline: false,
        autorange: "reversed" as const,
        anchor: "y3",
      },
      yaxis3: {
        domain: heatYDomain,
        showticklabels: false,
        showgrid: false,
        zeroline: false,
        anchor: "x3",
      },
    });
  }

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

// ---- Simple (no-dendrogram) variant ----

function SimpleHeatmap({
  data,
  rowLabels,
  colLabels,
  colorScale,
  customData,
  zmid,
  colorbarTitle,
}: {
  data: number[][];
  rowLabels: string[];
  colLabels: string[];
  colorScale: Array<[string, string]> | string;
  customData: string[][][];
  zmid?: number | null;
  colorbarTitle: string;
}) {
  const heatTrace: Record<string, unknown> = {
    type: "heatmap" as const,
    z: data,
    x: colLabels,
    y: rowLabels,
    customdata: customData,
    hovertemplate:
      "Row: %{customdata[0]}<br>Col: %{customdata[1]}<br>Value: %{z:.4f}<extra></extra>",
    colorscale: colorScale,
    colorbar: { title: { text: colorbarTitle, side: "right" as const } },
  };
  if (zmid != null) heatTrace.zmid = zmid;

  const traces: Data[] = [heatTrace as Data];

  const layout: Partial<Layout> = {
    autosize: true,
    height: 800,
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    margin: { t: 30, r: 40, b: 80, l: 30 },
    xaxis: {
      tickangle: -45,
      tickfont: { size: 9 },
      automargin: true,
    },
    yaxis: {
      showticklabels: false,
      automargin: true,
    },
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

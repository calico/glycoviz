import Plot from "react-plotly.js";
import type { Data, Layout, Config } from "plotly.js";

interface GlycanBarChartProps {
  data: Record<string, number[]>; // glycan/motif name -> array of values per replicate
  conditionNames: string[];
  colNames: string[]; // sample names
  mode: "glycan" | "motif";
  valueType: "abundance" | "count";
  displayType: "absolute" | "percentage";
  compact?: boolean; // smaller fonts/legend for constrained spaces
  compositeScores?: Record<string, Record<string, number[]>>; // glycan -> score_type -> list of values
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
 * Interpolate between red (score=0) and green (score=1).
 * Returns a CSS color string.
 */
function scoreToColor(score: number): string {
  if (score >= 0.45) return "rgb(34,139,34)"; // green
  if (score >= 0.3) return "rgb(200,180,0)"; // yellow
  return "rgb(210,40,30)"; // red
}

/**
 * Build per-tick color array from composite scores (using MAX per glycan).
 */
function buildTickColors(
  glycanNames: string[],
  compositeScores?: Record<string, Record<string, number[]>>,
  defaultColor = "#333",
): string[] {
  if (!compositeScores || Object.keys(compositeScores).length === 0) {
    return glycanNames.map(() => defaultColor);
  }
  return glycanNames.map((name) => {
    const scoreMap = compositeScores[name];
    const scores = scoreMap?.composite;
    if (!scores || scores.length === 0) return defaultColor;
    return scoreToColor(Math.max(...scores));
  });
}

/**
 * Build per-glycan hover text showing individual and composite scores.
 * Returns an array of HTML strings (one per glycan) for use in hovertemplate.
 */
function buildScoreHoverTexts(
  glycanNames: string[],
  compositeScores?: Record<string, Record<string, number[]>>,
): string[] {
  if (!compositeScores || Object.keys(compositeScores).length === 0) {
    return glycanNames.map(() => "");
  }
  const scoreLabels: [string, string][] = [
    ["depth", "Depth %ile"],
    ["rt_conflict", "RT Conflict %ile"],
    ["engine_score", "Engine Score %ile"],
    ["composite", "Composite"],
  ];
  return glycanNames.map((name) => {
    const scoreMap = compositeScores[name];
    if (!scoreMap) return "";
    const lines: string[] = [];
    for (const [key, label] of scoreLabels) {
      const vals = scoreMap[key];
      if (vals && vals.length > 0) {
        lines.push(`${label}: [${vals.map((v) => v.toFixed(3)).join(", ")}]`);
      }
    }
    return lines.length > 0
      ? "<br><br><b>Scores</b><br>" + lines.join("<br>")
      : "";
  });
}

/** Check whether any composite scores actually exist for the given glycans. */
function hasScores(
  glycanNames: string[],
  compositeScores?: Record<string, Record<string, number[]>>,
): boolean {
  if (!compositeScores) return false;
  return glycanNames.some((n) => compositeScores[n]?.composite?.length);
}

/**
 * Build Plotly annotations that act as colored x-axis tick labels.
 * Each annotation is positioned at the corresponding category on the x-axis,
 * placed just below the plot area.
 */
function buildTickAnnotations(
  glycanNames: string[],
  tickColors: string[],
  fontSize: number,
): Partial<Layout>["annotations"] {
  return glycanNames.map((name, i) => ({
    x: name,
    y: 0,
    xref: "x" as const,
    yref: "paper" as const,
    text: `<b>${name}</b>`,
    showarrow: false,
    font: { size: fontSize, color: tickColors[i] },
    textangle: -45,
    xanchor: "right" as const,
    yanchor: "top" as const,
    yshift: -4,
  }));
}

/**
 * Grouped bar chart showing glycan or motif abundances per condition.
 * Each condition is a separate trace (color-coded), grouped along the x-axis
 * by glycan/motif name.
 */
export function GlycanBarChart({
  data,
  conditionNames,
  colNames,
  mode,
  valueType,
  displayType,
  compact = false,
  compositeScores,
}: GlycanBarChartProps) {
  const glycanNames = Object.keys(data);
  const tickColors = buildTickColors(glycanNames, compositeScores);
  const useColoredTicks = hasScores(glycanNames, compositeScores);
  const tickFontSize = compact ? 10 : 11;
  const scoreHoverTexts = buildScoreHoverTexts(glycanNames, compositeScores);

  // Map each sample to its condition index.
  // Assumption: colNames are ordered so that the first N samples belong to
  // condition 0, the next M to condition 1, etc.  We split evenly when
  // conditionNames.length divides colNames.length, otherwise fall back to a
  // round-robin assignment.
  const samplesPerCondition = colNames.length / conditionNames.length;
  const isEvenSplit = Number.isInteger(samplesPerCondition);

  const sampleConditionIndex = colNames.map((_, i) =>
    isEvenSplit
      ? Math.floor(i / samplesPerCondition)
      : i % conditionNames.length,
  );

  // For each condition compute the mean (and std) across its replicates for
  // every glycan / motif.
  const traces: Data[] = conditionNames.map((condName, condIdx) => {
    const replicateIndices = sampleConditionIndex.reduce<number[]>(
      (acc, ci, si) => {
        if (ci === condIdx) acc.push(si);
        return acc;
      },
      [],
    );

    const means: number[] = [];
    const errors: number[] = [];

    for (const gName of glycanNames) {
      const values = data[gName];
      const repValues = replicateIndices.map((ri) => values[ri] ?? 0);

      let mean = repValues.reduce((s, v) => s + v, 0) / (repValues.length || 1);

      if (displayType === "percentage") {
        // Compute the total across all glycans for the same replicates so
        // we can express each glycan's value as a percentage of the column total.
        const totals = replicateIndices.map((ri) =>
          glycanNames.reduce((s, g) => s + (data[g][ri] ?? 0), 0),
        );
        const pctValues = repValues.map((v, i) =>
          totals[i] ? (v / totals[i]) * 100 : 0,
        );
        mean = pctValues.reduce((s, v) => s + v, 0) / (pctValues.length || 1);

        const variance =
          pctValues.reduce((s, v) => s + (v - mean) ** 2, 0) /
          (pctValues.length || 1);
        errors.push(Math.sqrt(variance));
      } else {
        const variance =
          repValues.reduce((s, v) => s + (v - mean) ** 2, 0) /
          (repValues.length || 1);
        errors.push(Math.sqrt(variance));
      }

      means.push(mean);
    }

    return {
      type: "bar" as const,
      name: condName,
      x: glycanNames,
      y: means,
      customdata: scoreHoverTexts,
      hovertemplate:
        "%{x}<br>%{fullData.name}<br>Mean: %{y:.4f}%{customdata}<extra></extra>",
      error_y: {
        type: "data" as const,
        array: errors,
        visible: true,
      },
      marker: {
        color: CONDITION_COLORS[condIdx % CONDITION_COLORS.length],
      },
    };
  });

  const metricLabel = valueType === "abundance" ? "Abundance" : "Count";
  const yAxisLabel =
    displayType === "percentage" ? `${metricLabel} %` : metricLabel;

  const layout: Partial<Layout> = {
    barmode: "group",
    title: `${mode === "glycan" ? "Glycan" : "Motif"} ${metricLabel} by Condition`,
    xaxis: {
      title: useColoredTicks
        ? undefined
        : mode === "glycan"
          ? "Glycan"
          : "Motif",
      tickangle: -45,
      tickfont: { size: tickFontSize },
      automargin: true,
      ...(useColoredTicks ? { showticklabels: false } : {}),
    },
    yaxis: {
      title: { text: yAxisLabel },
      automargin: true,
    },
    legend: {
      orientation: "v",
      x: 1.02,
      xanchor: "left",
      y: 1,
      yanchor: "top",
      font: { size: compact ? 9 : 12 },
    },
    autosize: true,
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    margin: {
      t: 50,
      r: compact ? 120 : 150,
      b: useColoredTicks ? 180 : 140,
      l: 60,
    },
    ...(useColoredTicks
      ? {
          annotations: buildTickAnnotations(
            glycanNames,
            tickColors,
            tickFontSize,
          ),
        }
      : {}),
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
      style={{ width: "100%", height: "550px" }}
    />
  );
}

/**
 * Grouped bar chart showing glycan or motif abundances per individual replicate/sample.
 * Each sample is a separate trace (color-coded), grouped along the x-axis
 * by glycan/motif name. No error bars – raw per-sample values.
 */
export function GlycanBarChartByReplicate({
  data,
  colNames,
  mode,
  valueType,
  displayType,
  compact = false,
  compositeScores,
}: GlycanBarChartProps) {
  const glycanNames = Object.keys(data);
  const tickColors = buildTickColors(glycanNames, compositeScores);
  const useColoredTicks = hasScores(glycanNames, compositeScores);
  const tickFontSize = compact ? 10 : 11;
  const scoreHoverTexts = buildScoreHoverTexts(glycanNames, compositeScores);

  // Pre-compute column totals for percentage mode
  const colTotals: number[] = colNames.map((_, si) =>
    glycanNames.reduce((sum, g) => sum + (data[g][si] ?? 0), 0),
  );

  const traces: Data[] = colNames.map((sampleName, si) => {
    const yValues = glycanNames.map((gName) => {
      const raw = data[gName][si] ?? 0;
      if (displayType === "percentage") {
        return colTotals[si] ? (raw / colTotals[si]) * 100 : 0;
      }
      return raw;
    });

    return {
      type: "bar" as const,
      name: sampleName,
      x: glycanNames,
      y: yValues,
      customdata: scoreHoverTexts,
      hovertemplate:
        "%{x}<br>%{fullData.name}<br>Value: %{y:.4f}%{customdata}<extra></extra>",
      marker: {
        color: CONDITION_COLORS[si % CONDITION_COLORS.length],
      },
    };
  });

  const metricLabel = valueType === "abundance" ? "Abundance" : "Count";
  const yAxisLabel =
    displayType === "percentage" ? `${metricLabel} %` : metricLabel;

  const layout: Partial<Layout> = {
    barmode: "group",
    title: `${mode === "glycan" ? "Glycan" : "Motif"} ${metricLabel} by Replicate`,
    xaxis: {
      title: useColoredTicks
        ? undefined
        : mode === "glycan"
          ? "Glycan"
          : "Motif",
      tickangle: -45,
      tickfont: { size: tickFontSize },
      automargin: true,
      ...(useColoredTicks ? { showticklabels: false } : {}),
    },
    yaxis: {
      title: { text: yAxisLabel },
      automargin: true,
    },
    legend: {
      orientation: "v",
      x: 1.02,
      xanchor: "left",
      y: 1,
      yanchor: "top",
      font: { size: compact ? 9 : 12 },
    },
    autosize: true,
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    margin: {
      t: 50,
      r: compact ? 120 : 150,
      b: useColoredTicks ? 180 : 140,
      l: 80,
    },
    ...(useColoredTicks
      ? {
          annotations: buildTickAnnotations(
            glycanNames,
            tickColors,
            tickFontSize,
          ),
        }
      : {}),
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
      style={{ width: "100%", height: "550px" }}
    />
  );
}

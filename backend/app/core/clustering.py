"""Hierarchical and k-means clustering for heatmap generation.

Replaces the legacy R-based ``heatmap_clustering.R`` with a pure Python
implementation built on scipy and scikit-learn.  All dendrogram data is
returned as plain Python types so it can be serialised to JSON directly.

Ported to Python 3.11+ with full type annotations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist
from sklearn.cluster import KMeans


# ---------------------------------------------------------------------------
# Configuration & result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ClusterParams:
    """Parameters that control how the data matrix is clustered.

    Attributes
    ----------
    distance_metric:
        Distance metric for hierarchical clustering.  Supported values:
        ``"euclidean"``, ``"manhattan"``, ``"maximum"``, ``"minkowski"``.
        ``"manhattan"`` and ``"maximum"`` are mapped to the scipy-compatible
        names ``"cityblock"`` and ``"chebyshev"`` internally.
    linkage_method:
        Agglomeration strategy for hierarchical clustering.  One of
        ``"complete"``, ``"single"``, or ``"average"``.
    use_kmeans:
        If ``True``, rows are grouped using k-means instead of hierarchical
        clustering and no row dendrogram is produced.
    k_clusters:
        Number of clusters for k-means (ignored when *use_kmeans* is ``False``).
    clr_transform:
        Apply a centred log-ratio (CLR) transform before clustering.
    zscore_transform:
        Apply row-wise z-score normalisation before clustering.  When both
        *clr_transform* and *zscore_transform* are enabled, CLR is applied
        first.
    """

    distance_metric: str = "euclidean"
    linkage_method: str = "complete"
    use_kmeans: bool = False
    k_clusters: int = 3
    clr_transform: bool = False
    zscore_transform: bool = False
    meaningful_change_cutoff: int = 0


@dataclass
class ClusterResult:
    """Clustering output ready for front-end heatmap rendering.

    Attributes
    ----------
    heatmap_data:
        The (possibly transformed) 2-D data matrix with rows and columns
        reordered according to the clustering result.
    row_labels:
        Row labels after reordering.
    col_labels:
        Column labels after reordering.
    row_dendrogram:
        Dendrogram dictionary for rows with keys ``"icoord"``,
        ``"dcoord"``, ``"ivl"``, and ``"leaves"``.  ``None`` when k-means
        clustering is used.
    col_dendrogram:
        Dendrogram dictionary for columns (same structure as
        *row_dendrogram*).  ``None`` when k-means clustering is used.
    """

    heatmap_data: np.ndarray
    row_labels: list[str]
    col_labels: list[str]
    row_dendrogram: dict | None = None
    col_dendrogram: dict | None = None


# ---------------------------------------------------------------------------
# Pre-processing helpers
# ---------------------------------------------------------------------------

# Mapping from user-facing metric names to scipy equivalents.
_METRIC_MAP: dict[str, str] = {
    "manhattan": "cityblock",
    "maximum": "chebyshev",
}


def clr_transform(data: np.ndarray) -> np.ndarray:
    """Apply a centred log-ratio (CLR) transform row-wise.

    For each row the CLR is defined as::

        clr(x_i) = log( x_i / G(x) )

    where *G(x)* is the geometric mean of the row.  Zeros are replaced by
    a small epsilon (half the smallest non-zero value in the matrix) before
    the transform so that the logarithm is well-defined.

    Parameters
    ----------
    data:
        2-D array of shape ``(n_rows, n_cols)`` with non-negative values.

    Returns
    -------
    np.ndarray
        CLR-transformed array with the same shape as *data*.
    """
    work = data.astype(np.float64, copy=True)

    # Replace zeros with a small pseudo-count.
    nonzero_vals = work[work > 0]
    epsilon = nonzero_vals.min() / 2 if nonzero_vals.size > 0 else 1e-10
    work[work == 0] = epsilon

    # Geometric mean per row: exp( mean( log(x) ) )
    log_data = np.log(work)
    geo_means = np.exp(log_data.mean(axis=1, keepdims=True))

    return log_data - np.log(geo_means)


def zscore_normalize(data: np.ndarray) -> np.ndarray:
    """Row-wise z-score normalisation.

    Each row is transformed to have zero mean and unit standard deviation.
    Rows with zero standard deviation are left unchanged to avoid division
    by zero.

    Parameters
    ----------
    data:
        2-D array of shape ``(n_rows, n_cols)``.

    Returns
    -------
    np.ndarray
        Z-score normalised array with the same shape as *data*.
    """
    work = data.astype(np.float64, copy=True)
    means = work.mean(axis=1, keepdims=True)
    # Use ddof=1 to match R's scale() which uses sample standard deviation.
    stds = work.std(axis=1, keepdims=True, ddof=1)

    # Avoid division by zero for constant rows.
    mask = stds.squeeze() != 0
    work[mask] = (work[mask] - means[mask]) / stds[mask]
    return work


def _signif(data: np.ndarray, digits: int = 4) -> np.ndarray:
    """Round array elements to *digits* significant digits (like R's signif())."""
    out = data.copy()
    nonzero = (data != 0) & np.isfinite(data)
    if nonzero.any():
        vals = data[nonzero]
        magnitude = np.floor(np.log10(np.abs(vals))).astype(int)
        decimals = -magnitude + (digits - 1)
        rounded = np.array([np.around(v, int(d)) for v, d in zip(vals, decimals)])
        out[nonzero] = rounded
    return out


# ---------------------------------------------------------------------------
# Dendrogram serialisation
# ---------------------------------------------------------------------------


def _dendrogram_to_dict(dendro: dict) -> dict:
    """Convert scipy dendrogram arrays to JSON-serialisable plain lists.

    Parameters
    ----------
    dendro:
        Dictionary returned by :func:`scipy.cluster.hierarchy.dendrogram`.

    Returns
    -------
    dict
        A copy containing only the keys ``"icoord"``, ``"dcoord"``,
        ``"ivl"``, and ``"leaves"`` with all numpy arrays converted to
        nested Python lists.
    """
    return {
        "icoord": [list(map(float, row)) for row in dendro["icoord"]],
        "dcoord": [list(map(float, row)) for row in dendro["dcoord"]],
        "ivl": list(dendro["ivl"]),
        "leaves": list(int(x) for x in dendro["leaves"]),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def cluster_data(data: pd.DataFrame, params: ClusterParams) -> ClusterResult:
    """Cluster rows and columns of *data* for heatmap visualisation.

    The pipeline is:

    1. Optionally apply CLR transform.
    2. Optionally apply row-wise z-score normalisation.
    3. Cluster rows (hierarchical **or** k-means) and columns (always
       hierarchical when not using k-means).
    4. Reorder the matrix and labels according to the clustering.
    5. Return a :class:`ClusterResult` with JSON-ready dendrogram data.

    Parameters
    ----------
    data:
        A ``pandas.DataFrame`` whose index contains row labels and whose
        columns contain column labels.  Values should be numeric.
    params:
        A :class:`ClusterParams` instance controlling the clustering
        behaviour.

    Returns
    -------
    ClusterResult
        Clustered matrix, reordered labels, and (optionally) dendrogram
        metadata.

    Raises
    ------
    ValueError
        If the DataFrame is empty or contains non-numeric data.
    """
    if data.empty:
        raise ValueError("Input DataFrame must not be empty")

    matrix = data.to_numpy(dtype=np.float64, copy=True)
    row_labels = list(data.index.astype(str))
    col_labels = list(data.columns.astype(str))

    # ------------------------------------------------------------------
    # 1 & 2  – Transforms
    # ------------------------------------------------------------------
    if params.clr_transform:
        matrix = clr_transform(matrix)

    # Fold-change filter: keep rows where max(|CLR value|) > log(cutoff).
    # Applied after CLR, before z-score (matches legacy R behaviour).
    if params.meaningful_change_cutoff > 0:
        threshold = np.log(params.meaningful_change_cutoff)
        keep_mask = np.nanmax(np.abs(matrix), axis=1) > threshold
        if not np.any(keep_mask):
            raise ValueError("Filtering for fold change left no rows to cluster.")
        matrix = matrix[keep_mask]
        row_labels = [row_labels[i] for i, keep in enumerate(keep_mask) if keep]

    if params.zscore_transform:
        matrix = zscore_normalize(matrix)

    # Round to 4 significant digits to match legacy R: signif(x, digits=4)
    matrix = _signif(matrix, 4)

    # ------------------------------------------------------------------
    # Resolve scipy-compatible metric name
    # ------------------------------------------------------------------
    metric = _METRIC_MAP.get(params.distance_metric, params.distance_metric)

    # ------------------------------------------------------------------
    # 3  – Clustering
    # ------------------------------------------------------------------
    row_dendro_dict: dict | None = None
    col_dendro_dict: dict | None = None

    if params.use_kmeans:
        # -- K-means for rows; no dendrogram --------------------------
        n_clusters = min(params.k_clusters, matrix.shape[0])
        km = KMeans(n_clusters=n_clusters, n_init="auto", random_state=42)
        labels = km.fit_predict(matrix)

        # Reorder rows so that members of the same cluster are adjacent.
        order = np.argsort(labels, kind="stable")
        matrix = matrix[order]
        row_labels = [row_labels[i] for i in order]
    else:
        # -- Hierarchical clustering for rows -------------------------
        if matrix.shape[0] > 1:
            row_dist = pdist(matrix, metric=metric)
            row_link = linkage(row_dist, method=params.linkage_method)
            row_dendro = dendrogram(row_link, no_plot=True)
            row_dendro_dict = _dendrogram_to_dict(row_dendro)

            row_order = row_dendro["leaves"]
            matrix = matrix[row_order]
            row_labels = [row_labels[i] for i in row_order]

        # -- Hierarchical clustering for columns ----------------------
        if matrix.shape[1] > 1:
            col_dist = pdist(matrix.T, metric=metric)
            col_link = linkage(col_dist, method=params.linkage_method)
            col_dendro = dendrogram(col_link, no_plot=True)
            col_dendro_dict = _dendrogram_to_dict(col_dendro)

            col_order = col_dendro["leaves"]
            matrix = matrix[:, col_order]
            col_labels = [col_labels[i] for i in col_order]

    return ClusterResult(
        heatmap_data=matrix,
        row_labels=row_labels,
        col_labels=col_labels,
        row_dendrogram=row_dendro_dict,
        col_dendrogram=col_dendro_dict,
    )

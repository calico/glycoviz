from pydantic import BaseModel


class ClusterRequest(BaseModel):
    analysis_id: int
    distance_metric: str = "euclidean"
    linkage_method: str = "complete"
    cluster_by_row: bool = True
    cluster_by_column: bool = True
    use_kmeans: bool = False
    k_clusters: int = 3
    clr_transform: bool = False
    zscore_transform: bool = False
    meaningful_change_cutoff: int = 0
    order_by_condition: bool = False
    condition_order: list[str] | None = None


class ClusterResult(BaseModel):
    heatmap_data: list[list[float]]
    row_labels: list[str]
    col_labels: list[str]
    row_dendrogram: dict | None = None
    col_dendrogram: dict | None = None
    total_quantified: int = 0
    heatmap_count: int = 0
    zmid: float | None = None
    colorbar_title: str = "Proportion"

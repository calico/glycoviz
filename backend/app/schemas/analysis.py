import datetime
from typing import Optional

from pydantic import BaseModel


class ColumnHeaderSet(BaseModel):
    """A named set of column header mappings for a particular search engine."""

    name: str = ""
    glycan_composition: str = ""
    protein_accessions: str = ""
    position_in_protein: str = ""
    master_protein_descriptions: str = ""
    sequence: str = ""
    modifications: str = ""
    modifications_fallback: str = ""
    retention_time: str = ""
    fdr_prefix: str = ""
    engine_score_prefix: str = ""
    ppm_prefix: str = ""
    abundance_columns: str = ""


# Pre-built Byonic defaults
BYONIC_HEADER_SET = ColumnHeaderSet(
    name="Byonic",
    glycan_composition="Glycan Composition",
    protein_accessions="Protein Accessions",
    position_in_protein="Position in Protein",
    master_protein_descriptions="Master Protein Descriptions",
    sequence="Sequence",
    modifications="Modifications (all possible sites)",
    modifications_fallback="Modifications",
    retention_time="Top Apex RT [min]",
    fdr_prefix="FDR 2D (by Search Engine)",
    engine_score_prefix="Byonic Score (",
    ppm_prefix="DeltaM [ppm] ",
    abundance_columns="Abundances (Grouped)*",
)

# Pre-built MSFragger defaults (native column names)
MSFRAGGER_HEADER_SET = ColumnHeaderSet(
    name="MSFragger",
    protein_accessions="Protein ID",
    master_protein_descriptions="Protein Description",
    modifications="Assigned Modifications",
    fdr_prefix="Probability",
)


class AnalysisCreate(BaseModel):
    file_id: str
    name: str = ""
    conditions: dict[str, str]
    fdr_threshold: float = 0.01
    fdr_is_probability: bool = False
    byonic_score: float = 150.0
    ppm_threshold: float = 10.0
    peptide_length: int = 6
    min_count: int = 1
    export_filter: str = "All"
    abundance_type: str = "Abundances (Grouped)"
    study_code: str | None = None
    quant_method: str | None = None
    note: str | None = None
    w_depth: float = 0.4
    w_conflict: float = 0.4
    w_byonic: float = 0.2
    column_header_sets: Optional[list[ColumnHeaderSet]] = None


class AnalysisResponse(BaseModel):
    id: int
    name: str
    study_code: str | None
    quant_method: str | None
    note: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class AnalysisRunResult(BaseModel):
    analysis_id: int
    output_file: str
    site_to_rows: dict
    statistics: dict
    qc_output_file: str


class UploadResponse(BaseModel):
    file_id: str
    columns: list[str]
    all_headers: list[str] = []

from pydantic import BaseModel


class FoldChangeRequest(BaseModel):
    analysis_id: str
    reference_condition: str
    comparison_condition: str


class FoldChangeResult(BaseModel):
    glycan_list: list[str]
    fc: list[float]
    p_value: list[float]
    anova: list[float] | None = None


class FcAvgRequest(BaseModel):
    analysis_id: str
    reference_condition: str
    comparison_condition: str
    remap_fasta: str | None = None

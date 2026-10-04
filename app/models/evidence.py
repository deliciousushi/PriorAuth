from pydantic import BaseModel, Field
from typing import Literal

class EvidenceItem(BaseModel):

    document: str = Field(
        description="Patient document containing the evidence"
    )
    page: int | None = Field(
        default=None,
        description="Page containing the evidence"
    )
    reference: str | None = Field(
        default=None,
        description="Section, paragraph, note, or other source reference"
    )
    text: str = Field(
        description="Relevant evidence text"
    )

class EvidenceResponse(BaseModel):
    evidence: list[EvidenceItem]

class EvidenceMatch(BaseModel):

    requirement_id: str

    applicability: Literal[
        "APPLICABLE",
        "NOT_APPLICABLE",
        "UNKNOWN"
    ]
    status: Literal[
        "SATISFIED",
        "NOT_SATISFIED",
        "UNKNOWN"
    ]
    reasoning: str
    evidence: list[EvidenceItem]
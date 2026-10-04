from langchain_core.prompts import ChatPromptTemplate

from app.services.groq_client import get_llm
from app.models.evidence import EvidenceItem, EvidenceResponse


class ChartAgent:

    def __init__(self, retriever):
        self.retriever = retriever
        self.llm = get_llm()

    def find_evidence(
        self,
        patient_id: str,
        requirement: str,
        evidence_required: list[str]
    ) -> list[EvidenceItem]:

        query = f"""
Insurance requirement:

{requirement}

Evidence that may be relevant:

{", ".join(evidence_required)}
"""

        retrieved = self.retriever.search(
            patient_id=patient_id,
            query=query,
            top_k=5
        )

        if not retrieved:
            return []

        context = "\n\n".join(
            [
                f"""
DOCUMENT: {item["document"]}
PAGE: {item.get("page")}

TEXT:
{item["text"]}
"""
                for item in retrieved
            ]
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You are the Chart Reviewer in a Prior Authorization system.

Task: Extract patient-record evidence relevant to insurance requirements.

Rules:
1. Use ONLY supplied patient records.
2. NEVER invent patient info.
3. Return ALL relevant evidence, even if it shows requirement NOT met.
4. Do NOT decide satisfaction of requirement.
5. Do NOT reject contradictory evidence.
6. If no evidence, return [].
7. Include section/note/heading/page number when possible.
8. Preserve source document.
9. No outside medical knowledge.

Output: Structured schema with traceable evidence.
"""
                ),
                (
                    "human",
                    """
INSURANCE REQUIREMENT:
{requirement}

EVIDENCE TYPES OF INTEREST:
{evidence_required}

PATIENT RECORDS:
{context}

Find all patient-record evidence relevant to the requirement.
Return evidence only, not judgment.

"""
                )
            ]
        )

        structured_llm = self.llm.with_structured_output(
            EvidenceResponse
        )

        result = (
            prompt | structured_llm
        ).invoke(
            {
                "requirement": requirement,
                "evidence_required": evidence_required,
                "context": "\n\n".join(
                    [
                        f"""
                DOCUMENT: {item["document"]}
                PAGE: {item.get("page")}
                SOURCE REFERENCE: {item.get("reference")}

                TEXT:
                {item["text"]}
                """
                        for item in retrieved
                    ]
                )
            }
        )

        return result.evidence
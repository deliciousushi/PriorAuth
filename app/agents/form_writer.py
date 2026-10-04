from langchain_core.prompts import ChatPromptTemplate
from app.models.prior_auth import PriorAuthDraft
from app.services.groq_client import get_llm

class FormWriter:

    def __init__(self):
        self.llm = get_llm()

    def generate(
        self,
        patient_id: str,
        treatment: str,
        insurer: str,
        guideline,
        evidence_matches
    ) -> PriorAuthDraft:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You are the Form Writer for a Prior Authorization system.

Create a professional prior authorization draft using ONLY
patient-record evidence supplied in the evidence assessments.

Rules:

1. Never invent patient information.
2. Never invent clinical history.
3. Never invent dates or treatment duration.
4. Never convert UNKNOWN into a factual claim.
5. Never describe a NOT_SATISFIED requirement as satisfied.
6. Only use evidence from SATISFIED evidence assessments
   as positive support for the requested authorization.
7. Clearly identify missing information when requirements
   cannot be supported.
8. Do not make new medical decisions.
9. Do not state that a treatment is "medically necessary"
   unless that conclusion is explicitly supported by the
   supplied policy or patient evidence.
10. Do not introduce facts from outside the supplied documents.
11. Keep the justification concise and evidence-grounded.
"""
                ),
                (
                    "human",
                    """
PATIENT:
{patient_id}

TREATMENT:
{treatment}

INSURER:
{insurer}

GUIDELINE:
{guideline}

VALIDATED EVIDENCE:
{evidence_matches}
"""
                )
            ]
        )

        structured_llm = self.llm.with_structured_output(
            PriorAuthDraft
        )

        return (
            prompt | structured_llm
        ).invoke(
            {
                "patient_id": patient_id,
                "treatment": treatment,
                "insurer": insurer,
                "guideline": guideline,
                "evidence_matches": evidence_matches
            }
        )

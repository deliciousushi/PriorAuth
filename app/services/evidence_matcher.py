from langchain_core.prompts import ChatPromptTemplate

from app.models.evidence import EvidenceMatch
from app.services.groq_client import get_llm


class EvidenceMatcher:

    def __init__(self):
        self.llm = get_llm()

    def match(
        self,
        requirement_id: str,
        requirement: str,
        evidence_required: list[str],
        condition: str | None,
        evidence,
    ) -> EvidenceMatch:

        # ========================================================
        # PROMPT
        # ========================================================

        prompt = ChatPromptTemplate.from_messages(
            [

                # ====================================================
                # SYSTEM PROMPT
                # ====================================================

                (
                    "system",
                    """
You are the Evidence Matcher in a Prior Authorization system.

Your job is to determine:

1. Whether a conditional insurance requirement applies.
2. If it applies, whether the requirement is satisfied.

You must use ONLY the supplied patient evidence.

Do not use outside medical knowledge.

============================================================
APPLICABILITY
============================================================

If the requirement has a condition:

APPLICABLE
- Evidence clearly establishes that the condition is true.

NOT_APPLICABLE
- Evidence clearly establishes that the condition is false.

UNKNOWN
- The available evidence is insufficient to determine
  whether the condition is true or false.

If there is no condition, applicability is APPLICABLE.

============================================================
REQUIREMENT STATUS
============================================================

SATISFIED
- The requirement applies and the supplied evidence
  clearly demonstrates that the requirement is satisfied.

NOT_SATISFIED
- The requirement applies and the supplied evidence contains
  AFFIRMATIVE evidence that the requirement is not satisfied.

Examples:

- Policy requires treatment for >=12 weeks and the record
  explicitly states treatment lasted only 6 weeks.

- Policy requires a specific diagnosis and the record
  explicitly states that the patient does not have that
  diagnosis.

- Policy requires a clinical response and the record
  explicitly documents that the required response did not occur.

UNKNOWN
- The available evidence is insufficient to determine whether
  the requirement is satisfied.

IMPORTANT DISTINCTION:

Missing documentation is NOT the same as evidence that
the requirement was not satisfied.

For example:

"The record does not document the treatment duration."

must result in:

UNKNOWN

NOT:

NOT_SATISFIED

Similarly:

"No clinical response is documented."

must result in:

UNKNOWN

NOT:

NOT_SATISFIED

Use NOT_SATISFIED only when the supplied evidence
affirmatively demonstrates that the requirement was not met.

============================================================
ABSENCE OF EVIDENCE
============================================================

Treat phrases such as:

- "not documented"
- "not recorded"
- "not provided"
- "documentation is unavailable"
- "documentation unavailable"
- "no information is available"
- "no information available"
- "the record does not state"
- "the record does not document"
- "duration is unknown"
- "response is unknown"
- "outcome is unknown"

as evidence insufficiency.

These phrases should normally lead to:

UNKNOWN

They should NOT lead to:

NOT_SATISFIED

unless the same evidence also contains an affirmative
contradictory fact.

============================================================
CONDITIONAL REQUIREMENTS
============================================================

For a conditional requirement:

- NOT_APPLICABLE → status is SATISFIED.
- UNKNOWN applicability → status is UNKNOWN.
- APPLICABLE → evaluate the requirement normally.

============================================================
IMPORTANT RULES
============================================================

1. Never invent patient information.

2. Never assume missing documentation means that the
   underlying event did not happen.

3. Distinguish:

      evidence of absence

   from:

      absence of evidence.

4. "Not documented" means the available evidence is
   insufficient unless an affirmative contradictory fact
   is also present.

5. Do not infer treatment duration from the fact that
   a treatment was prescribed or administered.

6. Do not infer treatment failure from the absence of
   a documented response.

7. Do not infer treatment success from the absence of
   a documented failure.

8. If evidence is insufficient, use UNKNOWN.

9. Use NOT_SATISFIED only when the supplied evidence
   affirmatively demonstrates that the requirement
   was not met.

10. Preserve the supplied evidence.

11. Explain what evidence is missing when status is UNKNOWN.

12. When the requirement is conditional and applicability
    is UNKNOWN, the requirement status MUST be UNKNOWN.

============================================================
REASONING
============================================================

Your reasoning must explain:

- Why the requirement applies or does not apply.
- Whether the requirement is satisfied.
- What evidence supports the decision.
- What information is missing when the result is UNKNOWN.

Do not claim that a patient failed a requirement merely
because the available record does not contain enough
information to prove compliance.
"""
                ),

                # ====================================================
                # HUMAN PROMPT
                # ====================================================

                (
                    "human",
                    """
REQUIREMENT ID:
{requirement_id}

INSURANCE REQUIREMENT:
{requirement}

CONDITION:
{condition}

EVIDENCE REQUIRED:
{evidence_required}

PATIENT EVIDENCE:
{evidence}

Determine:

1. Applicability
2. Requirement status
3. Reasoning
4. Supporting evidence

Do not invent information.
"""
                ),
            ]
        )

        # ========================================================
        # STRUCTURED LLM OUTPUT
        # ========================================================

        structured_llm = self.llm.with_structured_output(
            EvidenceMatch
        )

        result = (
            prompt
            | structured_llm
        ).invoke(
            {
                "requirement_id": requirement_id,
                "requirement": requirement,
                "condition": (
                    condition
                    or "No condition — always applicable."
                ),
                "evidence_required": evidence_required,
                "evidence": evidence,
            }
        )

        # ========================================================
        # SAFETY NORMALIZATION
        # ========================================================
        absence_phrases = [
            "not documented",
            "not recorded",
            "not provided",
            "documentation is unavailable",
            "documentation unavailable",
            "no information is available",
            "no information available",
            "the record does not state",
            "the record does not document",
            "duration is unknown",
            "response is unknown",
            "outcome is unknown",
        ]

        affirmative_failure_phrases = [
            "only",
            "less than",
            "shorter than",
            "failed",
            "failure",
            "does not meet",
            "does not have",
            "did not meet",
            "did not complete",
            "was not completed",
            "was below",
            "was less",
            "insufficient duration",
            "inadequate duration",
            "contraindicated",
        ]

        # --------------------------------------------------------
        # Normalize reasoning text
        # --------------------------------------------------------

        reasoning_text = (
            result.reasoning.lower()
            if result.reasoning
            else ""
        )

        # --------------------------------------------------------
        # Normalize evidence text
        # --------------------------------------------------------

        evidence_text = " ".join(
            item.text.lower()
            for item in (result.evidence or [])
            if getattr(item, "text", None)
        )

        # --------------------------------------------------------
        # Combine reasoning + evidence
        # --------------------------------------------------------

        combined_text = (
            reasoning_text
            + " "
            + evidence_text
        )

        # --------------------------------------------------------
        # Detect missing documentation
        # --------------------------------------------------------

        has_absence_language = any(
            phrase in combined_text
            for phrase in absence_phrases
        )

        # --------------------------------------------------------
        # Detect affirmative failure
        # --------------------------------------------------------

        has_affirmative_failure = any(
            phrase in combined_text
            for phrase in affirmative_failure_phrases
        )
        if (
            result.status == "NOT_SATISFIED"
            and has_absence_language
            and not has_affirmative_failure
        ):

            result.status = "UNKNOWN"

            result.reasoning = (
                result.reasoning
                + " The available evidence indicates that the "
                "required information is not documented, rather "
                "than affirmatively demonstrating that the "
                "requirement was not satisfied. Therefore the "
                "status is UNKNOWN."
            )

        if result.applicability == "UNKNOWN":

            result.status = "UNKNOWN"

            result.reasoning = (
                result.reasoning
                + " Because applicability is UNKNOWN, the "
                "conditional requirement cannot be determined "
                "to be satisfied or not satisfied."
            )
        return result
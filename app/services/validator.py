from langchain_core.prompts import ChatPromptTemplate
from app.services.groq_client import get_llm

class Validator:

    def __init__(self):
        self.llm = get_llm()

    # REQUIRED FIELD VALIDATION
    def validate_required_fields(self, draft) -> list[str]:

        errors = []

        if not draft.patient_id:
            errors.append("Missing patient ID")
        if not draft.treatment:
            errors.append("Missing treatment")
        if not draft.insurer:
            errors.append("Missing insurer")
        if not draft.diagnosis:
            errors.append("Missing diagnosis")
        if not draft.clinical_justification:
            errors.append(
                "Missing clinical justification"
            )

        return errors

    # CLAIM VALIDATION
    def validate_claims(
        self,
        draft,
        evidence_matches,
    ):
        prompt = ChatPromptTemplate.from_messages(
            [

                (
                    "system",
                    """
You are the final claim validation layer for
a Prior Authorization system.

Your job is to determine whether important claims
in the generated prior authorization draft are
supported by the supplied patient evidence.

Return exactly one of:

PASS
FAIL

PASS:
- Important claims are supported by the supplied evidence.

FAIL:
- An important claim is unsupported, invented,
  contradicted, or materially stronger than the evidence.

Rules:

1. Use ONLY the supplied evidence.
2. Never introduce outside medical knowledge.
3. Do not decide whether treatment is medically appropriate.
4. Do not treat missing evidence as evidence that something
   happened or did not happen.
5. If the draft makes an unsupported clinical claim,
   return FAIL.
"""
                ),

                (
                    "human",
                    """
GENERATED PRIOR AUTHORIZATION:
{draft}

SUPPLIED EVIDENCE:
{evidence_matches}

Return only:

PASS

or

FAIL
"""
                ),
            ]
        )

        response = (
            prompt | self.llm
        ).invoke(
            {
                "draft": draft.model_dump_json(),
                "evidence_matches": evidence_matches,
            }
        )

        result = response.content.strip().upper()

        if "FAIL" in result:
            return "FAIL"

        return "PASS"

    # FINAL VALIDATION
    def validate(
        self,
        draft,
        guideline,
        evidence_matches,
    ):
        """
        Produce the final deterministic validation status.

        PASS:
            - Required fields are present
            - All mandatory requirements are satisfied
            - Generated PA claims are supported

        FAIL:
            - Required field missing
            OR
            - Mandatory requirement clearly not satisfied
            OR
            - Generated claim is unsupported

        REVIEW:
            - Mandatory requirement is UNKNOWN
            - No required-field failure
            - Claims are otherwise supported
        """

        # 1. Required fields
        errors = self.validate_required_fields(
            draft
        )

        if errors:

            return {
                "status": "FAIL",
                "errors": errors,
                "claim_validation": "NOT_RUN",
            }

        # 2. Requirement validation
        mandatory_not_satisfied = []
        mandatory_unknown = []

        for requirement in guideline.requirements:

            if not requirement.mandatory:
                continue

            match = next(
                (
                    item
                    for item in evidence_matches
                    if item.requirement_id
                    == requirement.requirement_id
                ),
                None,
            )

            # No match for a mandatory requirement
            # means we cannot establish compliance.
            if match is None:

                mandatory_unknown.append(
                    requirement.requirement_id
                )

                continue

            if match.status == "NOT_SATISFIED":

                mandatory_not_satisfied.append(
                    requirement.requirement_id
                )

            elif match.status == "UNKNOWN":

                mandatory_unknown.append(
                    requirement.requirement_id
                )

        # 3. Zero requirements
        if not guideline.requirements:

            return {
                "status": "REVIEW",
                "errors": [
                    "No insurance requirements were extracted."
                ],
                "claim_validation": "NOT_RUN",
            }

        # 4. Claim validation
        claim_validation = self.validate_claims(
            draft,
            evidence_matches,
        )

        # Unsupported generated claim is a hard failure.
        if claim_validation == "FAIL":

            return {
                "status": "FAIL",
                "errors": [
                    "Generated prior authorization contains "
                    "unsupported or contradicted claims."
                ],
                "claim_validation": "FAIL",
            }

        # 5. Mandatory requirement failure
        if mandatory_not_satisfied:

            return {
                "status": "FAIL",
                "errors": [
                    "Mandatory requirements not satisfied: "
                    + ", ".join(
                        mandatory_not_satisfied
                    )
                ],
                "claim_validation": "PASS",
            }

        # 6. Mandatory requirement uncertainty
        if mandatory_unknown:

            return {
                "status": "REVIEW",
                "errors": [
                    "Mandatory requirements require "
                    "additional evidence: "
                    + ", ".join(
                        mandatory_unknown
                    )
                ],
                "claim_validation": "PASS",
            }

        # 7. Everything passed
        return {
            "status": "PASS",
            "errors": [],
            "claim_validation": "PASS",
        }
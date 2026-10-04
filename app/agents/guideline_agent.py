from langchain_core.prompts import ChatPromptTemplate

from app.models.guideline import Guideline
from app.services.groq_client import get_llm
from app.services.pdf_parser import extract_pdf_text


SYSTEM_PROMPT = """
You are the Guidelines Reader for a Prior Authorization system.

Your job is to extract prior authorization requirements
from an insurance company's clinical policy.

IMPORTANT RULES:

1. Extract requirements ONLY from the supplied document.
2. Do not use outside medical knowledge.
3. Do not invent requirements.
4. Preserve the meaning of the insurance policy.
5. Identify whether each requirement is mandatory.
6. Identify what evidence would be needed to prove each requirement.
7. Identify whether the requirement is conditional.
8. If a requirement begins with language such as "if", "when",
   "unless", or another condition, record that condition explicitly.
9. Record the source document and page number.
10. If information is unclear, represent the uncertainty rather
   than inventing information.
11. Do not decide whether a patient qualifies.
12. Do not interpret patient information.

You are extracting policy requirements only.

Return the information using the requested structured schema.
""" 


def create_guideline_agent():

    llm = get_llm()

    structured_llm = llm.with_structured_output(
        Guideline
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                SYSTEM_PROMPT
            ),
            (
                "human",
                    """
            Analyze the following insurance policy.

            Requested treatment:
            {treatment_name}

            First identify the treatment or medication that this policy applies to.

            Then extract ALL prior authorization requirements from the supplied
            policy that apply to that treatment.

            IMPORTANT:
            - Do not assume that the requested treatment name must exactly match
              the treatment name used in the policy.
            - Use the policy text to determine the covered treatment.
            - If the policy clearly applies to a different treatment, do NOT
             silently return an empty requirements list.
            - Extract the requirements only from the supplied policy.
            - Preserve requirement IDs when explicitly provided.
            - Preserve mandatory/conditional language.
            - Record the source page for every requirement.

            INSURANCE POLICY:

            {policy_text}
            """
            )
        ]
    )

    return prompt | structured_llm


def run_guideline_agent(
    pdf_path: str,
    treatment_name: str
) -> Guideline:

    policy_text = extract_pdf_text(pdf_path)
    if not policy_text.strip():
        raise ValueError(
            "The guideline PDF contains no extractable text."
        )

    agent = create_guideline_agent()

    result = agent.invoke(
        {
        "policy_text": policy_text,
        "treatment_name": treatment_name
        }
    )

    if not result.requirements:
        raise ValueError(
            f"No prior authorization requirements were extracted for "
            f"'{treatment_name}'. Check that the uploaded guideline "
            f"actually applies to this treatment."
        )

    return result
        

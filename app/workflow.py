from typing import TypedDict, Any

from langgraph.graph import StateGraph, START, END

from app.agents.guideline_agent import run_guideline_agent
from app.agents.chart_agent import ChartAgent
from app.agents.form_writer import FormWriter

from app.rag.retrieve import PatientRetriever

from app.services.evidence_matcher import EvidenceMatcher
from app.services.validator import Validator


class PriorAuthState(TypedDict, total=False):

    request_id: int
    patient_id: str
    treatment: str
    insurer: str
    guideline_path: str

    guideline: Any
    evidence: list
    evidence_matches: list

    draft: Any

    validation_errors: list
    validation_result: str


def guideline_node(state: PriorAuthState):

    guideline = run_guideline_agent(
        pdf_path=state["guideline_path"],
        treatment_name=state["treatment"]
    )
    print("=====Guideline debug=====")
    print("Guideline: ", guideline)
    print("requirements: ", guideline.requirements)
    print("requirement counts: ", len(guideline.requirements))

    return {
        "guideline": guideline
    }


def chart_node(state: PriorAuthState):

    retriever = PatientRetriever(
        request_id=state["request_id"]
    )

    chart_agent = ChartAgent(
        retriever=retriever
    )

    all_evidence = []

    for requirement in state["guideline"].requirements:

        evidence = chart_agent.find_evidence(
            patient_id=state["patient_id"],
            requirement=requirement.description,
            evidence_required=requirement.evidence_required
        )

        all_evidence.append(
            {
                "requirement_id": requirement.requirement_id,
                "evidence": evidence
            }
        )

    return {
        "evidence": all_evidence
    }


def evidence_node(state: PriorAuthState):

    matcher = EvidenceMatcher()

    matches = []

    for requirement in state["guideline"].requirements:

        requirement_evidence = next(
            (
                item["evidence"]
                for item in state["evidence"]
                if item["requirement_id"]
                == requirement.requirement_id
            ),
            []
        )

        match = matcher.match(
            requirement_id=requirement.requirement_id,
            requirement=requirement.description,
            evidence_required=requirement.evidence_required,
            condition=requirement.condition,
            evidence=requirement_evidence,
        )

        matches.append(match)

    return {
        "evidence_matches": matches
    }


def form_node(state: PriorAuthState):

    writer = FormWriter()

    draft = writer.generate(
        patient_id=state["patient_id"],
        treatment=state["treatment"],
        insurer=state["insurer"],
        guideline=state["guideline"],
        evidence_matches=state["evidence_matches"]
    )

    return {
        "draft": draft
    }


def validation_node(state: PriorAuthState):

    validator = Validator()

    result = validator.validate(
        draft=state["draft"],
        guideline=state["guideline"],
        evidence_matches=state["evidence_matches"],
    )

    return {
        "validation_errors": result["errors"],
        "validation_result": result["status"],
    }

def build_workflow():

    graph = StateGraph(PriorAuthState)

    graph.add_node(
        "guideline_reader",
        guideline_node
    )

    graph.add_node(
        "chart_reviewer",
        chart_node
    )

    graph.add_node(
        "evidence_matcher",
        evidence_node
    )

    graph.add_node(
        "form_writer",
        form_node
    )

    graph.add_node(
        "validator",
        validation_node
    )

    graph.add_edge(
        START,
        "guideline_reader"
    )

    graph.add_edge(
        "guideline_reader",
        "chart_reviewer"
    )

    graph.add_edge(
        "chart_reviewer",
        "evidence_matcher"
    )

    graph.add_edge(
        "evidence_matcher",
        "form_writer"
    )

    graph.add_edge(
        "form_writer",
        "validator"
    )

    graph.add_edge(
        "validator",
        END
    )

    return graph.compile()

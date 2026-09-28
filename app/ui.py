import os
import tempfile

import streamlit as st

from app.database import initialize_database, create_requestimport os
from pathlib import Path

import streamlit as st

from app.database import (
    initialize_database,
    create_request,
    update_request,
    add_audit_log,
    get_recent_requests
)

from app.rag.ingest import ingest_patient_documents
from app.workflow import build_workflow


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="PriorAuth AI",
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

initialize_database()


# --------------------------------------------------
# CSS
# --------------------------------------------------

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1150px;
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    .app-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0;
    }

    .app-subtitle {
        color: #6b7280;
        font-size: 0.9rem;
        margin-bottom: 1.2rem;
    }

    .metric-card {
        padding: 12px 16px;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        background: #fafafa;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 650;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }

    .evidence-card {
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        margin-bottom: 8px;
        background: #ffffff;
    }

    div[data-testid="stFileUploader"] {
        border-radius: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown(
    '<div class="app-title">⚕️ PriorAuth AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="app-subtitle">'
    'Evidence-grounded prior authorization assistant'
    '</div>',
    unsafe_allow_html=True
)


# --------------------------------------------------
# TOP METRICS
# --------------------------------------------------

recent_requests = get_recent_requests()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Total Requests",
        len(recent_requests)
    )

with col2:
    completed = sum(
        r["status"] == "COMPLETED"
        for r in recent_requests
    )

    st.metric(
        "Completed",
        completed
    )

with col3:
    processing = sum(
        r["status"] == "PROCESSING"
        for r in recent_requests
    )

    st.metric(
        "Processing",
        processing
    )


st.divider()


# --------------------------------------------------
# REQUEST FORM
# --------------------------------------------------

left, right = st.columns(
    [1, 1],
    gap="large"
)


with left:

    st.markdown(
        '<div class="section-title">Patient & Request</div>',
        unsafe_allow_html=True
    )

    patient_id = st.text_input(
        "Patient ID",
        placeholder="e.g. P001"
    )

    treatment = st.text_input(
        "Requested Treatment",
        placeholder="e.g. Drug X"
    )

    insurer = st.text_input(
        "Insurance Provider",
        placeholder="e.g. Demo Insurance"
    )


with right:

    st.markdown(
        '<div class="section-title">Documents</div>',
        unsafe_allow_html=True
    )

    guideline_file = st.file_uploader(
        "Insurance guideline",
        type=["pdf"],
        accept_multiple_files=False
    )

    patient_files = st.file_uploader(
        "Patient medical records",
        type=["pdf"],
        accept_multiple_files=True
    )


st.divider()


# --------------------------------------------------
# RUN BUTTON
# --------------------------------------------------

run = st.button(
    "⚡ Generate Prior Authorization",
    type="primary",
    use_container_width=True
)


# --------------------------------------------------
# WORKFLOW
# --------------------------------------------------

if run:

    if not patient_id:
        st.error("Enter a Patient ID.")

    elif not treatment:
        st.error("Enter the requested treatment.")

    elif not insurer:
        st.error("Enter the insurance provider.")

    elif guideline_file is None:
        st.error("Upload the insurance guideline PDF.")

    elif not patient_files:
        st.error("Upload at least one patient medical record.")

    else:

        request_id = create_request(
            patient_id=patient_id,
            treatment=treatment,
            insurer=insurer
        )

        add_audit_log(
            request_id,
            "DOCUMENTS_RECEIVED",
            f"{len(patient_files)} patient document(s) uploaded."
        )

        # ------------------------------------------
        # Save guideline
        # ------------------------------------------

        guideline_dir = Path(
            "data/guidelines"
        )

        guideline_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        guideline_path = (
            guideline_dir /
            guideline_file.name
        )

        with open(
            guideline_path,
            "wb"
        ) as file:

            file.write(
                guideline_file.getbuffer()
            )

        # ------------------------------------------
        # Save patient documents
        # ------------------------------------------

        patient_dir = Path(
            "data/patients"
        ) / patient_id

        patient_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        for uploaded_file in patient_files:

            file_path = (
                patient_dir /
                uploaded_file.name
            )

            with open(
                file_path,
                "wb"
            ) as file:

                file.write(
                    uploaded_file.getbuffer()
                )

        # ------------------------------------------
        # RAG INGESTION
        # ------------------------------------------

        with st.spinner(
            "Indexing patient records..."
        ):

            ingest_patient_documents(
                patient_id=patient_id,
                patient_directory=str(patient_dir)
            )

        add_audit_log(
            request_id,
            "RAG_INGESTION_COMPLETED",
            "Patient records indexed successfully."
        )

        # ------------------------------------------
        # WORKFLOW
        # ------------------------------------------

        try:

            workflow = build_workflow()

            initial_state = {
                "patient_id": patient_id,
                "treatment": treatment,
                "insurer": insurer,
                "guideline_path": str(
                    guideline_path
                )
            }

            with st.spinner(
                "Running PriorAuth AI agents..."
            ):

                result = workflow.invoke(
                    initial_state
                )

            draft = result["draft"]

            validation_result = result[
                "validation_result"
            ]

            update_request(
                request_id=request_id,
                status="COMPLETED",
                draft=draft,
                validation_result=validation_result
            )

            add_audit_log(
                request_id,
                "WORKFLOW_COMPLETED",
                "Prior authorization workflow completed."
            )

            # --------------------------------------
            # RESULTS
            # --------------------------------------

            st.success(
                f"Prior authorization generated successfully "
                f"(Request #{request_id})"
            )

            # --------------------------------------
            # REQUIREMENTS
            # --------------------------------------

            st.markdown(
                '<div class="section-title">'
                '📋 Guideline Requirements'
                '</div>',
                unsafe_allow_html=True
            )

            guideline = result["guideline"]

            for requirement in guideline.requirements:

                status = next(
                    (
                        m.status
                        for m in result["evidence_matches"]
                        if m.requirement_id
                        == requirement.requirement_id
                    ),
                    "UNKNOWN"
                )

                icon = {
                    "SATISFIED": "✅",
                    "NOT_SATISFIED": "❌",
                    "UNKNOWN": "⚠️"
                }.get(
                    status,
                    "⚠️"
                )

                with st.expander(
                    f"{icon} "
                    f"{requirement.requirement_id} — "
                    f"{requirement.description}"
                ):

                    st.write(
                        "**Evidence required:**"
                    )

                    for evidence_type in (
                        requirement.evidence_required
                    ):
                        st.write(
                            f"• {evidence_type}"
                        )

                    st.caption(
                        f"Source page: "
                        f"{requirement.source_page}"
                    )

            # --------------------------------------
            # EVIDENCE
            # --------------------------------------

            st.markdown(
                '<div class="section-title">'
                '🔎 Evidence Matching'
                '</div>',
                unsafe_allow_html=True
            )

            for match in result[
                "evidence_matches"
            ]:

                if match.status == "SATISFIED":
                    st.success(
                        f"{match.requirement_id} — "
                        f"Satisfied"
                    )

                elif match.status == "NOT_SATISFIED":
                    st.error(
                        f"{match.requirement_id} — "
                        f"Not satisfied"
                    )

                else:
                    st.warning(
                        f"{match.requirement_id} — "
                        f"Insufficient evidence"
                    )

                st.write(
                    match.reasoning
                )

                for evidence in match.evidence:

                    with st.container(
                        border=True
                    ):

                        st.caption(
                            f"📄 {evidence.document}"
                            f"  |  Page {evidence.page}"
                        )

                        st.write(
                            evidence.text
                        )

            # --------------------------------------
            # DRAFT
            # --------------------------------------

            st.markdown(
                '<div class="section-title">'
                '📝 Prior Authorization Draft'
                '</div>',
                unsafe_allow_html=True
            )

            with st.container(
                border=True
            ):

                st.markdown(
                    "**Diagnosis**"
                )

                st.write(
                    draft.diagnosis
                )

                st.markdown(
                    "**Clinical Justification**"
                )

                st.write(
                    draft.clinical_justification
                )

                st.markdown(
                    "**Previous Treatments**"
                )

                for previous in (
                    draft.previous_treatments
                ):
                    st.write(
                        f"• {previous}"
                    )

                if draft.missing_information:

                    st.warning(
                        "Missing information"
                    )

                    for missing in (
                        draft.missing_information
                    ):
                        st.write(
                            f"• {missing}"
                        )

            # --------------------------------------
            # VALIDATION
            # --------------------------------------

            st.markdown(
                '<div class="section-title">'
                '🛡️ Validation'
                '</div>',
                unsafe_allow_html=True
            )

            if validation_result == "PASS":

                st.success(
                    "Validation passed — "
                    "draft claims are supported by evidence."
                )

            else:

                st.warning(
                    validation_result
                )

        except Exception as error:

            update_request(
                request_id=request_id,
                status="FAILED"
            )

            add_audit_log(
                request_id,
                "WORKFLOW_FAILED",
                str(error)
            )

            st.error(
                "Workflow failed."
            )

            st.exception(error)


# --------------------------------------------------
# HISTORY
# --------------------------------------------------

st.divider()

st.markdown(
    '<div class="section-title">'
    '🗂 Recent Requests'
    '</div>',
    unsafe_allow_html=True
)

history = get_recent_requests(8)

if history:

    for request in history:

        status = request["status"]

        if status == "COMPLETED":
            icon = "🟢"
        elif status == "FAILED":
            icon = "🔴"
        else:
            icon = "🟡"

        st.write(
            f"{icon} **#{request['id']}** — "
            f"{request['patient_id']} — "
            f"{request['treatment']} — "
            f"{status}"
        )

else:

    st.caption(
        "No previous requests."
    )
from app.rag.ingest import ingest_patient_documents
from app.workflow import build_workflow


# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="PriorAuth AI",
    page_icon="🏥",
    layout="wide"
)


# ---------------------------------------------------------
# INITIALIZE DATABASE
# ---------------------------------------------------------

initialize_database()


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("🏥 PriorAuth AI")
st.caption(
    "Evidence-grounded Prior Authorization Assistant"
)

st.divider()


# ---------------------------------------------------------
# INPUT SECTION
# ---------------------------------------------------------

st.header("Prior Authorization Request")

col1, col2 = st.columns(2)

with col1:

    patient_id = st.text_input(
        "Patient ID",
        value="P001"
    )

    treatment = st.text_input(
        "Treatment",
        value="Advanced Therapy X"
    )


with col2:

    insurer = st.text_input(
        "Insurance Provider",
        value="Demo Insurance"
    )

    st.write("")


# ---------------------------------------------------------
# FILE UPLOADS
# ---------------------------------------------------------

st.subheader("Documents")

patient_file = st.file_uploader(
    "Upload Patient Chart (PDF)",
    type=["pdf"],
    key="patient_chart"
)

guideline_file = st.file_uploader(
    "Upload Insurance Guideline (PDF)",
    type=["pdf"],
    key="guideline"
)


# ---------------------------------------------------------
# DOCUMENT PREVIEW
# ---------------------------------------------------------

if patient_file is not None:

    st.success(
        f"Patient chart uploaded: {patient_file.name}"
    )


if guideline_file is not None:

    st.success(
        f"Insurance guideline uploaded: {guideline_file.name}"
    )


st.divider()


# ---------------------------------------------------------
# GENERATE BUTTON
# ---------------------------------------------------------

generate = st.button(
    "🚀 Generate Prior Authorization",
    type="primary",
    use_container_width=True
)


# ---------------------------------------------------------
# WORKFLOW
# ---------------------------------------------------------

if generate:

    # ---------------------------------------------
    # Validate inputs
    # ---------------------------------------------

    if not patient_id.strip():

        st.error("Please enter a Patient ID.")
        st.stop()


    if not treatment.strip():

        st.error("Please enter a treatment.")
        st.stop()


    if not insurer.strip():

        st.error("Please enter an insurance provider.")
        st.stop()


    if patient_file is None:

        st.error(
            "Please upload the patient's clinical chart PDF."
        )
        st.stop()


    if guideline_file is None:

        st.error(
            "Please upload the insurance guideline PDF."
        )
        st.stop()


    # ---------------------------------------------
    # Create temporary working directories
    # ---------------------------------------------

    temp_root = tempfile.mkdtemp(
        prefix="priorauth_"
    )

    patient_directory = os.path.join(
        temp_root,
        "patients",
        patient_id
    )

    guideline_directory = os.path.join(
        temp_root,
        "guidelines"
    )

    os.makedirs(
        patient_directory,
        exist_ok=True
    )

    os.makedirs(
        guideline_directory,
        exist_ok=True
    )


    # ---------------------------------------------
    # Save uploaded patient chart
    # ---------------------------------------------

    patient_pdf_path = os.path.join(
        patient_directory,
        patient_file.name
    )

    with open(
        patient_pdf_path,
        "wb"
    ) as file:

        file.write(
            patient_file.getbuffer()
        )


    # ---------------------------------------------
    # Save uploaded guideline
    # ---------------------------------------------

    guideline_pdf_path = os.path.join(
        guideline_directory,
        guideline_file.name
    )

    with open(
        guideline_pdf_path,
        "wb"
    ) as file:

        file.write(
            guideline_file.getbuffer()
        )


    # ---------------------------------------------
    # Create database request
    # ---------------------------------------------

    request_id = create_request(
        patient_id=patient_id,
        treatment=treatment,
        insurer=insurer
    )


    st.info(
        f"Workflow started — Request #{request_id}"
    )


    # ---------------------------------------------
    # Ingest patient chart into RAG
    # ---------------------------------------------

    try:

        with st.spinner(
            "Indexing patient chart..."
        ):

            ingest_patient_documents(
                patient_id=patient_id,
                patient_directory=patient_directory
            )

    except Exception as error:

        st.error(
            "Patient chart ingestion failed."
        )

        st.exception(error)

        st.stop()


    # ---------------------------------------------
    # Build workflow
    # ---------------------------------------------

    try:

        workflow = build_workflow()

        initial_state = {

            "patient_id": patient_id,

            "treatment": treatment,

            "insurer": insurer,

            "guideline_path": guideline_pdf_path

        }


        # -----------------------------------------
        # Run workflow
        # -----------------------------------------

        with st.spinner(
            "Analyzing guideline and patient evidence..."
        ):

            result = workflow.invoke(
                initial_state
            )


    except Exception as error:

        st.error(
            "Prior authorization workflow failed."
        )

        st.exception(error)

        st.stop()


    # ---------------------------------------------
    # WORKFLOW COMPLETED
    # ---------------------------------------------

    st.success(
        "Prior Authorization workflow completed."
    )


    # =================================================
    # GUIDELINE REQUIREMENTS
    # =================================================

    st.header("1. Guideline Requirements")

    guideline = result["guideline"]

    for requirement in guideline.requirements:

        with st.expander(
            requirement.requirement_id,
            expanded=True
        ):

            st.write(
                "**Requirement:**"
            )

            st.write(
                requirement.description
            )


            st.write(
                "**Mandatory:**"
            )

            st.write(
                "Yes"
                if requirement.mandatory
                else "No"
            )


            st.write(
                "**Evidence Required:**"
            )

            for item in requirement.evidence_required:

                st.write(
                    f"- {item}"
                )


            st.caption(
                f"Source: {requirement.source_document} "
                f"| Page: {requirement.source_page}"
            )


    # =================================================
    # EVIDENCE MATCHING
    # =================================================

    st.header("2. Evidence Matching")

    for match in result["evidence_matches"]:

        if match.status == "SATISFIED":

            st.success(
                f"{match.requirement_id}: SATISFIED"
            )

        elif match.status == "NOT_SATISFIED":

            st.error(
                f"{match.requirement_id}: NOT SATISFIED"
            )

        else:

            st.warning(
                f"{match.requirement_id}: UNKNOWN"
            )


        st.write(
            match.reasoning
        )


        if match.evidence:

            st.write(
                "**Supporting Evidence:**"
            )

            for evidence in match.evidence:

                st.info(
                    f"{evidence.document} "
                    f"| Page {evidence.page}"
                )

                st.write(
                    evidence.text
                )

        else:

            st.caption(
                "No supporting evidence found."
            )


    # =================================================
    # GENERATED PRIOR AUTHORIZATION
    # =================================================

    st.header("3. Generated Prior Authorization")

    draft = result["draft"]


    st.subheader("Patient")

    st.write(
        draft.patient_id
    )


    st.subheader("Treatment")

    st.write(
        draft.treatment
    )


    st.subheader("Insurance Provider")

    st.write(
        draft.insurer
    )


    st.subheader("Diagnosis")

    st.write(
        draft.diagnosis
    )


    st.subheader("Clinical Justification")

    st.write(
        draft.clinical_justification
    )


    st.subheader("Previous Treatments")

    if draft.previous_treatments:

        for treatment_item in draft.previous_treatments:

            st.write(
                f"- {treatment_item}"
            )

    else:

        st.write(
            "No previous treatments documented."
        )


    # =================================================
    # MISSING INFORMATION
    # =================================================

    if draft.missing_information:

        st.warning(
            "Missing Information"
        )

        for item in draft.missing_information:

            st.write(
                f"- {item}"
            )


    # =================================================
    # VALIDATION
    # =================================================

    st.header("4. Validation")

    validation = result[
        "validation_result"
    ]


    if validation == "PASS":

        st.success(
            "✅ Validation passed"
        )

    else:

        st.warning(
            validation
        )


    # =================================================
    # DEBUG / WORKFLOW INFORMATION
    # =================================================

    with st.expander(
        "Developer Debug Information"
    ):

        st.write(
            "Request ID:",
            request_id
        )

        st.write(
            "Patient:",
            patient_id
        )

        st.write(
            "Treatment:",
            treatment
        )

        st.write(
            "Insurer:",
            insurer
        )

        st.write(
            "Patient chart:",
            patient_file.name
        )

        st.write(
            "Guideline:",
            guideline_file.name
        )

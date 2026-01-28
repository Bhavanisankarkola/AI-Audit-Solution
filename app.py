import streamlit as st
from pathlib import Path
import json

# Page configuration
st.set_page_config(
    page_title="AI Audit Assistant",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state [web:27]
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = False
if 'audit_results' not in st.session_state:
    st.session_state.audit_results = None
if 'document_count' not in st.session_state:
    st.session_state.document_count = 0

# Main page
st.title("🔍 AI Audit Assistant")
st.markdown("### Automated Compliance Auditing with RAG")

st.markdown("""
This tool helps you automatically audit organizational policies against compliance principles 
using AI-powered document analysis.

**How it works:**
1. **📄 Upload Documents**: Add your policy documents, SOPs, and directives
2. **🔍 Run Audit**: Select audit principles and execute the audit
3. **📊 View Results**: Review findings, evidence, and compliance status
4. **💾 Export**: Download results in JSON or Excel format
""")

# Quick stats
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Documents Uploaded", st.session_state.document_count)
with col2:
    status = "✅ Ready" if st.session_state.documents_processed else "⏳ Pending"
    st.metric("System Status", status)
with col3:
    results = "Available" if st.session_state.audit_results else "None"
    st.metric("Audit Results", results)

# Quick actions
st.markdown("### Quick Actions")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📤 Upload Documents", use_container_width=True):
        st.switch_page("pages/1_📄_Document_Management.py")
with col2:
    if st.button("▶️ Run Audit", use_container_width=True, 
                 disabled=not st.session_state.documents_processed):
        st.switch_page("pages/2_🔍_Run_Audit.py")
with col3:
    if st.button("📊 View Results", use_container_width=True,
                 disabled=st.session_state.audit_results is None):
        st.switch_page("pages/3_📊_View_Results.py")

# System info
with st.expander("ℹ️ System Information"):
    st.markdown("""
    - **LLM Model**: Llama 3.2 3B (Ollama - Local)
    - **Vector Database**: ChromaDB (Embedded)
    - **Embeddings**: all-MiniLM-L6-v2
    - **Processing**: Real-time RAG pipeline
    """)

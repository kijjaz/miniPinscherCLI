import streamlit as st
import pandas as pd
import io
import re
from engine import IFRAEngine
from pdf_generator import create_ifra_pdf
import datetime

# --- CONFIG & VSCODE MONO FONT ---
st.set_page_config(
    page_title="miniPinscher | Terminal",
    page_icon="🐕",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Engine
@st.cache_resource
def get_engine():
    return IFRAEngine()

engine = get_engine()

# --- TERMINAL CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

    /* Global Reset */
    .stApp {
        background-color: #0e0e0e !important;
        color: #00FF00 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Hide Streamlit Elements */
    header, footer {visibility: hidden !important;}
    [data-testid="stSidebar"], [data-testid="stDecoration"] {display: none !important;}
    
    /* Typography */
    h1, h2, h3, h4, p, div, span, label, button {
        font-family: 'JetBrains Mono', monospace !important;
        color: #00FF00 !important;
    }
    
    /* Input Fields */
    .stTextInput input, .stTextArea textarea, .stSelectbox, .stNumberInput input {
        background-color: #000000 !important;
        color: #00FF00 !important;
        border: 1px solid #333 !important;
    }
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #000000 !important;
        color: #00FF00 !important;
        border: 1px solid #333 !important;
    }

    /* Buttons (Menu Items) */
    div.stButton > button {
        background-color: #000000 !important;
        color: #00FF00 !important;
        border: 1px solid #00FF00 !important;
        border-radius: 0px !important;
        text-align: left !important;
        padding-left: 20px !important;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #00FF00 !important;
        color: #000000 !important;
        border-color: #00FF00 !important;
    }
    div.stButton > button:focus {
        background-color: #003300 !important;
        color: #00FF00 !important;
        border-color: #00FF00 !important;
    }

    /* Dataframes/Tables */
    [data-testid="stDataFrame"] {
        border: 1px solid #333 !important;
    }
    
    /* Custom ASCII Box */
    .ascii-box {
        font-family: 'JetBrains Mono', monospace;
        white-space: pre;
        line-height: 1.2;
        color: #00FF00;
        margin-bottom: 20px;
        overflow-x: hidden;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE NAVIGATION ---
if 'screen' not in st.session_state:
    st.session_state['screen'] = 'MENU'
if 'formula' not in st.session_state:
    st.session_state['formula'] = []
if 'last_result' not in st.session_state:
    st.session_state['last_result'] = None

# --- ASCII ART ---
# Simplified for Web (HTML parsing of the complex format is heavy, using a clean text version)
ASCII_LOGO = """
         █          █                          
        ███       ███                          
        █████     ██                           
        ████  ███  ██                          
        ████ ████████                          
         █ █████████████                       
        █████████████████                      
         ███████████████         █             
         █ ████████████ ██       █             
         █ █████████████        █              
         ████████████████      ████            
       ██ █████████           █████            
       ████ ██████████      ████████           
    ██████████ ███ ██████  ███ ████            
   ███████████████ █████████████████           
  ███████████████ ████████████████████         
  ████████████████ █████████ ████████          
 ██████████████████████                        
 ██████████████████████                        

 DISSOLVING MUSK KETONE FOREVER... .           
"""

ASCII_HEADER = """
╭───────────────────────────────────────╮
│ miniPinscher | IFRA Compliance Engine │
│ v2.6.2 | Aromatic Data Intelligence   │
╰───────────────────────────────────────╯
"""

# --- SCREENS ---

def show_menu():
    st.markdown(f'<div class="ascii-box">{ASCII_LOGO}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ascii-box">{ASCII_HEADER}</div>', unsafe_allow_html=True)
    
    st.write("Select an option:")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("1. 🧪 Compliance Check"):
            st.session_state['screen'] = 'CHECK'
            st.rerun()
        if st.button("2. ➕ Formula Composer"):
            st.session_state['screen'] = 'COMPOSER'
            st.rerun()
        if st.button("3. 🔍 Search Database"):
            st.session_state['screen'] = 'SEARCH'
            st.rerun()
        if st.button("4. 📘 Manual / Help"):
            st.session_state['screen'] = 'HELP'
            st.rerun()
        if st.button("5. ❌ Exit / Reset"):
            st.session_state.clear()
            st.rerun()

def show_check():
    st.markdown("### 1. 🧪 Compliance Check (Batch Processing)")
    st.markdown("---")
    
    uploaded_file = st.file_uploader("Upload Formula (CSV/Excel)", type=['csv', 'xlsx'])
    
    dosage = st.number_input("Finished Product Dosage (%)", value=20.0, step=0.1)
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Simple Column Mapping
            cols = [str(c).lower() for c in df.columns]
            name_col = df.columns[0]
            amount_col = df.columns[1] if len(df.columns) > 1 else None
            
            # Heuristics
            for c in df.columns:
                if 'name' in c.lower() or 'material' in c.lower(): name_col = c
                if 'amount' in c.lower() or 'weight' in c.lower() or 'grams' in c.lower(): amount_col = c
            
            st.write(f"Map Columns: Name=`{name_col}`, Amount=`{amount_col}`")
            
            if st.button("🚀 Run Analysis"):
                formula = []
                for _, row in df.iterrows():
                    formula.append({'name': str(row[name_col]), 'amount': float(row[amount_col])})
                
                with st.spinner("Analyzing..."):
                    res = engine.calculate_compliance(formula, dosage)
                    st.session_state['last_result'] = res
                    st.session_state['screen'] = 'RESULT'
                    st.rerun()
                    
        except Exception as e:
            st.error(f"Error: {e}")
            
    st.markdown("---")
    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

def show_result():
    res = st.session_state['last_result']
    if not res:
        st.error("No results found.")
        if st.button("Back"): 
            st.session_state['screen'] = 'MENU'
            st.rerun()
        return

    st.markdown("### 📊 Compliance Report")
    
    if res['is_compliant']:
        st.success("✅ PASSED Category 4")
    else:
        st.error("❌ FAILED Category 4")
        
    st.markdown(f"**Max Safe Dosage:** `{round(res['max_safe_dosage'], 4)}%`")
    
    # Simple Table
    results = pd.DataFrame(res['results'])
    # Filter useful cols
    disp = results[['standard_name', 'concentration', 'limit', 'ratio', 'pass']]
    st.dataframe(disp, use_container_width=True)
    
    if st.button("📥 Download PDF Certificate"):
        # Placeholder for PDF Logic
        pass
        
    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

def show_composer():
    st.markdown("### 2. ➕ Formula Composer")
    st.info("Interactive Composer Logic Here (Simplified for Terminal View)")
    
    # Terminal-style text input for formula
    txt = st.text_area("Enter Formula (Name, Amount)", height=300, help="Format: Rose Oil, 10\nJasmine, 5")
    
    if st.button("Analyze Input"):
         # Parse text
         lines = txt.strip().split('\n')
         formula = []
         for l in lines:
             parts = l.split(',')
             if len(parts) >= 2:
                 formula.append({'name': parts[0].strip(), 'amount': float(parts[1].strip())})
         
         if formula:
             res = engine.calculate_compliance(formula, 20.0) # Default 20%
             st.session_state['last_result'] = res
             st.session_state['screen'] = 'RESULT'
             st.rerun()
    
    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

def show_search():
    st.markdown("### 3. 🔍 Search Database")
    q = st.text_input("Enter search term:")
    if q:
        matches = [k for k in engine.contributions_data.keys() if q.lower() in k.lower()]
        st.write(f"Found {len(matches)} matches:")
        for m in matches[:10]:
            st.markdown(f"- `{m}`")
            
    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

def show_help():
    st.markdown("### 4. 📘 Manual")
    st.markdown("""
    **miniPinscher Terminal Help**
    
    - **Compliance Check**: Upload CSV to check against IFRA 51st.
    - **Formula Composer**: Type simple formulas to check quickly.
    - **Search**: Find ingredients in the index.
    
    *Press 'Back to Menu' to return.*
    """)
    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

# --- MAIN ROUTER ---

if st.session_state['screen'] == 'MENU':
    show_menu()
elif st.session_state['screen'] == 'CHECK':
    show_check()
elif st.session_state['screen'] == 'COMPOSER':
    show_composer()
elif st.session_state['screen'] == 'SEARCH':
    show_search()
elif st.session_state['screen'] == 'RESULT':
    show_result()
elif st.session_state['screen'] == 'HELP':
    show_help()

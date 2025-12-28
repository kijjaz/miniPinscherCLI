import streamlit as st
import pandas as pd
import io
from engine import IFRAEngine
from fpdf import FPDF
import datetime
from pdf_generator import create_ifra_pdf

# Page Config
st.set_page_config(
    page_title="miniPinscher | IFRA 51st Compliance",
    page_icon="🐕",
    layout="wide"
)

# Initialize Engine
@st.cache_resource
def get_engine():
    return IFRAEngine()

engine = get_engine()

# --- CSS STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

    html, body, [class*="css"]  {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    code {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* --- TERMINAL THEME OVERRIDES --- */
    
    /* Main Background */
    .stApp {
        background-color: #0e0e0e !important;
        color: #00FF00 !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1e1e1e !important;
        border-right: 1px solid #333 !important;
    }
    [data-testid="stSidebar"] * {
        color: #00FF00 !important;
    }

    /* Text Elements */
    h1, h2, h3, p, div, span, label {
        color: #00FF00 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Inputs & Widgets */
    .stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"], .stNumberInput input {
        background-color: #000000 !important;
        color: #00FF00 !important;
        border: 1px solid #00FF00 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Buttons */
    .stButton button {
        background-color: #000000 !important;
        color: #00FF00 !important;
        border: 1px solid #00FF00 !important;
        font-family: 'JetBrains Mono', monospace !important;
        text-transform: uppercase;
    }
    .stButton button:hover {
        background-color: #00FF00 !important;
        color: #000000 !important;
        border-color: #00FF00 !important;
    }
    
    /* Sliders */
    [data-baseweb="slider"] * { 
        color: #00FF00 !important; 
    }
    
    /* Tables/Dataframes */
    [data-testid="stDataFrame"] {
        border: 1px solid #333 !important;
    }

    /* Custom Cards */
    .report-card {
        padding: 20px;
        border-radius: 0px;
        margin-bottom: 20px;
        border: 1px solid #ff0000;
        background-color: #000000;
        color: #ff0000 !important;
        font-family: 'JetBrains Mono', monospace;
    }
    .pass-card {
        border-color: #00FF00;
        color: #00FF00 !important;
    }
    
    /* Metric Cards */
    [data-testid="stMetric"] {
        background-color: #000000 !important;
        padding: 15px;
        border-radius: 0px;
        border: 1px solid #00FF00 !important;
        color: #00FF00 !important;
        font-family: 'JetBrains Mono', monospace;
    }
    [data-testid="stMetricLabel"] {
        color: #00FF00 !important;
        opacity: 0.8;
    }
    [data-testid="stMetricValue"] {
        color: #00FF00 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.title("🐕 miniPinscher | IFRA Compliance Engine")
st.caption("v2.3 | Powered by Aromatic Data Intelligence | 51st Amendment (Category 4)")


# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Application Settings")
    dosage = st.slider("Finished Product Dosage (%)", 0.1, 100.0, 20.0, step=0.1, help="The concentration of the concentrate in your final product (e.g., 20% for EDP).")
    
    st.divider()
    st.info("💡 **Tip**: Enter your formula in grams or parts. The engine automatically scales everything based on the dosage above.")
    
    if st.button("Reset Session"):
        st.session_state.clear()
        st.rerun()

# --- INPUT SECTION ---
tabs = st.tabs(["📄 Batch Upload (CSV)", "⌨️ Quick Entry (Manual)", "🧪 Formula Composer", "🔍 Database Explorer"])

formula = []

with tabs[0]:
    uploaded_file = st.file_uploader("Upload your Formula (CSV or Excel)", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Show complete formula
            cols = df.columns.tolist()
            st.write("Full Formula Preview:")
            st.dataframe(df, width='stretch')
            
            name_col = st.selectbox("Material Name Column", cols, index=0 if 'name' in [c.lower() for c in cols] else 0)
            amount_col = st.selectbox("Amount Column", cols, index=1 if 'amount' in [c.lower() for c in cols] else (1 if len(cols) > 1 else 0))
            cas_col = st.selectbox("CAS Column (Optional)", ["None"] + cols, index=0)
            
            for _, row in df.iterrows():
                entry = {'name': row[name_col], 'amount': row[amount_col]}
                if cas_col != "None":
                    entry['cas'] = row[cas_col]
                formula.append(entry)
                
        except Exception as e:
            st.error(f"Error reading file: {e}")

with tabs[1]:
    # --- Example Loader ---
    EXAMPLE_VAL = (
        "Bergamot FCF oil Sicilian from PerfumersWorld, 15.0\n"
        "Lemon essential oil from PerfumersWorld, 5.0\n"
        "Rose Otto Fleuressence from PerfumersWorld, 3.0\n"
        "Jasmine Petal F-TEC from PerfumersWorld, 2.0\n"
        "Hedione from PerfumersWorld, 20.0\n"
        "Iso E Super from PerfumersWorld, 25.0\n"
        "Vertofix Couer from PerfumersWorld, 15.0\n"
        "Ethylene Brassylate from PerfumersWorld, 10.0\n"
        "Musk Ketone from PerfumersWorld, 4.8\n"
        "Alpha Damascone from PerfumersWorld, 0.1\n"
        "Butylated hydroxytoluene (bht) antioxidant from PerfumersWorld, 0.1"
    )
    
    if st.button("🧪 Load Complex Example (F-TEC & Furocoumarins)"):
        st.session_state['manual_input'] = EXAMPLE_VAL
        st.rerun()

    manual_input = st.text_area(
        "Paste Formula (Name, Amount)", 
        value=st.session_state.get('manual_input', ""),
        placeholder="Phenyl Ethyl Alcohol, 120\nHydroxycitronellal, 50.5\nLemon Oil, 10",
        height=300
    )
    
    if manual_input:
        st.session_state['manual_input'] = manual_input
        # Provide download for manual input too
        lines = manual_input.strip().split('\n')
        dl_data = []
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 2:
                try:
                    name = parts[0].strip()
                    amount = float(parts[1].strip())
                    dl_data.append({"Material Name": name, "Amount": amount})
                    formula.append({'name': name, 'amount': amount})
                except: pass
        
        if dl_data:
            st.download_button(
                label="📥 Download Formula (CSV)",
                data=pd.DataFrame(dl_data).to_csv(index=False),
                file_name="manual_formula.csv",
                mime="text/csv",
                key="dl_manual"
            )

with tabs[3]:
    st.subheader("🔍 Ingredient Lookup")
    search_query = st.text_input("Search Ingredients (Name or CAS)", placeholder="e.g. 106-22-9 or Rose").strip().lower()
    
    if search_query:
        # Search match candidates
        all_materials = engine.contributions_data
        matches = [k for k in all_materials.keys() if search_query in k or search_query in str(all_materials[k].get('name', '')).lower()]
        
        if matches:
            # Group keys by name to avoid duplicate names in dropdown
            name_to_keys = {}
            for k in matches:
                name = all_materials[k].get('name', k)
                if name not in name_to_keys:
                    name_to_keys[name] = []
                name_to_keys[name].append(k)
            
            # If multiple keys have same name, append the key in parentheses for clarity
            display_options = []
            option_to_key = {}
            for name, keys in name_to_keys.items():
                if len(keys) > 1:
                    for k in keys:
                        label = f"{name} ({k})"
                        display_options.append(label)
                        option_to_key[label] = k
                else:
                    label = name
                    display_options.append(label)
                    option_to_key[label] = keys[0]

            selected_option = st.selectbox("Select exact material match", display_options)
            selected_key = option_to_key[selected_option]
            
            # Display Breakdown
            mat = all_materials[selected_key]
            st.write(f"### {mat['name']}")
            st.write(f"**Key/CAS**: `{selected_key}`")
            
            constituents = mat.get('constituents', {})
            if constituents:
                c_df = pd.DataFrame([
                    {'Constituent': c_cas, 'Percentage (%)': c_val, 'Type': 'IFRA Standard' if c_cas in engine.cas_to_std_ids else 'Constituent'} 
                    for c_cas, c_val in constituents.items()
                ])
                st.dataframe(c_df.sort_values('Percentage (%)', ascending=False), width='stretch', hide_index=True)
                
                total_mass = sum(constituents.values())
                if total_mass < 90.0:
                    st.warning(f"⚠️ **Incomplete Data**: This material only totals {round(total_mass, 2)}% mass.")
                else:
                    st.success(f"✅ **Full Profile**: {round(total_mass, 2)}% mass accounted for.")
            else:
                st.info("No constituent breakdown available for this material.")
        else:
            st.error("No matches found in the database.")
    else:
        st.write("Enter a keyword above to explore the Aromatic Data Intelligence database.")

with tabs[2]:
    st.subheader("🧪 Interactive Formula Composer")
    st.info("Build your formula by selecting materials from the database. Use the 'Scale to Target' feature to normalize your formula (e.g. to 100%).")
    
    # Initialize Composer State
    if 'composer_data' not in st.session_state:
        st.session_state['composer_data'] = pd.DataFrame([
            {"Material Name": "Hedione from PerfumersWorld", "Amount": 10.0},
            {"Material Name": "Iso E Super from PerfumersWorld", "Amount": 15.0}
        ])

    # Scaling Controls
    current_total = st.session_state['composer_data']['Amount'].sum()
    st.write(f"**Current Total Mass**: `{round(current_total, 4)}` units")
    
    scale_col1, scale_col2, scale_col3 = st.columns([1, 1, 2])
    with scale_col1:
        scaling_mode = st.radio("Scaling Mode", ["Multiplier", "Scale to Total"], horizontal=True)
    
    with scale_col2:
        if scaling_mode == "Multiplier":
            factor = st.number_input("Multiplier", value=1.0, min_value=0.0001, step=0.1)
        else:
            target_total = st.number_input("Target Total", value=100.0, min_value=0.1, step=10.0)
            factor = target_total / current_total if current_total > 0 else 1.0

    with scale_col3:
        st.write("") # Spacer
        if st.button("⚖️ Apply Scaling", use_container_width=True):
            st.session_state['composer_data']['Amount'] = st.session_state['composer_data']['Amount'] * factor
            st.success(f"Scaled by {round(factor, 4)}x")
            st.rerun()

    # Database for selectbox (Unique-ified names)
    all_material_names = sorted(list(set(engine.contributions_data[k].get('name', k) for k in engine.contributions_data)))
    
    # Interactive Table
    edited_df = st.data_editor(
        st.session_state['composer_data'],
        column_config={
            "Material Name": st.column_config.SelectboxColumn(
                "Material Name",
                help="Search and select from the ADI Database",
                options=all_material_names,
                required=True,
            ),
            "Amount": st.column_config.NumberColumn(
                "Amount (g/parts)",
                min_value=0.0,
                format="%.6f",
                required=True
            ),
        },
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="composer_editor"
    )
    
    # Update Session State and check for changes
    if not edited_df.equals(st.session_state.get('composer_data')):
        st.session_state['composer_data'] = edited_df
        
        # Sync to Manual Input automatically
        sync_lines = []
        for _, row in edited_df.iterrows():
            if row["Material Name"]:
                sync_lines.append(f"{row['Material Name']}, {row['Amount']}")
        st.session_state['manual_input'] = "\n".join(sync_lines)
        st.rerun()

    # Download Button
    if not edited_df.empty:
        st.download_button(
            label="📥 Download Formula (CSV)",
            data=edited_df.to_csv(index=False),
            file_name="composer_formula.csv",
            mime="text/csv",
            key="dl_composer"
        )
    
    # Populate the calculation formula
    for _, row in edited_df.iterrows():
        if row["Material Name"] and row["Amount"] > 0:
            formula.append({'name': row['Material Name'], 'amount': float(row['Amount'])})

# --- CALCULATION & REPORTING ---
if formula and st.button("🚀 Calculate Compliance", type="primary"):
    with st.spinner("Analyzing Formula..."):
        data = engine.calculate_compliance(formula, finished_dosage=dosage)
        
        # High Level Status
        col1, col2, col3 = st.columns(3)
        
        status_color = "red" if not data['is_compliant'] else "green"
        status_text = "!!! FAIL !!!" if not data['is_compliant'] else "✓ PASS"
        
        with col1:
            st.metric("Overall Status", status_text, delta=None, delta_color="inverse" if not data['is_compliant'] else "normal")
        with col2:
            st.metric("Critical Component", data['critical_component'] or "N/A")
        with col3:
            st.metric("Max Safe Dosage", f"{round(data['max_safe_dosage'], 4)}%")

        # Warnings for missing materials
        if data['unresolved_materials']:
            st.warning(f"⚠️ **Missing Items**: The following materials were not found in the database and were ignored: {', '.join(data['unresolved_materials'])}")
        
        # Data Integrity Warnings
        if data.get('data_integrity_warnings'):
            with st.expander("🛡️ **Data Integrity Warnings** (Incomplete Composition)"):
                st.write("The following materials have incomplete documentation in the database (total reported mass < 100%). Safety calculations for these rely on conservative defaults:")
                for w in data['data_integrity_warnings']:
                    st.write(f"- {w}")

        # Exceedance Message
        if not data['is_compliant']:
            st.error(f"🚨 **Safety Breach**: This formula at {dosage}% dosage exceeds IFRA limits. Recommended concentrate level: **{round(data['max_safe_dosage'], 4)}%**")
        else:
            st.success(f"✅ **Compliant**: This formula is safe for Category 4 at {dosage}% dosage.")
            
            # --- PDF CERTIFICATE GENERATION ---
            st.divider()
            st.subheader("📄 Generate IFRA Certificate")
            c1, c2, c3 = st.columns(3)
            with c1:
                prod_name = st.text_input("Product Name", value="My Fragrance")
            with c2:
                client_name = st.text_input("Client", value="Internal")
            with c3:
                date_str = st.text_input("Date", value=datetime.date.today().strftime("%Y-%m-%d"))
                
            # Generate automatically (always show download button)
            pdf_bytes = create_ifra_pdf(prod_name, client_name, date_str, dosage, data)
            st.download_button(
                label="📄 Download Certificate (PDF)",
                data=pdf_bytes,
                file_name=f"IFRA_Certificate_{prod_name.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )

        # Detailed Table
        st.subheader("Detailed Breakdown")
        results_df = pd.DataFrame(data['results'])
        
        # Format table
        results_df = results_df[['pass', 'standard_name', 'concentration', 'limit', 'ratio', 'exceedance_perc', 'sources']]
        results_df.columns = ['Status', 'Standard Name', 'Conc (%)', 'Limit', 'Ratio', 'Exceed %', 'Source']
        
        def highlight_fail(s):
            if not s['Status']:
                return ['background-color: #9c2b2b; color: white; font-weight: bold'] * len(s)
            return [''] * len(s)

        # Convert Limit to string to avoid Arrow serialization errors with mixed types
        results_df['Limit'] = results_df['Limit'].astype(str)

        st.dataframe(
            results_df.style.apply(highlight_fail, axis=1).format({
                'Status': lambda x: "✗" if not x else "✓",
                'Conc (%)': "{:.4f}",
                'Ratio': "{:.2f}",
                'Exceed %': lambda x: f"{x}%" if x > 0 else "-"
            }),
            width='stretch',
            hide_index=True
        )
        
        # Phototoxicity Section
        st.divider()
        p_data = data['phototoxicity']
        p_status = "✅ PASS" if p_data['pass'] else "🚨 FAIL"
        st.write(f"**Phototoxicity Check**: {p_status} | **Sum of Ratios**: {p_data['sum_of_ratios']} (Limit: 1.0)")
        
        # Download Report
        buffer = io.StringIO()
        # Mocking the print to capture report
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer
        engine.generate_report(formula, finished_dosage=dosage)
        sys.stdout = old_stdout
        
        st.download_button(
            label="📄 Download Full Certificate (Text)",
            data=buffer.getvalue(),
            file_name="ifra_compliance_report.txt",
            mime="text/plain"
        )

elif not formula:
    st.info("👋 Welcome! Please upload a formula or enter one manually to begin.")
    
    # Feature Showcase
    with st.expander("✨ Features Overview"):
        st.markdown("""
        - **Recursive Resolution**: Resolves mixtures and Schiff bases automatically.
        - **Smart Exemption**: Bergamot FCF and distilled oils are handled with IFRA-compliant logic.
        - **Automatic Scaling**: No need to calculate percentages; just enter grams.
        - **Phototoxicity Focus**: Industry-standard Sum of Ratios calculation.
        """)

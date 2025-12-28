import streamlit as st
import pandas as pd
import re
from engine import IFRAEngine
from rich.console import Console
from rich.table import Table
from rich import box

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

# --- TERMINAL CSS & ANIMATION ---
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
    h1, h2, h3, h4, p, div, span, label, button, pre, code {
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
        transition: all 0.1s ease;
    }
    div.stButton > button:hover {
        background-color: #00FF00 !important;
        color: #000000 !important;
        border-color: #00FF00 !important;
    }
    div.stButton > button:focus {
        background-color: #00FF00 !important;
        color: #000000 !important;
    }

    /* Custom ASCII Box */
    .ascii-box {
        font-family: 'JetBrains Mono', monospace;
        white-space: pre;
        line-height: 1.1;
        margin-bottom: 20px;
        overflow-x: hidden;
    }
    
    /* RICH OUTPUT CONTAINER */
    pre {
        background-color: #0e0e0e !important;
        padding: 10px;
        border: 1px solid #333;
    }
    
    /* ANIMATIONS */
    @keyframes typing {
      from { width: 0 }
      to { width: 100% }
    }
    .typing-effect {
        overflow: hidden;
        white-space: nowrap;
        border-right: .15em solid orange; /* The cursor */
        animation: 
            typing 3.5s steps(40, end),
            blink-caret .75s step-end infinite;
        display: inline-block;
        color: #ff00ff; /* Magenta */
    }
    @keyframes blink-caret {
      from, to { border-color: transparent }
      50% { border-color: orange; }
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

# --- PARSING HELPERS ---
def parse_ansi_art(text):
    # Regex to find [#hex]content[/#hex]
    # Replace with <span style="color:hex">content</span>
    pattern = r'\[(#[a-fA-F0-9]{6})\](.*?)\[/#\1\]'
    
    # Recursive replacement for nested tags if any (though regex is simple here)
    # Python's re doesn't support recursive easily, but we can do a pass.
    # Actually, simplistic replacement:
    
    def replace_color(match):
        hex_color = match.group(1)
        content = match.group(2)
        return f'<span style="color:{hex_color}">{content}</span>'
    
    # Apply multiple times if needed, or stick to simple
    html = re.sub(pattern, replace_color, text)
    return html

# Load Raw Art
RAW_ART = """                                        
          [#2e2e2e]█[/#2e2e2e]          [#181818]█[/#181818]                  
         [#1e1e1c]█[/#1e1e1c][#cb6d27]█[/#cb6d27][#4b2f24]█[/#4b2f24]       [#1c1c1c]█[/#1c1c1c][#242424]█[/#242424][#5c3219]█[/#5c3219]                  
         [#96603a]█[/#96603a][#ca6925]█[/#ca6925][#a54515]█[/#a54515][#412f25]█[/#412f25][#1e201f]█[/#1e201f]     [#1e1e1e]█[/#1e1e1e][#7d3a10]█[/#7d3a10]                   
         [#c96d24]█[/#c96d24][#c76b22]█[/#c76b22][#a74818]█[/#a74818][#381803]█[/#381803]  [#2a2a2c]█[/#2a2a2c][#2c2c2c]█[/#2c2c2c][#303030]█[/#303030]  [#441a0a]█[/#441a0a][#5b3118]█[/#5b3118]                  
         [#b1642c]█[/#b1642c][#c25f28]█[/#c25f28][#240b06]█[/#240b06][#250000]█[/#250000] [#1a1a1a]█[/#1a1a1a][#1b1b1b]█[/#1b1b1b][#1c1c1c]█[/#1c1c1c][#1a1a18]█[/#1a1a18][#1b1d1c]█[/#1b1d1c][#1b1b1b]█[/#1b1b1b][#1b1b1b]█[/#1b1b1b][#202020]█[/#202020]                  
          [#3f2820]█[/#3f2820] [#1a1a1a]█[/#1a1a1a][#1a1a1a]█[/#1a1a1a][#1a242d]█[/#1a242d][#25363e]█[/#25363e][#3d3d3f]█[/#3d3d3f][#383838]█[/#383838][#3b3b3b]█[/#3b3b3b][#343434]█[/#343434][#383838]█[/#383838][#3b3b3b]█[/#3b3b3b][#3a3a3a]█[/#3a3a3a][#3b3b3b]█[/#3b3b3b][#283639]█[/#283639]               
         [#2a5132]█[/#2a5132][#1c7535]█[/#1c7535][#25a534]█[/#25a534][#2eb33c]█[/#2eb33c][#185128]█[/#185128][#77a0be]█[/#77a0be][#76c898]█[/#76c898][#5aec4b]█[/#5aec4b][#11751d]█[/#11751d][#98ee93]█[/#98ee93][#54eb46]█[/#54eb46][#5ce851]█[/#5ce851][#7def75]█[/#7def75][#56eb49]█[/#56eb49][#61ae66]█[/#61ae66][#1da01e]█[/#1da01e][#8ba2aa]█[/#8ba2aa]              
          [#171717]█[/#171717][#1b1b1b]█[/#1b1b1b][#1b1b1b]█[/#1b1b1b][#191b1a]█[/#191b1a][#101c28]█[/#101c28][#7cbbb3]█[/#7cbbb3][#18951f]█[/#18951f][#28ac25]█[/#28ac25][#2bb12a]█[/#2bb12a][#244e44]█[/#244e44][#171918]█[/#171918][#1c1c1c]█[/#1c1c1c][#1b1b1d]█[/#1b1b1d][#262626]█[/#262626][#052415]█[/#052415]         [#001600]█[/#001600]     
          [#171717]█[/#171717] [#543822]█[/#543822][#c86722]█[/#c86722][#814b25]█[/#814b25][#1c1c1a]█[/#1c1c1a][#1b1b1b]█[/#1b1b1b][#1b1b19]█[/#1b1b19][#1c1c1a]█[/#1c1c1a][#88552a]█[/#88552a][#c96622]█[/#c96622][#cb6922]█[/#cb6922][#8a552b]█[/#8a552b][#1a1a1a]█[/#1a1a1a] [#363837]█[/#363837][#6a6869]█[/#6a6869]       [#2d912e]█[/#2d912e]     
          [#141414]█[/#141414] [#171717]█[/#171717][#332012]█[/#332012][#ce6b27]█[/#ce6b27][#a34313]█[/#a34313][#ce6925]█[/#ce6925][#ca6723]█[/#ca6723][#cd6a26]█[/#cd6a26][#cc6a23]█[/#cc6a23][#cf6a26]█[/#cf6a26][#d06b27]█[/#d06b27][#cd6b24]█[/#cd6b24][#cc6b27]█[/#cc6b27][#672004]█[/#672004]        [#2ae22c]█[/#2ae22c]      
          [#141414]█[/#141414][#1b1b19]█[/#1b1b19][#1b1b1b]█[/#1b1b1b][#151515]█[/#151515][#57291c]█[/#57291c][#350700]█[/#350700][#53271c]█[/#53271c][#c86a2d]█[/#c86a2d][#883002]█[/#883002][#3b1300]█[/#3b1300][#532609]█[/#532609][#925d3e]█[/#925d3e][#8e5b3c]█[/#8e5b3c][#8a5239]█[/#8a5239][#250000]█[/#250000][#3d1000]█[/#3d1000]      [#9dd4d7]█[/#9dd4d7][#8bc5d3]█[/#8bc5d3][#87d6e5]█[/#87d6e5][#687474]█[/#687474]    
        [#4d5b64]█[/#4d5b64][#a7c4d6]█[/#a7c4d6] [#1c1c1e]█[/#1c1c1e][#1c1c1c]█[/#1c1c1c][#1d1f1e]█[/#1d1f1e][#1f1f1f]█[/#1f1f1f][#d06e25]█[/#d06e25][#c96a2a]█[/#c96a2a][#8e290b]█[/#8e290b][#8f2c0d]█[/#8f2c0d][#818a93]█[/#818a93]           [#c06c30]█[/#c06c30][#cf6a24]█[/#cf6a24][#7b441b]█[/#7b441b][#190100]█[/#190100][#1f0200]█[/#1f0200]    
        [#738390]█[/#738390][#edf8fc]█[/#edf8fc][#ffffff]█[/#ffffff][#eaf5fb]█[/#eaf5fb] [#161618]█[/#161618][#1a1a1a]█[/#1a1a1a][#352213]█[/#352213][#cf6c28]█[/#cf6c28][#cd6a26]█[/#cd6a26][#c86521]█[/#c86521][#171e24]█[/#171e24][#b8d0dc]█[/#b8d0dc][#63686b]█[/#63686b][#7b8996]█[/#7b8996]      [#60676d]█[/#60676d][#a5adaf]█[/#a5adaf][#954915]█[/#954915][#669db2]█[/#669db2][#95d098]█[/#95d098][#321d1a]█[/#321d1a][#845738]█[/#845738][#28150f]█[/#28150f]   
     [#0e1619]█[/#0e1619][#9ec6e0]█[/#9ec6e0][#dee9ef]█[/#dee9ef][#ffffff]█[/#ffffff][#9bacb4]█[/#9bacb4][#646462]█[/#646462][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#a2b9bf]█[/#a2b9bf] [#1c1c1c]█[/#1c1c1c][#765438]█[/#765438][#6b4c38]█[/#6b4c38] [#dfedf0]█[/#dfedf0][#fefefe]█[/#fefefe][#a6a6a6]█[/#a6a6a6][#9b9b9b]█[/#9b9b9b][#e1ecf0]█[/#e1ecf0][#6a7c88]█[/#6a7c88]  [#a3b2b7]█[/#a3b2b7][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff] [#c1f3f4]█[/#c1f3f4][#d9fef6]█[/#d9fef6][#a3e6df]█[/#a3e6df][#6f8f9e]█[/#6f8f9e]    
    [#8ba8ba]█[/#8ba8ba][#aecde1]█[/#aecde1][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#e2f6ff]█[/#e2f6ff][#3c3e3d]█[/#3c3e3d][#666f74]█[/#666f74][#525f68]█[/#525f68][#c7c5c6]█[/#c7c5c6][#ffffff]█[/#ffffff][#393939]█[/#393939][#1c1c1c]█[/#1c1c1c][#1b1b1b]█[/#1b1b1b] [#fefefe]█[/#fefefe][#6b6b6b]█[/#6b6b6b][#fefefe]█[/#fefefe][#feffff]█[/#feffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#f4fcff]█[/#f4fcff][#ffffff]█[/#ffffff][#878789]█[/#878789][#111c1e]█[/#111c1e][#6ce876]█[/#6ce876][#3fd33f]█[/#3fd33f][#03d305]█[/#03d305][#2be232]█[/#2be232][#03d407]█[/#03d407][#5caa78]█[/#5caa78]   
   [#4a5863]█[/#4a5863][#a2cae4]█[/#a2cae4][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ecf6f8]█[/#ecf6f8][#25333c]█[/#25333c][#b2b2b2]█[/#b2b2b2][#ffffff]█[/#ffffff][#364049]█[/#364049] [#a2a9af]█[/#a2a9af][#e9e9e9]█[/#e9e9e9][#b3b6bb]█[/#b3b6bb][#fefefe]█[/#fefefe][#dbeef5]█[/#dbeef5][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#a09ea1]█[/#a09ea1][#5fb183]█[/#5fb183][#26d226]█[/#26d226][#d3ffd2]█[/#d3ffd2][#05dc03]█[/#05dc03][#03d905]█[/#03d905][#25da2b]█[/#25da2b][#21d625]█[/#21d625][#03d905]█[/#03d905][#5bfa79]█[/#5bfa79][#0e1f26]█[/#0e1f26] 
   [#a7cce6]█[/#a7cce6][#e5f6fe]█[/#e5f6fe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#314c57]█[/#314c57][#feffff]█[/#feffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#f7ffff]█[/#f7ffff][#182023]█[/#182023][#dce6e8]█[/#dce6e8] [#c7e0e7]█[/#c7e0e7][#ffffff]█[/#ffffff][#fffeff]█[/#fffeff][#7f7f7f]█[/#7f7f7f][#a9cbe4]█[/#a9cbe4][#a4cce5]█[/#a4cce5][#aad0e7]█[/#aad0e7][#bcd3e3]█[/#bcd3e3][#a3c4d7]█[/#a3c4d7] [#69ccc7]█[/#69ccc7][#60e1a9]█[/#60e1a9][#5ddca7]█[/#5ddca7][#5ddca7]█[/#5ddca7][#5ddea6]█[/#5ddea6][#5fdea9]█[/#5fdea9][#5bd9a9]█[/#5bd9a9][#093444]█[/#093444]  
  [#a7becc]█[/#a7becc][#9ecae3]█[/#9ecae3][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#27353e]█[/#27353e][#9dcae1]█[/#9dcae1][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#f3fdff]█[/#f3fdff][#bdbbbe]█[/#bdbbbe][#474745]█[/#474745][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#9ecbe2]█[/#9ecbe2]                
  [#a2b8c6]█[/#a2b8c6][#a3c8e2]█[/#a3c8e2][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#8c9eac]█[/#8c9eac][#a2cae3]█[/#a2cae3][#dfedf6]█[/#dfedf6][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#bfbfc1]█[/#bfbfc1][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#fefefc]█[/#fefefc][#a2cae3]█[/#a2cae3]                
"""
COLORED_ART = parse_ansi_art(RAW_ART)

# --- SCREENS ---
def show_menu():
    st.markdown(f'<div class="ascii-box">{COLORED_ART}</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <span class="typing-effect">DISSOLVING MUSK KETONE FOREVER...</span>
    </div>
    """, unsafe_allow_html=True)
    
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
    st.markdown("### 1. 🧪 ANSI Compliance Report")
    st.markdown("---")
    
    uploaded_file = st.file_uploader("Upload Formula (CSV/Excel)", type=['csv', 'xlsx'])
    dosage = st.number_input("Finished Product Dosage (%)", value=20.0, step=0.1)
    
    if uploaded_file and st.button("🚀 Run Analysis"):
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Simple Column Mapping
            cols = [str(c).lower() for c in df.columns]
            name_col = df.columns[0]
            amount_col = df.columns[1] if len(df.columns) > 1 else None
            for c in df.columns:
                if 'name' in c.lower() or 'material' in c.lower(): name_col = c
                if 'amount' in c.lower() or 'weight' in c.lower(): amount_col = c

            formatted_formula = []
            for _, row in df.iterrows():
                formatted_formula.append({'name': str(row[name_col]), 'amount': float(row[amount_col])})
            
            with st.spinner("Analyzing..."):
                res = engine.calculate_compliance(formatted_formula, dosage)
                
                # --- RICH CONSOLE CAPTURE ---
                console = Console(record=True, force_terminal=True, color_system="truecolor", width=120)
                
                # Title
                status = "[bold green]PASS[/bold green]" if res['is_compliant'] else "[bold red]FAIL[/bold red]"
                console.print(f"Compliance Status: {status}")
                console.print(f"Max Safe Dosage: [cyan]{round(res['max_safe_dosage'], 4)}%[/cyan]\n")
                
                # Table
                table = Table(title="Restricted Materials Breakdown", box=box.SIMPLE)
                table.add_column("Status", justify="center")
                table.add_column("Material / Standard", style="cyan")
                table.add_column("Conc (%)", justify="right")
                table.add_column("Limit", justify="right")
                table.add_column("Ratio", justify="right")
                table.add_column("Exceed %", justify="right", style="red")
                table.add_column("Sources", style="dim", max_width=30)
                
                restricted = [r for r in res['results'] if r['limit'] != 'Specification' and r['limit'] is not None]
                restricted.sort(key=lambda x: x['ratio'], reverse=True)
                
                for r in restricted:
                    if not r['pass'] or r['concentration'] > 0.001:
                        icon = "✅" if r['pass'] else "❌"
                        style = "dim" if r['pass'] else "bold white on red"
                        table.add_row(
                            icon, 
                            str(r['standard_name'])[:30], 
                            f"{r['concentration']:.4f}", 
                            str(r['limit']), 
                            f"{r['ratio']:.2f}",
                            f"{r['exceedance_perc']}%" if r['exceedance_perc'] > 0 else "-",
                            str(r.get('sources', '-')),
                            style=style
                        )
                
                console.print(table)
                
                # Export HTML
                html_out = console.export_html(inline_styles=True, code_format="<pre>{code}</pre>")
                
                st.session_state['last_html'] = html_out
                st.session_state['screen'] = 'RESULT'
                st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
            
    st.markdown("---")
    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

def show_result():
    if 'last_html' in st.session_state:
        st.markdown(st.session_state['last_html'], unsafe_allow_html=True)
    else:
        st.error("No result data.")
        
    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

def show_composer():
    st.markdown("### 2. ➕ Formula Composer (Simple)")
    txt = st.text_area("Enter Formula (Name, Amount)", height=300, help="Format: Rose Oil, 10")
    if st.button("Calculate"):
        # (Simplified logic similar to check)
        pass
    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

def show_search():
    st.markdown("### 3. 🔍 Search Database")
    q = st.text_input("Enter search term:")
    if q:
        matches = [k for k in engine.contributions_data.keys() if q.lower() in k.lower()]
        console = Console(record=True, force_terminal=True, width=100)
        table = Table(title=f"Search Results: {q}", box=box.SIMPLE)
        table.add_column("Material Name", style="green")
        for m in matches[:20]:
            table.add_row(m)
        console.print(table)
        st.markdown(console.export_html(inline_styles=True, code_format="<pre>{code}</pre>"), unsafe_allow_html=True)

    if st.button("« Back to Menu"):
        st.session_state['screen'] = 'MENU'
        st.rerun()

def show_help():
    st.markdown("### 4. 📘 Manual")
    st.write("Terminal Help...")
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

import json
import os
import sys
import random
import pandas as pd
import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich import box
import questionary
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.formatted_text import HTML

from engine import IFRAEngine
from pdf_generator import create_ifra_pdf

console = Console()
engine = IFRAEngine()
CONFIG_FILE = "config.json"

class ConfigManager:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            console.print(f"[red]Failed to save config: {e}[/red]")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

config = ConfigManager()

def clear_screen():
    console.clear()

def print_header():
    console.print(Panel.fit(
        "[bold cyan]miniPinscher[/bold cyan] | [yellow]IFRA Compliance Engine[/yellow]\n"
        "[dim]v2.6.2 | Aromatic Data Intelligence[/dim]",
        box=box.ROUNDED,
        border_style="cyan"
    ))

def load_formula(file_path):
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            console.print("[red]Unsupported file format. Please use CSV or Excel.[/red]")
            return None
        
        # Normalize columns - simple heuristic
        cols = [c.lower() for c in df.columns]
        
        name_col = next((c for c in df.columns if 'name' in c.lower()), df.columns[0])
        # Try to find 'amount', 'weight', 'mass', 'grams'
        amount_col = next((c for c in df.columns if any(x in c.lower() for x in ['amount', 'weight', 'mass', 'gram'])), df.columns[1] if len(df.columns) > 1 else None)
        
        if not amount_col:
             console.print("[red]Could not identify an 'Amount' column automatically. Please ensure one column header contains 'amount', 'weight', or 'grams'.[/red]")
             return None

        formula = []
        for _, row in df.iterrows():
             formula.append({'name': str(row[name_col]), 'amount': float(row[amount_col])})
        
        return formula, os.path.basename(file_path)

    except Exception as e:
        console.print(f"[red]Error loading file: {e}[/red]")
        return None, None

def show_results(data, dosage):
    # Summary Panel
    status = "[bold green]PASS[/bold green]" if data['is_compliant'] else "[bold red]FAIL[/bold red]"
    
    summary_text = f"""
    Overall Status: {status}
    Finished Dosage: {dosage}%
    Max Safe Dosage: {round(data['max_safe_dosage'], 4)}%
    Critical Component: {data['critical_component'] if data['critical_component'] else 'None'}
    Phototoxicity: {'[green]PASS[/green]' if data['phototoxicity']['pass'] else '[red]FAIL[/red]'} (Sum: {data['phototoxicity']['sum_of_ratios']})
    """
    
    console.print(Panel(summary_text, title="Compliance Summary", expand=False))

    # Details Table
    table = Table(title="Restricted Materials Breakdown", box=box.SIMPLE)
    table.add_column("Status", justify="center")
    table.add_column("Material / Standard", style="cyan")
    table.add_column("Conc (%)", justify="right")
    table.add_column("Limit", justify="right")
    table.add_column("Ratio", justify="right")
    table.add_column("Sources", style="dim", max_width=40)

    restricted = [r for r in data['results'] if r['limit'] != 'Specification' and r['limit'] is not None]
    restricted.sort(key=lambda x: x['ratio'], reverse=True)

    for r in restricted:
        # Show all failing, or anything with significant concentration
        if not r['pass'] or r['concentration'] > 0.001:
            status_icon = "✅" if r['pass'] else "❌"
            limit_display = str(r['limit'])
            exceed_display = f"{r['exceedance_perc']}%" if r['exceedance_perc'] > 0 else "-"
            
            style = "dim" if r['pass'] else "bold white on red"
            
            table.add_row(
                status_icon,
                str(r['standard_name'])[:40],
                f"{r['concentration']:.4f}",
                limit_display,
                f"{r['ratio']:.2f}",
                exceed_display,
                str(r.get('sources', '-')),
                style=style
            )

    console.print(table)
    
    if data['unresolved_materials']:
        console.print(f"\n[yellow]⚠️  Unresolved Materials ({len(data['unresolved_materials'])}):[/yellow] {', '.join(data['unresolved_materials'][:5])}...")

def run_compliance_check():
    clear_screen()
    print_header()
    console.print("[bold]Run Compliance Check[/bold]\n")
    
    last_file = config.get("last_formula_path", "")
    default_prompt = f" (default: {last_file})" if last_file else ""
    
    # Use questionary for path completion (Tab key support!)
    file_path = questionary.path(
        HTML(f"📂 Drop your formula file here (or type <style fg='magenta'>'example'</style>){default_prompt}"),
        default=last_file
    ).ask()
    
    if not file_path: return
    file_path = file_path.strip().strip("'").strip('"')
    
    if file_path.lower() == 'example':
        # Prefer complex formula if available
        if os.path.exists("complex_perfume_formula.csv"):
            file_path = "complex_perfume_formula.csv"
        elif os.path.exists("example_formula.csv"):
            file_path = "example_formula.csv"
        else:
            console.print("[red]No example files found![/red]")
            questionary.text("Press Enter...").ask()
            return

    if not os.path.exists(file_path):
        console.print("[red]File not found![/red]")
        questionary.text("Press Enter to continue...").ask()
        return
        
    # Save successful file path
    config.set("last_formula_path", file_path)

    formula, filename = load_formula(file_path)
    if not formula:
        questionary.text("Press Enter to return...").ask()
        return

    last_dosage = config.get("last_dosage", "20")
    dosage_str = questionary.text("💧 Finished Product Dosage (%):", default=str(last_dosage)).ask()
    if not dosage_str: return
    dosage = float(dosage_str)
    config.set("last_dosage", dosage)
    
    with console.status("[bold green]Calculating compliance...[/bold green]"):
        data = engine.calculate_compliance(formula, finished_dosage=dosage)
    
    show_results(data, dosage)
    
    # PDF Generation
    if questionary.confirm("\n📄 Generate PDF Certificate?", default=True).ask():
        default_prod = os.path.splitext(filename)[0].replace("_", " ").title() if filename else "My Product"
        
        # Load defaults from config
        last_client = config.get("last_client", "Internal Assessment")
        
        prod_name = questionary.text("Product Name:", default=default_prod).ask()
        client_name = questionary.text("Client Name:", default=last_client).ask()
        date_str = questionary.text("Date:", default=datetime.date.today().strftime("%Y-%m-%d")).ask()
        
        # Save preferences
        config.set("last_client", client_name)
        
        output_dir = "reports"
        os.makedirs(output_dir, exist_ok=True)
        
        # Safe filename
        safe_name = "".join([c for c in prod_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        output_path = os.path.join(output_dir, f"IFRA_Cert_{safe_name.replace(' ', '_')}.pdf")
        
        try:
            pdf_bytes = create_ifra_pdf(prod_name, client_name, date_str, dosage, data)
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            console.print(f"\n[bold green]✅ Report saved to: {output_path}[/bold green]")
        except Exception as e:
            console.print(f"\n[red]Failed to save PDF: {e}[/red]")
    
    questionary.text("\nPress Enter to return to menu...").ask()

def run_search():
    while True:
        clear_screen()
        print_header()
        console.print("[bold]Search Database[/bold] (Type 'exit' to go back)\n")
        
        query = questionary.text("🔍 Search for:").ask()
        if not query or query.strip().lower() in ['exit', 'quit']:
            break
        query = query.strip().lower()
            
        matches = [k for k in engine.contributions_data.keys() if query in k.lower() or query in str(engine.contributions_data[k].get('name', '')).lower()]
        
        if not matches:
             console.print("[red]No matches found.[/red]")
        else:
            table = Table(box=box.SIMPLE_HEAD)
            table.add_column("Name", style="green")
            table.add_column("key/CAS", style="dim")
            
            # Limit to 10
            for m in matches[:10]:
                name = engine.contributions_data[m].get('name', 'Unknown')
                table.add_row(name, m)
            
            console.print(table)
            if len(matches) > 10:
                console.print(f"[dim]...and {len(matches)-10} more[/dim]")
        
        questionary.text("\nPress Enter to continue...").ask()

def run_formula_composer():
    formula = []
    
    while True:
        clear_screen()
        print_header()
        console.print("[bold]🧪 Interactive Formula Composer[/bold]")
        console.print("[dim]Build a formula by searching and adding materials one by one.[/dim]\n")
        
        # Show Current Formula context
        if formula:
            table = Table(title=f"Current Formula ({len(formula)} items)", box=box.SIMPLE_HEAD)
            table.add_column("Material", style="cyan")
            table.add_column("Amount", justify="right", style="green")
            
            total_amt = 0
            for item in formula:
                table.add_row(item['name'], f"{item['amount']:.4f}")
                total_amt += item['amount']
            
            table.add_row("[bold]Total[/bold]", f"[bold]{total_amt:.4f}[/bold]", end_section=True)
            console.print(table)
            console.print("\n")

        # Action Prompt
        # Action Prompt
        action = questionary.select(
            "Action:",
            choices=["Add Material", "Edit Material", "Remove Material", "Check Compliance", "Save Formula", "Load Formula", "Load Example Formula", "Exit"],
            style=questionary.Style([('selected', 'fg:#673ab7 bold')])
        ).ask()
        
        if not action: break

        if action == "Exit":
            if not formula or questionary.confirm("Exit without saving?").ask():
                return
        
        elif action == "Save Formula":
            if not formula:
                console.print("[red]Formula is empty![/red]")
                questionary.text("Press Enter to continue...").ask()
                continue
            
            default_name = f"formula_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            fname = questionary.text("Filename to save:", default=default_name).ask()
            if not fname: fname = default_name
            if not fname.endswith('.csv'): fname += ".csv"
            
            try:
                pd.DataFrame(formula).to_csv(fname, index=False)
                console.print(f"[bold green]✅ Saved to {fname}[/bold green]")
            except Exception as e:
                console.print(f"[red]Error saving: {e}[/red]")
            Prompt.ask("Press Enter...")
            
        elif action == "Load Formula":
            if formula and not questionary.confirm("Current formula will be cleared. Continue?", default=False).ask():
                continue
                
            # List CSV/Excel files in current directory
            files = [f for f in os.listdir('.') if f.lower().endswith(('.csv', '.xlsx', '.xls'))]
            files.sort()
            
            if not files:
                 console.print("[red]No formula files found in current directory.[/red]")
                 questionary.text("Press Enter...").ask()
                 continue
            
            files.append("Cancel")
            
            fpath = questionary.select(
                "📂 Select Formula File:",
                choices=files,
                style=questionary.Style([('selected', 'fg:#2196f3 bold')])
            ).ask()
            
            if not fpath or fpath == "Cancel":
                continue
                
            res = load_formula(fpath)
            if res:
                loaded, _ = res
                if loaded:
                    formula = loaded
                    console.print(f"[bold green]✅ Loaded {len(formula)} ingredients![/bold green]")
            else:
                console.print("[red]Failed to load formula (invalid format?)[/red]")
            
            questionary.text("Press Enter...").ask()
            
        elif action == "Load Example Formula":
            if formula and not questionary.confirm("Current formula will be cleared. Continue?", default=False).ask():
                continue
                
            example_file = "complex_perfume_formula.csv"
            if os.path.exists(example_file):
                res = load_formula(example_file)
                if res:
                    loaded, _ = res
                    if loaded:
                        formula = loaded
                        console.print(f"[bold green]✅ Loaded Example Formula ({len(formula)} ingredients)![/bold green]")
                    else:
                        console.print("[red]Failed to load example formula.[/red]")
            else:
                console.print(f"[red]Example file '{example_file}' not found![/red]")
            
            questionary.text("Press Enter...").ask()

        elif action == "Remove Material":
            if not formula: continue
            
            # Create choices for removal
            choices = [f"{i+1}. {item['name']} ({item['amount']}g)" for i, item in enumerate(formula)]
            choices.append("Cancel")
            
            selection = questionary.select("Select material to remove:", choices=choices).ask()
            
            if selection and selection != "Cancel":
                idx = int(selection.split(".")[0]) - 1
                removed = formula.pop(idx)
                console.print(f"[yellow]Removed {removed['name']}[/yellow]")
            questionary.text("Press Enter...").ask()

        elif action == "Check Compliance":
            if not formula: continue
            
            last_dosage = config.get("last_dosage", "20")
            dosage_str = questionary.text("💧 Finished Product Dosage (%):", default=str(last_dosage)).ask()
            if not dosage_str: continue
            
            dosage = float(dosage_str)
            config.set("last_dosage", dosage)
            
            with console.status("[bold green]Calculating compliance...[/bold green]"):
                data = engine.calculate_compliance(formula, finished_dosage=dosage)
            
            show_results(data, dosage)
            questionary.text("\nPress Enter to continue editing...").ask()

        elif action == "Edit Material":
            if not formula: continue
            
            choices = [f"{i+1}. {item['name']} ({item['amount']}g)" for i, item in enumerate(formula)]
            choices.append("Cancel")
            
            selection = questionary.select("Select material to edit:", choices=choices).ask()
            
            if selection and selection != "Cancel":
                idx = int(selection.split(".")[0]) - 1
                item = formula[idx]
                
                new_amt_str = questionary.text(f"⚖️ New Amount (g) for {item['name']}:", default=str(item['amount'])).ask()
                if new_amt_str:
                    try:
                        new_amt = float(new_amt_str)
                        formula[idx]['amount'] = new_amt
                        console.print(f"[green]Updated {item['name']} to {new_amt}g[/green]")
                    except:
                        console.print("[red]Invalid amount[/red]")
                        time.sleep(1)

        elif action == "Add Material":
            # Pre-compute autocomplete list (Name + CAS)
            # This might be heavy if list is huge, but fine for ~3000 items
            if not getattr(run_formula_composer, "autocomplete_list", None):
                run_formula_composer.autocomplete_list = []
                
                # Deduplication logic: Map Name -> (Key, DisplayString)
                # We prefer keys that are codes (short) over keys that are just the name lowercased (long)
                seen_materials = {} 
                
                for k, v in engine.contributions_data.items():
                    name = v.get('name', k)
                    display_str = f"{name} | {k}"
                    
                    if name not in seen_materials:
                        seen_materials[name] = (k, display_str)
                    else:
                        # If existing key is long (likely a name) and new key is shorter (likely a CAS/Code), swap.
                        existing_k, _ = seen_materials[name]
                        if len(str(k)) < len(str(existing_k)):
                            seen_materials[name] = (k, display_str)
                            
                # Sort for better UX
                run_formula_composer.autocomplete_list = sorted([item[1] for item in seen_materials.values()])
            
            selection = questionary.autocomplete(
                "🔍 Search Material (Type to search):",
                choices=run_formula_composer.autocomplete_list,
                style=questionary.Style([('answer', 'fg:#f44336 bold')])
            ).ask()
            
            if not selection: continue
            
            # Parse selection "Name | CAS"
            parts = selection.split(" | ")
            selected_cas = parts[-1]
            selected_name = " | ".join(parts[:-1])
            
            amt_str = questionary.text(f"⚖️ Amount (g) for {selected_name}:").ask()
            if amt_str:
                try:
                    amt = float(amt_str)
                    formula.append({'name': selected_name, 'amount': amt})
                except:
                    console.print("[red]Invalid amount[/red]")
                    time.sleep(1)

def run_manual():
    clear_screen()
    print_header()
    
    manual_text = """
# 📘 miniPinscher User Manual

## 🚀 Quick Start
**miniPinscher** is your professional IFRA Compliance assistant. It helps you ensure your fragrance formulas are safe and compliant with the **51st Amendment (Category 4)**.

### 1. 🧪 Compliance Check (Batch Mode)
Use this if you already have a formula in Excel or CSV.
1. Select **Option 1** from the menu.
2. Drag and drop your file into the terminal.
   - *Tip: You can also type 'example' to load a demo formula.*
3. Enter your finished product dosage (e.g., **20%** for EDP).
4. The app will calculate safety limits and generate a **PDF Certificate**.

### 2. ➕ Formula Composer
Build a formula from scratch, right here in the terminal.
- **Add**: Search for materials by name (e.g., "Rose") or CAS.
- **Check**: Instantly verify if your current blend is compliant.
- **Save**: Export your work to a CSV file for later use.

### 3. 🔍 Database Search
Quickly look up any ingredient to see its IFRA limits and status.

## 💡 Key Features
- **Smart Memory**: The app remembers your Client Name, Dosage, and last used file.
- **Recursive Resolution**: It automatically calculates the content of restricted substances inside complex ingredients (like *Lemon Oil* containing *Citral*).
- **Phototoxicity**: It calculates the "Sum of Ratios" for phototoxic ingredients to ensure skin safety.

## ❓ FAQ
- **Q: My file won't load?**
  - A: Ensure your CSV/Excel has columns for `Name` and `Amount`.
- **Q: How do I exit?**
  - A: Select 'Exit' from the main menu or press `Ctrl+C`.

[dim]Powered by Aromatic Data Intelligence[/dim]
    """
    
    console.print(Markdown(manual_text))
    questionary.text("\nPress Enter to return to menu...").ask()

import time
import subprocess
import threading

def play_music():
    try:
        # Play in background, suppressor output
        # -v 0.3 approximates -18 LUFS for a loud chiptune source
        subprocess.run(["afplay", "theme.m4a", "-v", "0.3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

def show_welcome_animation():
    clear_screen()
    
    # Start Music (if enabled)
    if config.get("play_music", True):
        music_thread = threading.Thread(target=play_music)
        music_thread.daemon = True
        music_thread.start()
    
    # Load Dr. Pinscher art from file
    pinscher_art = ""
    if os.path.exists("ansi_art.txt"):
        with open("ansi_art.txt", "r") as f:
            # The art file seems to have literal \n stringified. 
            # We need to ensure it's treated as a raw string or cleaned.
            pinscher_art = f.read().replace("\\n", "\n").rstrip()
    else:
        # Fallback if file not found (or for testing without file)
        pinscher_art = """
[#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfffe]█[/#fdfffe][#fcfcfc]█[/#fcfcfc][#fdfdfd]█[/#fdfdfd][#fdfdfd]█[/#fdfdfd]
[#fefffd]█[/#fefffd][#fdfdfd]█[/#fdfdfd][#fcfcfc]█[/#fcfcfc][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefeff]█[/#fefeff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#feffff]█[/#feffff][#fdfdfd]█[/#fdfdfd][#fdfdfd]█[/#fdfdfd][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfffe]█[/#fdfffe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fffdfe]█[/#fffdfe][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fdfdfd]█[/#fdfdfd]
[#fefefe]█[/#fefefe][#fcfefd]█[/#fcfefd][#fefefe]█[/#fefefe][#fffdfe]█[/#fffdfe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfffe]█[/#fdfffe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#fefefe]█[/#fefefe][#fefffd]█[/#fefffd][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#feffff]█[/#feffff][#fffeff]█[/#fffeff][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#feffff]█[/#feffff][#fefefe]█[/#fefefe][#feffff]█[/#feffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fdfffe]█[/#fdfffe][#fcfcfc]█[/#fcfcfc][#fdfffe]█[/#fdfffe]
[#ffffff]█[/#ffffff][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fdfdfd]█[/#fdfdfd][#fdfdfd]█[/#fdfdfd][#fdfdfd]█[/#fdfdfd][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefeff]█[/#fefeff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefeff]█[/#fefeff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fcfcfc]█[/#fcfcfc][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#feffff]█[/#feffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fffffd]█[/#fffffd][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fcfcfc]█[/#fcfcfc][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd]
[#fdfdfb]█[/#fdfdfb][#fcfcfc]█[/#fcfcfc][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefc]█[/#fefefc][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefc]█[/#fefefc][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#fdfffe]█[/#fdfffe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#feffff]█[/#feffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#fefefe]█[/#fefefe][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fbfdfc]█[/#fbfdfc][#fefefc]█[/#fefefc][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fdfffc]█[/#fdfffc][#fdfffe]█[/#fdfffe][#fcfefd]█[/#fcfefd][#fdfdfd]█[/#fdfdfd][#fdfdfd]█[/#fdfdfd]
[#fffffd]█[/#fffffd][#fbfbfb]█[/#fbfbfb][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fcfcfc]█[/#fcfcfc][#fefefe]█[/#fefefe][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#fcfcfc]█[/#fcfcfc][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fffffd]█[/#fffffd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#040404]█[/#040404][#493630]█[/#493630][#000000]█[/#000000][#ffffff]█[/#ffffff][#fcfefb]█[/#fcfefb][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#332727]█[/#332727][#382829]█[/#382829][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fffffd]█[/#fffffd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefcfd]█[/#fefcfd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fcfefd]█[/#fcfefd][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe]
[#fffffd]█[/#fffffd][#fcfcfc]█[/#fcfcfc][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfffc]█[/#fdfffc][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fffffd]█[/#fffffd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#010101]█[/#010101][#d07e42]█[/#d07e42][#99573d]█[/#99573d][#000000]█[/#000000][#fcfefb]█[/#fcfefb][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#040404]█[/#040404][#292025]█[/#292025][#9f4b27]█[/#9f4b27][#3b2c27]█[/#3b2c27][#fdfdfd]█[/#fdfdfd][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fffffd]█[/#fffffd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefeff]█[/#fefeff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#feffff]█[/#feffff][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#fcfcfc]█[/#fcfcfc]
[#fffffd]█[/#fffffd][#fcfcfc]█[/#fcfcfc][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fffeff]█[/#fffeff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefc]█[/#fefefc][#fefefe]█[/#fefefe][#fcfcfc]█[/#fcfcfc][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#ffffff]█[/#ffffff][#fffeff]█[/#fffeff][#ffffff]█[/#ffffff][#fefefc]█[/#fefefc][#ffffff]█[/#ffffff][#020202]█[/#020202][#d17738]█[/#d17738][#d67c3d]█[/#d67c3d][#883821]█[/#883821][#000000]█[/#000000][#f3f3f3]█[/#f3f3f3][#f8f8f8]█[/#f8f8f8][#f6f6f6]█[/#f6f6f6][#f5f5f5]█[/#f5f5f5][#ffffff]█[/#ffffff][#38292c]█[/#38292c][#411911]█[/#411911][#d87f3b]█[/#d87f3b][#d77d3e]█[/#d77d3e][#8b4627]█[/#8b4627][#fffdfe]█[/#fffdfe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefc]█[/#fefefc][#fffffd]█[/#fffffd][#fcfcfc]█[/#fcfcfc][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#fefefc]█[/#fefefc][#fdfdfd]█[/#fdfdfd][#fffffd]█[/#fffffd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fcfefd]█[/#fcfefd][#fdfdfb]█[/#fdfdfb]
[#fffffd]█[/#fffffd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fcfefb]█[/#fcfefb][#fdfffe]█[/#fdfffe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#fffeff]█[/#fffeff][#fefefe]█[/#fefefe][#fdfffe]█[/#fdfffe][#feffff]█[/#feffff][#feffff]█[/#feffff][#fefefc]█[/#fefefc][#352724]█[/#352724][#9b5345]█[/#9b5345][#7b5f53]█[/#7b5f53][#4d3a33]█[/#4d3a33][#4c3932]█[/#4c3932][#4f3b34]█[/#4f3b34][#4c3933]█[/#4c3933][#4b3a33]█[/#4b3a33][#4b3a32]█[/#4b3a32][#322225]█[/#322225][#873120]█[/#873120][#a84e36]█[/#a84e36][#432616]█[/#432616][#020202]█[/#020202][#fffffd]█[/#fffffd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefc]█[/#fefefc][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#fcfefd]█[/#fcfefd][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fffffd]█[/#fffffd][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefffd]█[/#fefffd][#feffff]█[/#feffff][#fefefe]█[/#fefefe][#fdfffe]█[/#fdfffe][#fdfdfd]█[/#fdfdfd]
[#fefefe]█[/#fefefe][#fdfdfd]█[/#fdfdfd][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfffe]█[/#fdfffe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fdfffe]█[/#fdfffe][#fffdfe]█[/#fffdfe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#010101]█[/#010101][#f9fdfe]█[/#f9fdfe][#b8e4e7]█[/#b8e4e7][#000000]█[/#000000][#4f3b34]█[/#4f3b34][#503c35]█[/#503c35][#000000]█[/#000000][#f6feff]█[/#f6feff][#bfe6eb]█[/#bfe6eb][#000201]█[/#000201][#4c3b34]█[/#4c3b34][#4d3a33]█[/#4d3a33][#2d2123]█[/#2d2123][#010101]█[/#010101][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#feffff]█[/#feffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#fefefc]█[/#fefefc][#ffffff]█[/#ffffff][#fefefc]█[/#fefefc][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fefefe]█[/#fefefe][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#ffffff]█[/#ffffff][#fdfdfd]█[/#fdfdfd][#fffefc]█[/#fffefc][#fdfdfd]█[/#fdfdfd]
"""

    
    console.print("\n")
    
    with Live(console=console, refresh_per_second=4) as live:
        # Phase 1: Typing effect (Faster)
        txt = "INITIALIZING miniPinscher IFRA ENGINE..."
        for i in range(len(txt) + 1):
            live.update(Panel(f"[bold green]{txt[:i]}[/bold green]"))
            time.sleep(0.01) # Very fast typing
            
        time.sleep(0.2)

        # Phase 2: Animation Loop (Shortened)
        meme_texts = [
            "ODING ON ISO E SUPER...",
            "WAITING FOR MACERATION...",
            "DILUTING THE DAMASCENONE...",
            "REFORMULATING OAKMOSS...",
            "SMELLING 1000 STRIPS...",
            "CALIBRATING NOSE...",
            "BUYING YOUR OWN GCMS...",
            "ESCAPING ARKHAM TO FIGHT BATMAN...",
            "IT'S ALL AMBROXAN? ALWAYS HAS BEEN.",
            "EXTRACTING 2-NONENAL FROM GRANDMAS...",
            "DRINKING ARABICA ABSOLUTE...",
            "IF NOT FRIEND WHY FRIEND-SHAPED?",
            "SPILLING CADE OIL...",
            "SCENTING HOUSE FOR 2 MONTHS...",
            "GROWING 80 VARIETALS OF ROSES...",
            "USING VANILLA TINCTURE...",
            "WAITING FOR CIVET TO CALM DOWN...",
            "EXPLAINING 'CHEMIKILLZ' TO FAMILY...",
            "PRETENDING TO LIKE GALBANUM...",
            "CRYING OVER SANDALWOOD PRICES...",
            "FILTERING OUT BEAVER GLANDS...",
            "WATCHING THE MARKET CRASH...",
            "HIDING RECEIPT FROM SPOUSE...",
            "DREAMING OF AMBERGRIS ON BEACH...",
            "FIGHTING WITH THE SCENT PYRAMID...",
            "LOSING PIPETTE IN THE BOTTLE...",
            "ACCIDENTALLY TASTING BITREX...",
            "DISSOLVING MUSK KETONE FOREVER..."
        ]
        
        # Pick one random funny text to show for this session
        funny_text = random.choice(meme_texts)
        
        status = "Loading miniPinscher v2.6..." # Define status variable as per instruction's code edit
        
        for i in range(6):  # Much shorter loop (~1.5s)
            # Cycle dots or something so it feels alive
            status_text = f"{funny_text} {'.' * (i % 4)}"
            
            # Show art with text nicely centered below it in the panel
            combined_content = f"{pinscher_art}\n\n[bold yellow center]{status_text}[/bold yellow center]"
            
            content = Panel(combined_content, style="cyan on black", title="[bold]Dr. Pinscher[/bold]", width=50, padding=(0,0))
            
            live.update(content)
            time.sleep(0.25)
            
    time.sleep(0.5)

def run_main_menu_pt():
    choices = [
        "🧪 Compliance Check (Batch Processing)",
        "➕ Formula Composer (Interactive)",
        "🔍 Search Database",
        "📘 Manual / Help",
        "❌ Exit"
    ]
    # State
    selected_index = 0

    kb = KeyBindings()

    @kb.add('c-c')
    def exit_(event):
        event.app.exit(result=None)

    @kb.add('up')
    def up_(event):
        nonlocal selected_index
        selected_index = (selected_index - 1) % len(choices)

    @kb.add('down')
    def down_(event):
        nonlocal selected_index
        selected_index = (selected_index + 1) % len(choices)

    @kb.add('enter')
    def enter_(event):
        event.app.exit(result=choices[selected_index])

    # Instant Hotkeys
    @kb.add('1')
    def key_1(event): event.app.exit(result=choices[0])
    @kb.add('2')
    def key_2(event): event.app.exit(result=choices[1])
    @kb.add('3')
    def key_3(event): event.app.exit(result=choices[2])
    @kb.add('4')
    def key_4(event): event.app.exit(result=choices[3])
    @kb.add('5')
    def key_5(event): event.app.exit(result=choices[4])
    
    # ESC key - Do nothing in main menu per request
    @kb.add('escape')
    def esc_(event):
        pass

    def get_formatted_text():
        tokens = []
        tokens.append(('class:question', 'Select an option (Press 1-5):\n'))
        for i, choice in enumerate(choices):
            if i == selected_index:
                tokens.append(('class:pointer', ' » '))
                tokens.append(('class:selected', f"{i+1}. {choice}\n"))
            else:
                tokens.append(('class:text', '   '))
                tokens.append(('class:text', f"{i+1}. {choice}\n"))
        return tokens

    # Define minimal style to match questionary logic roughly
    from prompt_toolkit.styles import Style
    style = Style.from_dict({
        'question': 'bold',
        'selected': 'fg:#2196f3 bold',
        'pointer': 'fg:#673ab7 bold',
        'text': '',
    })

    layout = Layout(Window(FormattedTextControl(get_formatted_text)))
    app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
    return app.run()

def main():
    show_welcome_animation()
    
    while True:
        clear_screen()
        print_header()
        
        choice = run_main_menu_pt()
        
        if not choice: # Handle interruption
            sys.exit(0)

        if "Compliance Check" in choice:
            run_compliance_check()
        elif "Formula Composer" in choice:
            run_formula_composer()
        elif "Search Database" in choice:
            run_search()
        elif "Manual" in choice:
            run_manual()
        elif "Exit" in choice:
            console.print("Goodbye! 👋")
            sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\nExiting...")
        sys.exit(0)

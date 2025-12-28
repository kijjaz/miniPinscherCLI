# 🐕 miniPinscher | IFRA 51st Compliance Engine

A powerful, stylized terminal application (CLI) and engine for calculating perfume formula compliance against the IFRA 51st Amendment (Category 4).

## ✨ Features

-   **Interactive TUI**: Keyboard-driven menu with instant shortcuts (1-5), magenta-styled prompts, and Dr. Pinscher ANSI art.
-   **Advanced Search**: Smart deduplicated search for ingredients by name, CAS, or code.
-   **Compliance Checking**:
    -   **Recursive Resolution**: Automatically breaks down Schiff Bases (e.g., Aurantiol) and Naturals (e.g., Rose Otto) into their restricted constituents (Methyl Anthranilate, Citronellol, etc.).
    -   **Phototoxicity**: Calculates Sum-of-Ratios for phototoxic materials (Citrus oils) while intelligently exempting FCF/Distilled versions.
    -   **Source Tracking**: Detailed report shows exactly *which* ingredient contributed to a restricted limit.
-   **PDF Generation**: Exports professional compliance certificates.

## 🚀 Getting Started

### Prerequisites

-   Python 3.10+
-   `pip`

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-repo/miniPinscher.git
    cd miniPinscher
    ```

2.  **Set up Virtual Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

### Running the App

Run the wrapper script for the full experience:

```bash
./start_terminal_app.sh
```

Or run Python directly:

```bash
python cli.py
```

## 🧪 Testing

Run the verification suite to test core logic, deduplication, and persistence:

```bash
python verify_cli.py
```

## 📂 Project Structure

-   `cli.py`: Main Terminal User Interface (TUI) logic.
-   `engine.py`: Core calculation "brain" (shared with future Web App).
-   `contributions_optimized.json`: Database of material compositions (IFRA Annex).
-   `standards_optimized.json`: Database of IFRA limits (51st Amendment).
-   `complex_perfume_formula.csv`: Example formula file demonstrating advanced features.

## 📜 License

[Add License Here]

---
*Powered by Aromatic Data Intelligence | 2025*

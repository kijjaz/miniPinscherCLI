import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

# Mock engine before importing cli because cli initializes engine
sys.modules['engine'] = MagicMock()
from engine import IFRAEngine

# Mock rich console to avoid clutter
with patch('rich.console.Console.print'):
    import cli

class TestCLI(unittest.TestCase):
    def setUp(self):
        # Setup dummy engine data
        # Setup dummy engine data with DUPLICATES to test deduplication
        cli.engine.contributions_data = {
            "CAS-1": {"name": "Rose Oil", "ifra_class": "Class 4"},
            "rose oil": {"name": "Rose Oil", "ifra_class": "Class 4"}, # Duplicate name, longer key
            "CAS-2": {"name": "Jasmine Abs", "ifra_class": "Class 4"}
        }
        # Mock calculation result
        cli.engine.calculate_compliance.return_value = {
            "analysis": [], "is_compliant": True, "compliant": True, "total_usage": {"CAS-1": 10.0}
        }
        # Create dummy csv
        pd.DataFrame([{'name': 'Test', 'amount': 10}]).to_csv('test_formula.csv', index=False)

    def tearDown(self):
        if os.path.exists('test_formula.csv'):
            os.remove('test_formula.csv')
        if os.path.exists('saved_formula.csv'):
            os.remove('saved_formula.csv')

    @patch('rich.prompt.Prompt.ask')
    @patch('questionary.text')
    @patch('questionary.select')
    @patch('questionary.path')
    @patch('questionary.confirm')
    @patch('questionary.autocomplete')
    def test_compliance_check(self, mock_auto, mock_conf, mock_path, mock_sel, mock_text, mock_prompt):
        print("Testing Compliance Check...")
        
        def mock_q(val):
            m = MagicMock()
            m.ask.return_value = val
            return m
        
        # Files selection: "test_formula.csv"
        mock_sel.return_value = mock_q("test_formula.csv")
        
        # Dosage input
        # Also need to mock the "Press Enter" return pause
        mock_text.side_effect = [
            mock_q("20"), # Dosage
            mock_q("")    # Pause at end
        ]
        
        mock_conf.return_value = mock_q(False) # No PDF
        mock_prompt.return_value = ""

        try:
            cli.run_compliance_check()
            print("Compliance Check: SUCCESS")
        except Exception as e:
            print(f"Compliance Check: FAILED - {e}")
            raise e

    @patch('cli.run_main_menu_pt')
    @patch('rich.prompt.Prompt.ask')
    @patch('questionary.confirm')
    @patch('questionary.text')
    @patch('questionary.select')
    @patch('questionary.autocomplete')
    def test_formula_composer_add_save(self, mock_auto, mock_sel, mock_text, mock_conf, mock_prompt, mock_main_menu):
        print("Testing Formula Composer (Add & Save)...")
        
        def mock_q(val):
            m = MagicMock()
            m.ask.return_value = val
            return m

        # Mock the new main menu call: returns string "Formula Composer..."
        # But wait, logic calls `run_formula_composer()` directly inside the main loop based on this return.
        # This test calls `cli.run_formula_composer()` directly, so we just need to adapt mocks inside `run_formula_composer`.
        # Actually `run_formula_composer` *uses* `questionary.select` for the Action menu (Add/Save/Exit).
        # So we MUST keep mocking `questionary.select` for that internal menu.
        
        # Actions sequence: "Add Material" -> "Save Formula" -> "Exit"
        mock_sel.side_effect = [
            mock_q("Add Material"), 
            mock_q("Save Formula"),
            mock_q("Exit")
        ]
        
        # Autocomplete (Add Material) return "Rose Oil | CAS-1"
        mock_auto.return_value = mock_q("Rose Oil | CAS-1")
        
        # Text inputs: Amount(10), Save Filename, Press Enter (after save), Press Enter (pause?)
        mock_text.side_effect = [
            mock_q("10"), # Amount
            mock_q("saved_formula.csv"), # Filename
            mock_q("") # Press Enter after save
        ]
        
        mock_conf.return_value = mock_q(True)
        mock_prompt.return_value = ""
        
        try:
            cli.run_formula_composer()
            print("Composer Add/Save: SUCCESS")
            
            # Verify deduplication
            # We expect choices to contain "Rose Oil | CAS-1" and "Jasmine Abs | CAS-2"
            # But NOT "Rose Oil | rose oil" because "CAS-1" (len 5) < "rose oil" (len 8)
            args, kwargs = mock_auto.call_args
            choices = kwargs.get('choices', [])
            print(f"Autocomplete choices: {choices}")
            
            if "Rose Oil | CAS-1" in choices and "Rose Oil | rose oil" not in choices:
                 print("Deduplication: VERIFIED ✅")
            else:
                 print("Deduplication: FAILED ❌")
                 
        except Exception as e:
            print(f"Composer Add/Save: FAILED - {e}")
            raise e
            
    @patch('questionary.text')
    def test_search(self, mock_text):
        print("Testing Search...")
        
        def mock_q(val):
            m = MagicMock()
            m.ask.return_value = val
            return m
            
        # Search "Rose" -> Pause -> "exit"
        mock_text.side_effect = [
            mock_q("Rose"),
            mock_q(""), # Pause "Press Enter to continue"
            mock_q("exit")
        ]
        
        try:
            cli.run_search()
            print("Search: SUCCESS")
        except Exception as e:
            print(f"Search: FAILED - {e}")
            raise e

    @patch('cli.run_main_menu_pt')
    @patch('rich.prompt.Prompt.ask')
    @patch('questionary.confirm')
    @patch('questionary.text')
    @patch('questionary.select')
    def test_load_example(self, mock_sel, mock_text, mock_conf, mock_prompt, mock_main_menu):
        print("Testing Load Example...")
        
        def mock_q(val):
            m = MagicMock()
            m.ask.return_value = val
            return m
            
        # Create dummy example file
        mock_file = 'mock_complex_formula.csv'
        pd.DataFrame([{'name': 'Example Rose', 'amount': 100}]).to_csv(mock_file, index=False)
        
        # Sequence: "Load Example Formula" -> "Exit"
        # We need to ensure logic looks for this file. 
        # Since we can't easily change the hardcoded path in cli.py without more patching,
        # we will patch os.path.exists to return True for 'complex_perfume_formula.csv' 
        # but verify that the Load Action was attempted.
        # Actually, simpler: The CLI checks specific filenames. 
        # Let's just patch 'cli.load_formula' to return our dummy data regardless of filename.
        
        with patch('cli.load_formula') as mock_load:
            mock_load.return_value = ([{'name': 'Example Rose', 'amount': 100}], mock_file)
            
            mock_sel.side_effect = [
                mock_q("Load Example Formula"),
                mock_q("Exit")
            ]
            
            mock_text.return_value = mock_q("") # Press Enter pauses
            
            try:
                cli.run_formula_composer()
                print("Load Example: SUCCESS")
            except Exception as e:
                print(f"Load Example: FAILED - {e}")
                raise e
            finally:
                if os.path.exists(mock_file):
                    os.remove(mock_file)

if __name__ == '__main__':
    unittest.main()

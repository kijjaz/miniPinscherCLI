import json

class IFRAEngine:
    def __init__(self, standards_path='standards_optimized.json', contributions_path='contributions_optimized.json'):
        with open(standards_path, 'r') as f:
            std_data = json.load(f)
            self.standards_metadata = std_data['metadata']
            self.cas_to_std_ids = std_data['cas_mapping']
            
        with open(contributions_path, 'r') as f:
            self.contributions_data = json.load(f)
            
    def normalize_cas(self, cas):
        if not cas: return None
        return str(cas).strip().lower()

    def resolve_contributions(self, key, concentration, depth=0):
        """Recursively resolve NCS, Schiff Base, and User Material contributions."""
        if depth > 10: return {} # Safety limit
        
        contributions = {}
        target_key = self.normalize_cas(key)
        
        if target_key in self.contributions_data:
            entry_data = self.contributions_data[target_key]
            for const_key, const_perc in entry_data['constituents'].items():
                const_conc = concentration * (const_perc / 100.0)
                
                # If the constituent itself is an IFRA standard (e.g. an oil), add it
                if const_key in self.cas_to_std_ids:
                    contributions[const_key] = contributions.get(const_key, 0) + const_conc
                
                # Resolve nested components
                if const_key in self.contributions_data:
                    nested = self.resolve_contributions(const_key, const_conc, depth + 1)
                    for n_cas, n_conc in nested.items():
                        contributions[n_cas] = contributions.get(n_cas, 0) + n_conc
                elif const_key not in self.cas_to_std_ids:
                    # Only add as leaf if it wasn't already added as a standard
                    contributions[const_key] = contributions.get(const_key, 0) + const_conc
        return contributions

    def generate_report(self, formula, finished_dosage=100.0):
        """Generates a professional text-based report."""
        data = self.calculate_compliance(formula, finished_dosage)
        
        print("\n" + "="*85)
        print(" IFRA CATEGORY 4 COMPLIANCE REPORT (51st Amendment)")
        print("="*85)
        
        status = "PASS" if data['is_compliant'] else "!!! FAIL !!!"
        print(f"OVERALL STATUS: {status}")
        print(f"FINISHED PRODUCT CONCENTRATION: {finished_dosage}%")
        print(f"CRITICAL COMPONENT: {data['critical_component']}")
        
        if not data['is_compliant']:
            print(f"RECOMMENDED DOSAGE FOR PASS: {round(data['max_safe_dosage'], 4)}% (Concentrate)")
        else:
            print(f"MAX SAFE DOSAGE: {round(data['max_safe_dosage'], 4)}% (Currently Safe)")

        if data['unresolved_materials']:
            print("-" * 85)
            print("WARNING: THE FOLLOWING MATERIALS WERE NOT FOUND IN THE DATABASE:")
            for m in data['unresolved_materials']:
                print(f" - {m}")
            print("COLLECTIVE COMPLIANCE CANNOT BE FULLY GUARANTEED.")
            
        if data.get('data_integrity_warnings'):
            print("-" * 85)
            print("DATA INTEGRITY WARNINGS (Check for incomplete composition data):")
            for m in data['data_integrity_warnings']:
                print(f" - {m}")

        print("-" * 85)
        
        # Table Header
        print(f"{'Standard Name':<35} | {'Conc (%)':<10} | {'Limit':<8} | {'Ratio':<6} | {'Exceed %'}")
        print("-" * 85)
        
        for res in sorted(data['results'], key=lambda x: x['ratio'], reverse=True):
            p_mark = "✓" if res['pass'] else "✗"
            limit_str = f"{res['limit']}" if isinstance(res['limit'], (int, float)) else res['limit']
            ex_str = f"{res['exceedance_perc']}%" if res['exceedance_perc'] > 0 else "-"
            
            # Show all failing components, and safe components with > 0.0001% concentration
            if not res['pass'] or res['concentration'] > 1e-6:
                print(f"{p_mark} {res['standard_name'][:32]:<33} | {res['concentration']:<10.6f} | {limit_str:<8} | {res['ratio']:<6.2f} | {ex_str}")
            
        print("-" * 85)
        p_data = data['phototoxicity']
        p_status = "✓" if p_data['pass'] else "✗"
        p_ex = f"{p_data['exceedance_perc']}%" if p_data['exceedance_perc'] > 0 else "-"
        print(f"{p_status} PHOTOTOXICITY (Sum of Ratios): {p_data['sum_of_ratios']} (Limit: 1.0) | Exceed: {p_ex}")
        print("="*85 + "\n")

    def calculate_compliance(self, formula, finished_dosage=100.0):
        """
        formula: list of dicts {'name': str, 'cas': str, 'amount': float, 'concentration': float (optional)}
        finished_dosage: The concentration of the perfume oil in the final product (%)
        """
        # 0. Normalize formula to percentages of concentrate if amounts are provided
        normalized_formula = []
        total_amount = sum(float(entry.get('amount', 0)) for entry in formula)
        
        for entry in formula:
            new_entry = entry.copy()
            if 'amount' in entry and total_amount > 0:
                # Calculate % in concentrate
                perc_in_concentrate = (float(entry['amount']) / total_amount) * 100.0
                # Scale by finished product dosage
                final_conc = perc_in_concentrate * (finished_dosage / 100.0)
                new_entry['concentration'] = final_conc
            elif 'concentration' in entry:
                # Direct scaling if % was already provided
                new_entry['concentration'] = float(entry['concentration']) * (finished_dosage / 100.0)
            else:
                new_entry['concentration'] = 0.0
            normalized_formula.append(new_entry)

        # 1. Initialize Restricted Component Map
        # Key: CAS -> { 'total_conc': float, 'is_photo_exempt': bool, 'sources': { origin_name: conc } }
        restricted_components = {}
        unresolved_materials = []
        data_integrity_warnings = []
        
        # 2. Process normalized entries
        for entry in normalized_formula:
            cas = self.normalize_cas(entry.get('cas'))
            sku = self.normalize_cas(entry.get('sku'))
            name = entry.get('name', entry.get('Material Name', 'Unknown'))
            norm_name = self.normalize_cas(name)
            conc = float(entry['concentration'])
            
            # Smart Phototoxicity Exclusion (Heuristic)
            is_exempt = any(word in name.upper() for word in ["FCF", "DISTILLED", "TERPENELESS"])
            
            # Identify the best resolution key
            resolution_key = None
            if cas and (cas in self.contributions_data or cas in self.cas_to_std_ids):
                resolution_key = cas
            elif sku and (sku in self.contributions_data):
                resolution_key = sku
            elif norm_name and (norm_name in self.contributions_data):
                resolution_key = norm_name
            
            # Data Integrity Check (Sub-100% check)
            if resolution_key and resolution_key in self.contributions_data:
                c_data = self.contributions_data[resolution_key]
                c_sum = sum(c_data.get('constituents', {}).values())
                # If sum < 90% and name doesn't imply a dilution (e.g. "10% in")
                is_dilution = any(re_match in name.lower() for re_match in ["% in", "dilution", " (dil)"])
                if c_sum < 90.0 and not is_dilution:
                    data_integrity_warnings.append(f"{name} (Composition only totals {round(c_sum, 1)}%)")

            # Resolve
            found = False
            if cas and not resolution_key:
                if cas not in restricted_components: 
                    restricted_components[cas] = {'total_conc': 0.0, 'is_photo_exempt': is_exempt, 'sources': {}}
                restricted_components[cas]['total_conc'] += conc
                restricted_components[cas]['sources'][name] = restricted_components[cas]['sources'].get(name, 0.0) + conc
                restricted_components[cas]['is_photo_exempt'] = restricted_components[cas]['is_photo_exempt'] and is_exempt
                found = True
            elif resolution_key:
                found = True
                if resolution_key in self.contributions_data:
                    resolved = self.resolve_contributions(resolution_key, conc)
                    for r_cas, r_conc in resolved.items():
                        if r_cas not in restricted_components: 
                            restricted_components[r_cas] = {'total_conc': 0.0, 'is_photo_exempt': is_exempt, 'sources': {}}
                        restricted_components[r_cas]['total_conc'] += r_conc
                        restricted_components[r_cas]['sources'][name] = restricted_components[r_cas]['sources'].get(name, 0.0) + r_conc
                        restricted_components[r_cas]['is_photo_exempt'] = restricted_components[r_cas]['is_photo_exempt'] and is_exempt
                
                if resolution_key in self.cas_to_std_ids:
                    if resolution_key not in restricted_components: 
                        restricted_components[resolution_key] = {'total_conc': 0.0, 'is_photo_exempt': is_exempt, 'sources': {}}
                    restricted_components[resolution_key]['total_conc'] += conc
                    restricted_components[resolution_key]['sources'][name] = restricted_components[resolution_key]['sources'].get(name, 0.0) + conc
                    restricted_components[resolution_key]['is_photo_exempt'] = restricted_components[resolution_key]['is_photo_exempt'] and is_exempt
            
            if not found:
                unresolved_materials.append(name)
        
        # 3. Aggregate by Standard
        standard_aggregation = {}
        for cas, data in restricted_components.items():
            total_conc = data['total_conc']
            is_exempt = data['is_photo_exempt']
            sources = data['sources']
            
            if cas in self.cas_to_std_ids:
                std_ids = self.cas_to_std_ids[cas]
                for std_id in std_ids:
                    if std_id not in self.standards_metadata: continue
                    std = self.standards_metadata[std_id]
                    
                    # Heuristic for Citrus Oils sum-of-ratios
                    # If the source was FCF/Distilled, we skip PHOTOTOXICITY aggregation for this component
                    if is_exempt and 'PHOTOTOXICITY' in std['type'].upper():
                        continue 
                    
                    if std_id not in standard_aggregation:
                        standard_aggregation[std_id] = {
                            'id': std_id, 'name': std['name'], 'total_conc': 0.0,
                            'limit': std['limit_cat4'], 'type': std['type'],
                            'sources': {}
                        }
                    standard_aggregation[std_id]['total_conc'] += total_conc
                    for s_name, s_conc in sources.items():
                        standard_aggregation[std_id]['sources'][s_name] = standard_aggregation[std_id]['sources'].get(s_name, 0.0) + s_conc

        # 4. Phototoxicity (Sum of Ratios)
        phototoxic_ratios = []
        for std_id, data in standard_aggregation.items():
            if 'PHOTOTOXICITY' in data['type'].upper():
                limit = data['limit']
                if limit is not None and limit > 0:
                    ratio = data['total_conc'] / limit
                    phototoxic_ratios.append(ratio)
        
        sum_of_ratios = sum(phototoxic_ratios)
        phototoxicity_pass = sum_of_ratios <= 1.0

        # 5. Final Compliance results
        results = []
        is_compliant = True
        critical_component = None
        max_ratio = 1e-9 
        
        for std_id, data in standard_aggregation.items():
            conc = data['total_conc']
            limit = data['limit']
            
            if limit is None:
                ratio = 0.0
                pass_std = True
                display_limit = "Spec."
                exceedance = 0.0
            else:
                ratio = (conc / limit) if limit > 0 else (0 if conc == 0 else float('inf'))
                pass_std = conc <= limit + 1e-9
                display_limit = limit
                exceedance = max(0.0, (ratio - 1.0) * 100.0) if ratio > 1.0 else 0.0
            
            if not pass_std:
                is_compliant = False
            
            if ratio > max_ratio:
                max_ratio = ratio
                critical_component = data['name']
                
            # Format sources string (e.g. "Rose (0.01%), Jasmine (0.005%)")
            # Show all sources recorded for transparency (even trace amounts)
            source_list = [f"{s_name} ({round(s_conc, 6)}%)" for s_name, s_conc in data['sources'].items()]
            source_str = ", ".join(source_list) if source_list else "Inherited/Direct Addition"

            results.append({
                'standard_name': data['name'],
                'concentration': round(conc, 6),
                'limit': display_limit,
                'pass': pass_std,
                'ratio': round(ratio, 4),
                'exceedance_perc': round(exceedance, 2),
                'sources': source_str
            })
            
        if not phototoxicity_pass:
            is_compliant = False
            if sum_of_ratios > max_ratio:
                max_ratio = sum_of_ratios
                critical_component = "Phototoxicity (Sum of Ratios)"
            
        # The Max Safe Dosage is the dosage that would make the highest ratio equal exactly 1.0
        # If current max_ratio is 2.0 (Double the limit) at 20% dosage, 
        # then passing dosage is 20% / 2.0 = 10%.
        pass_dosage = (finished_dosage / max_ratio) if max_ratio > 1e-9 else 100.0

        return {
            'is_compliant': is_compliant,
            'results': results,
            'phototoxicity': {
                'sum_of_ratios': round(sum_of_ratios, 4),
                'pass': phototoxicity_pass,
                'exceedance_perc': round(max(0.0, (sum_of_ratios - 1.0) * 100.0), 2)
            },
            'critical_component': critical_component,
            'max_safe_dosage': pass_dosage,
            'finished_dosage': finished_dosage,
            'unresolved_materials': unresolved_materials,
            'data_integrity_warnings': data_integrity_warnings
        }

if __name__ == "__main__":
    engine = IFRAEngine()
    
    # --- COMPREHENSIVE STRESS TEST FORMULA ---
    # This formula exercises 10+ engine features simultaneously:
    # 1. Grams-to-% Normalization: Using absolute amounts
    # 2. Specification Handling: Linalool/Limonene (marked as Spec, skip limit)
    # 3. Recursive Resolution (Mixtures): Schiff Base (Aurantiol) & NCS
    # 4. Group Restrictions: Multiple Damascones (aggregated under Rose Ketones)
    # 5. Phototoxicity Sum-of-Ratios: Combined oils
    # 6. Smart FCF Exemption: Bergamot FCF is excluded from phototoxicity sum
    # 7. Intermediate Resolution: Lemon Oil phototoxicity AND chemicals are tracked
    # 8. Database Validation: "Mystery Material X" triggers missing warning
    # 9. Exceedance Reporting: Hydroxycitronellal set intentionally high
    # 10. Pass Dosage Calculation: Recommends concentrate limit for safety
    
    stress_test_formula = [
        # Chemical (Specification Only)
        {'name': 'Linalool Synthetic from PerfumersWorld', 'amount': 10.0},
        
        # Phototoxic Oil (Regular - Included in Sum-of-Ratios)
        {'name': 'Lemon Essential Oil from PerfumersWorld', 'amount': 5.0},
        
        # Phototoxic Oil (FCF - Exempt from Sum-of-Ratios via Smart Name Logic)
        {'name': 'Bergamot FCF oil Sicilian from PerfumersWorld', 'amount': 15.0},
        
        # Group Restriction (Group: Rose Ketones)
        {'name': 'Alpha Damascone from PerfumersWorld', 'amount': 0.1},
        {'name': 'Beta Damascone from PerfumersWorld', 'amount': 0.15},
        
        # Schiff Base (Mixture Resolution)
        {'name': 'Aurantiol - Methyl Anthranilate Schiffs Base from PerfumersWorld', 'amount': 2.0},
        
        # High restriction component (sensitizer)
        {'name': 'Hydroxycitronellal from PerfumersWorld', 'amount': 3.0},
        
        # Database Validation Test (Missing item)
        {'name': 'Mystery Material X (Not in DB)', 'amount': 1.0},
        
        # Data Integrity Test (Partial composition < 90%)
        {'name': 'Lavandin absolute from PerfumersWorld', 'amount': 2.0},
        
        # Other base materials
        {'name': 'Phenyl Ethyl Alcohol (PEA) from PerfumersWorld', 'amount': 13.65}
    ]
    
    print("\n" + "#"*85)
    print(" ENGINE STRESS TEST: VERIFYING ALL FEATURES")
    print("#"*85)

    # 1. Test at 100% (Concentrate)
    print("\n[TEST 1] PURE CONCENTRATE (100% Dosage)")
    engine.generate_report(stress_test_formula, finished_dosage=100.0)
    
    # 2. Test at 20% (Fine Fragrance)
    print("\n[TEST 2] EAU DE PARFUM (20.0% Dosage)")
    engine.generate_report(stress_test_formula, finished_dosage=20.0)

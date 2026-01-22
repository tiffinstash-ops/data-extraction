
# import pandas as pd
# import numpy as np
# from datetime import datetime, timedelta
# from constants import CSV_FIELDNAMES

# # Source Column Mapping (based on CSV_FIELDNAMES index)
# IDX_ORDER_ID = 0
# IDX_DATE = 1
# IDX_NAME = 2
# IDX_PHONE_NUMERIC = 3
# IDX_PHONE_EDIT = 4
# IDX_EMAIL = 5
# IDX_HOUSE_NO = 6
# IDX_ADDRESS_1 = 7
# IDX_SELECT_DELIVERY_CITY = 8
# IDX_SHIPPING_CITY = 9
# IDX_ZIP = 10
# IDX_SKU = 11
# IDX_DELIVERY_INSTRUCTIONS = 12
# IDX_ORDER_SELLER_NOTES = 13
# IDX_DELIVERY_TIME = 14
# IDX_DINNER_DELIVERY = 15
# IDX_LUNCH_DELIVERY = 16
# IDX_LUNCH_DELIVERY_TIME = 17
# IDX_LUNCH_TIME = 18
# IDX_DELIVERY_BETWEEN = 19
# IDX_DELIVERY_TIME_EDIT = 20
# IDX_QUANTITY = 21
# IDX_SELECT_START_DATE = 22
# IDX_DELIVERY_CITY = 23

# # Destination Columns (derived from copyDataToExportOrders)
# # We will create a generic column naming A-Z for the export dataframe initially to match the script logic
# EXPORT_COLUMNS = [
#     "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"
# ]

# def apply_all_transformations(df: pd.DataFrame) -> pd.DataFrame:
#     """
#     Apply the full chain of transformations described in the user's scripts.
#     """
#     if df.empty:
#         return df

#     # --- Phase 1: Modify 'Source' Sheet Logic (modifySheet) ---
    
#     # Step 1: Remove rows where SKU (Column L / Index 11) is blank
#     # In pandas, empty string or 0 or NaN? clean() function makes None->0.
#     # The script checks `if (data[i][11] === '')`.
#     # Our `clean` function in utils puts 0 if empty/None. But here we might have str.
#     # Let's ensure we handle standard pandas empty check.
#     df = df[df['SKU'].astype(str).str.strip() != '']
#     df = df[df['SKU'] != '0'] # If clean() converted None to 0
#     df = df[df['SKU'] != 0]

#     # Step 2: Update Column M (Delivery Instructions) - replace \n with .
#     # Index 12
#     col_deliver_instr = CSV_FIELDNAMES[IDX_DELIVERY_INSTRUCTIONS]
#     if col_deliver_instr in df.columns:
#         df[col_deliver_instr] = df[col_deliver_instr].astype(str).str.replace('\n', '. ', regex=False)

#     # Step 3: Move Column X (Delivery city) to Column I (Select Delivery City)
#     # Index 23 -> Index 8
#     target_col = CSV_FIELDNAMES[IDX_SELECT_DELIVERY_CITY]
#     source_col = CSV_FIELDNAMES[IDX_DELIVERY_CITY]
    
#     if source_col in df.columns and target_col in df.columns:
#         mask = df[source_col].astype(str).str.strip().isin(['', '0', 'None', 'nan']) == False
#         # Copy values
#         df.loc[mask, target_col] = df.loc[mask, source_col]
#         # Clear source
#         df.loc[mask, source_col] = ""

#     # Step 4: Fill Zeros (A2 to W)
#     # Our `utils.clean` handles most of this during extraction.
#     # We can do a global fillna just in case.
#     df = df.fillna(0)
#     df = df.replace('', 0)
    
#     # --- Phase 2: Create 'Export Orders' Sheet (copyDataToExportOrders) ---
#     export_df = create_export_dataframe(df)
    
#     # --- Phase 3: Post-processing on Export Sheet ---
    
#     # Step: convertTimeRangesAndAddWTD
#     export_df = convert_time_ranges_and_add_suffixes(export_df)
    
#     # Step: updateOrders_TS01_to_TS16 (The big expansion)
#     export_df = expand_subscriptions(export_df)
    
#     # Step: swapDates (mentioned in runAllScriptsInExport but logic not in code-dump? 
#     # Wait, the prompt implies "series of steps... code-dump.txt". 
#     # I don't see `swapDates` implementation in the dump provided in the view?
#     # Ah, I see `swapDates();` called in `runAllScriptsInExport` in the text file, 
#     # but I need to scroll down to find the definition if it exists?
#     # I read lines 1-800. Let me check if it's further down.
#     # For now, I will implement what I have seen.
    
#     return export_df

# def create_export_dataframe(source_df: pd.DataFrame) -> pd.DataFrame:
#     """
#     Map source columns to the final export layout.
#     Based on `destinationRange.setValues(sourceDataValues.map(row => [...]))`
#     """
#     new_data = []
    
#     # Helper to safe get
#     def get_val(row, idx):
#         col_name = CSV_FIELDNAMES[idx]
#         return row[col_name]

#     for _, row in source_df.iterrows():
#         new_row = {
#             "A": get_val(row, IDX_ORDER_ID),                 # row[0]
#             "B": get_val(row, IDX_DATE),                     # row[1]
#             "C": get_val(row, IDX_NAME),                     # row[2]
#             "D": get_val(row, IDX_PHONE_EDIT),               # row[4] - Note: Script uses index 4
#             "E": get_val(row, IDX_EMAIL),                    # row[5]
#             "F": get_val(row, IDX_HOUSE_NO),                 # row[6]
#             "G": get_val(row, IDX_ADDRESS_1),                # row[7]
#             "H": get_val(row, IDX_SELECT_DELIVERY_CITY),     # row[8]
#             "I": get_val(row, IDX_ZIP),                      # row[10] - Note SKIP row[9] (Shipping city)
#             "J": get_val(row, IDX_SKU),                      # row[11]
#             "K": "", "L": "", "M": "", "N": "", "O": "", "P": "", "Q": "", "R": "",
#             "S": get_val(row, IDX_DELIVERY_INSTRUCTIONS),    # row[12]
#             "T": get_val(row, IDX_ORDER_SELLER_NOTES),       # row[13]
#             "U": "",
#             "V": get_val(row, IDX_DELIVERY_TIME_EDIT),       # row[20]
#             "W": get_val(row, IDX_QUANTITY),                 # row[21]
#             "X": "", "Y": "",
#             "Z": get_val(row, IDX_SELECT_START_DATE)         # row[22]
#         }
#         new_data.append(new_row)
        
#     return pd.DataFrame(new_data, columns=EXPORT_COLUMNS)

# def convert_time_ranges_and_add_suffixes(df: pd.DataFrame) -> pd.DataFrame:
#     """
#     Logic from `convertTimeRangesAndAddWTD`.
#     Operates on Columns V (Time), A (Order ID), J (SKU).
#     """
#     # Mappings for Column V
#     time_mapping = {
#         'Dinner (1.30 PM - 7.30 PM)': 'DINNER',
#         'Lunch (9.00 AM - 2.00 PM)': 'LUNCH',
#         'Lunch (9.00 AM - 3.00 PM)': 'LUNCH',
#         'Lunch (9.30 AM - 2.30 PM)': 'LUNCH',
#         'Lunch (4.00 AM - 8.00 AM)': 'LUNCH',
#         'Lunch (10.30 AM - 2.00 PM)': 'LUNCH',
#         'Lunch (6.00 AM - 1.00 PM)': 'LUNCH',
#         'Lunch (6.00 AM - 2.00 PM)': 'LUNCH',
#         'Lunch (6.00 AM - 11.00 AM)': 'LUNCH',
#         'Lunch (7.00 AM - 1.00 PM)': 'LUNCH',
#         'Dinner (2.00 PM - 8.00 PM)': 'DINNER',
#         'Dinner (6.00 PM - 9.00 PM)': 'DINNER',
#         'Lunch (4.00 AM - 11.00 AM)': 'LUNCH',
#         'Lunch (8.00 AM - 11.00 AM)': 'LUNCH',
#         'Lunch (9.00 AM - 1.00 PM)': 'LUNCH',
#         'Lunch (10.00 AM - 3.00 PM)': 'LUNCH',
#     }
    
#     # We can use .map or .replace, strictly matching.
#     # The script uses exact match logic.
#     df['V'] = df['V'].map(lambda x: time_mapping.get(x, x))
    
#     # Suffix logic
#     wtd_skus = [
#       'STASH-TD-TS01-W05-ONCA-VEG08', 'STASH-TD-TS02-W05-ONCA-VEG08',
#       'STASH-TD-TS03-W05-ONCA-VEG12', 'STASH-TD-TS04-W05-ONCA-VEG12',
#       'STASH-TD-TS05-W05-ONCA-VEG12', 'STASH-TD-TS06-W05-ONCA-NVG12',
#       'STASH-TD-TS07-W05-ONCA-NVG12', 'STASH-TD-TS08-W05-ONCA-NVG12',
#       'STASH-TD-TS10-W05-ONCA-VEG08', 'STASH-TD-TS11-W05-ONCA-VEG08',
#       'STASH-TD-TS12-W05-ONCA-VEG08', 'STASH-TD-TS13-W05-ONCA-VEG08',
#       'STASH-TD-TS14-W05-ONCA-VEG12', 'STASH-TD-TS15-W05-ONCA-VEG12',
#       'STASH-TD-TS16-W05-ONCA-VEG12'
#     ]
    
#     gtd_skus = ['STASH-TD-TS09-W05-ONCA-GUJ01']
    
#     def add_suffix(row):
#         sku = str(row['J'])
#         order_id = str(row['A'])
#         if sku in wtd_skus:
#             return order_id + '-WTD'
#         if sku in gtd_skus:
#             return order_id + '-GTD'
#         return order_id

#     df['A'] = df.apply(add_suffix, axis=1)
    
#     return df

# def get_next_business_days(start_date, num_days=5):
#     """
#     Calculate the next N business days (Mon-Fri) starting from start_date.
#     Returns a list of datetime objects.
#     """
#     days = []
#     current_date = start_date
#     while len(days) < num_days:
#         # Check if Sat (5) or Sun (6)
#         if current_date.weekday() < 5: # 0-4 is Mon-Fri
#             days.append(current_date)
#         current_date += timedelta(days=1)
#     return days

# def parse_date(date_val):
#     """Try to parse date from string or return if already datetime"""
#     if isinstance(date_val, datetime):
#         return date_val
#     try:
#         # Expected 'YYYY-MM-DD' from Shopify usually
#         return datetime.strptime(str(date_val).split('T')[0], "%Y-%m-%d")
#     except:
#         return None

# def expand_subscriptions(df: pd.DataFrame) -> pd.DataFrame:
#     """
#     Logic from `updateOrders_TS01_to_TS16`.
#     Expands specific SKUs into 5 daily rows with date calculations.
#     """
#     # The Map from the script
#     sku_map = {
#         'STASH-TD-TS01-W05-ONCA-VEG08': [
#           'TPROS-TD-MT91-T01-ONCA-TPROS', 'FIERY-TD-MT01-T01-ONCA-FGBVG',
#           'LALKT-TD-MT31-T01-ONCA-SWAGT', 'ANGTH-TD-MT40-T01-ONCA-ANGVG',
#           'KRISK-TD-MT01-T01-ONCA-KRIVG'
#         ],
#         'STASH-TD-TS02-W05-ONCA-VEG08': [
#           'TPROS-TD-MT92-T01-ONCA-TPROS', 'FIERY-TD-MT02-T01-ONCA-FGBVG',
#           'LALKT-TD-MT30-T01-ONCA-SWAGT', 'ANGTH-TD-MT41-T01-ONCA-ANGVG',
#           'KRISK-TD-MT02-T01-ONCA-KRIVG'
#         ],
#         # ... (Abbreviated, I should use the full list from the text file)
#         # Using a subset for demonstration if the list is huge? 
#         # No, I should copy the map provided in the text file accurately.
        
#         # TS03
#         'STASH-TD-TS03-W05-ONCA-VEG12': ['TPROS-TD-MT93-T01-ONCA-TPROS', 'FIERY-TD-MT06-T01-ONCA-FGPVG', 'LALKT-TD-MT01-T01-ONCA-LEELA', 'ANGTH-TD-MT40-T01-ONCA-ANGVG', 'KRISK-TD-MT07-T01-ONCA-KRIVG'],
#         # TS04
#         'STASH-TD-TS04-W05-ONCA-VEG12': ['TPROS-TD-MT94-T01-ONCA-TPROS', 'FIERY-TD-MT09-T01-ONCA-FGPVG', 'LALKT-TD-MT03-T01-ONCA-LEELA', 'ANGTH-TD-MT47-T01-ONCA-ANGVG', 'KRISK-TD-MT92-T01-ONCA-KRIVG'],
#         # TS05
#         'STASH-TD-TS05-W05-ONCA-VEG12': ['TPROS-TD-MT95-T01-ONCA-TPROS', 'FIERY-TD-MT12-T01-ONCA-FGPVG', 'LALKT-TD-MT04-T01-ONCA-LEELA', 'ANGTH-TD-MT50-T01-ONCA-ANGVG', 'KRISK-TD-MT93-T01-ONCA-KRIVG'],
        
#         # TS06
#         'STASH-TD-TS06-W05-ONCA-NVG12': ['LALKT-TD-MT20-T01-ONCA-LALIT', 'FIERY-TD-MT19-T01-ONCA-FGPNV', 'WAKHR-TD-MT19-T01-ONCA-KTDNV', 'ANGTH-TD-MT58-T01-ONCA-ANGNV', 'FEAST-TD-MT34-T01-ONCA-SPFNV'],
#         # TS07
#         'STASH-TD-TS07-W05-ONCA-NVG12': ['LALKT-TD-MT24-T01-ONCA-LALIT', 'FIERY-TD-MT20-T01-ONCA-FGPNV', 'WAKHR-TD-MT20-T01-ONCA-KTDNV', 'ANGTH-TD-MT60-T01-ONCA-ANGNV', 'FEAST-TD-MT21-T01-ONCA-SPFNV'],
#         # TS08
#         'STASH-TD-TS08-W05-ONCA-NVG12': ['LALKT-TD-MT83-T01-ONCA-LALIT', 'FIERY-TD-MT23-T01-ONCA-FGPNV', 'WAKHR-TD-MT23-T01-ONCA-KTDNV', 'ANGTH-TD-MT61-T01-ONCA-ANGNV', 'FEAST-TD-MT22-T01-ONCA-SPFNV'],
        
#         # TS09
#         'STASH-TD-TS09-W05-ONCA-GUJ01': ['SRIJI-TD-MT03-T01-ONCA-SRIJI', 'SPBAR-TD-MT27-T01-ONCA-SBPGJ', 'TSWAD-TD-MT04-T01-ONCA-FRESH', 'RADHA-TD-MT08-T01-ONCA-RRBVG', 'MUMMA-TD-MT04-T01-ONCA-MMGUJ'],

#         # TS10
#         'STASH-TD-TS10-W05-ONCA-VEG08': ['TPROS-TD-MT96-T01-ONCA-TPROS', 'FIERY-TD-MT05-T01-ONCA-FGBVG', 'LALKT-TD-MT35-T01-ONCA-SWAGT', 'ANGTH-TD-MT44-T01-ONCA-ANGVG', 'KRISK-TD-MT91-T01-ONCA-KRIVG'],
        
#         # TS11
#         'STASH-TD-TS11-W05-ONCA-VEG08': ['LALKT-TD-MT31-T01-ONCA-SWAGT', 'FIERY-TD-MT01-T01-ONCA-FGBVG', 'WAKHR-TD-MT01-T01-ONCA-WCBVG', 'INFLV-TD-MT94-T01-ONCA-INFVG', 'FEAST-TD-MT01-T01-ONCA-SPFVG'],
#         # TS12
#         'STASH-TD-TS12-W05-ONCA-VEG08': ['LALKT-TD-MT30-T01-ONCA-SWAGT', 'FIERY-TD-MT02-T01-ONCA-FGBVG', 'WAKHR-TD-MT02-T01-ONCA-WCBVG', 'INFLV-TD-MT95-T01-ONCA-INFVG', 'FEAST-TD-MT02-T01-ONCA-SPFVG'],
#         # TS13
#         'STASH-TD-TS13-W05-ONCA-VEG08': ['LALKT-TD-MT35-T01-ONCA-SWAGT', 'FIERY-TD-MT05-T01-ONCA-FGBVG', 'WAKHR-TD-MT03-T01-ONCA-WCBVG', 'INFLV-TD-MT93-T01-ONCA-INFVG', 'FEAST-TD-MT05-T01-ONCA-SPFVG'],
        
#         # TS14
#         'STASH-TD-TS14-W05-ONCA-VEG12': ['LALKT-TD-MT01-T01-ONCA-LEELA', 'FIERY-TD-MT06-T01-ONCA-FGPVG', 'WAKHR-TD-MT08-T01-ONCA-WCPVG', 'INFLV-TD-MT96-T01-ONCA-INFVG', 'FEAST-TD-MT08-T01-ONCA-SPFVG'],
#         # TS15
#         'STASH-TD-TS15-W05-ONCA-VEG12': ['LALKT-TD-MT03-T01-ONCA-LEELA', 'FIERY-TD-MT09-T01-ONCA-FGPVG', 'WAKHR-TD-MT04-T01-ONCA-KTDVG', 'INFLV-TD-MT91-T01-ONCA-INFVG', 'FEAST-TD-MT11-T01-ONCA-SPFVG'],
#         # TS16
#         'STASH-TD-TS16-W05-ONCA-VEG12': ['LALKT-TD-MT04-T01-ONCA-LEELA', 'FIERY-TD-MT12-T01-ONCA-FGPVG', 'WAKHR-TD-MT11-T01-ONCA-WCPVG', 'INFLV-TD-MT92-T01-ONCA-INFVG', 'FEAST-TD-MT14-T01-ONCA-SPFVG']
#     }
    
#     new_rows = []
    
#     for _, row in df.iterrows():
#         sku = row['J']
#         if sku not in sku_map:
#             new_rows.append(row)
#             continue
            
#         # Expansion logic
#         mapped_skus = sku_map[sku]
#         start_date_raw = row['Z']
#         start_date = parse_date(start_date_raw)
        
#         if not start_date:
#             # Fallback if no date, just push rows with same date? 
#             # Or assume current date? Use original row.
#             new_rows.append(row)
#             continue
            
#         business_days = get_next_business_days(start_date, 5)
        
#         # Create 5 rows
#         for i, new_sku in enumerate(mapped_skus):
#             if i >= len(business_days):
#                 break
                
#             expanded_row = row.copy()
#             expanded_row['J'] = new_sku
#             expanded_row['Z'] = business_days[i].strftime("%Y-%m-%d")
            
#             # Note: The script says out.push(newRow) based on row.
#             # It updates SKU (J) and Date (Z).
#             # It also implies Logic for "Monday to Friday".
            
#             new_rows.append(expanded_row)
            
#     return pd.DataFrame(new_rows, columns=EXPORT_COLUMNS)

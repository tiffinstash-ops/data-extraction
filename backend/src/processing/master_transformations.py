import pandas as pd
import numpy as np
import os

# Column Labels for Master (A-BB, 54 columns total)
# Based on User Request Step 430 and lookup alignments
MASTER_COLUMNS = [
    "ORDER ID", "DATE", "NAME", "PHONE", "EMAIL", "HOUSE UNIT NO", "ADDRESS LINE 1", "CITY", "ZIP", "SKU", 
    "SELLER", "DELIVERY", "MEAL TYPE", "MEAL PLAN", "PRODUCT", "PRODUCT CODE", # 10-15 (K-P)
    "CLABL", "LABEL", "DRIVER NOTE", "SELLER NOTE (Changed original value)", "UPSTAIR DELIVERY", 
    "DELIVERY TIME", "QUANTITY", "DAYS", "COUNT", # 16-25 (Q-Y)
    "START DATE", "END DATE", "STATUS", "SKIP1", "SKIP2", "SKIP3", "SKIP4", "SKIP5", "SKIP6", 
    "SKIP7", "SKIP8", "SKIP9", "SKIP10", "SKIP11", "SKIP12", "SKIP13", "SKIP14", "SKIP15", "SKIP16", 
    "SKIP17", "SKIP18", "SKIP19", "SKIP20", "DELSAT", "DELSUN", "TS NOTES", "DESCRIPTION",
    "City Mismatch"
]

def vlookup_sku(export_df: pd.DataFrame) -> pd.DataFrame:
    """
    1. Loads SKU Reference Data.
    2. Maps Export data to Master columns (0-9, 16-25, etc.).
    3. Fills 10-15 via lookup on SKU using columns 3,7,5,6,4,8 from ref (1-based).
    """
    # 1. Initialize Master DataFrame
    master_df = pd.DataFrame(index=export_df.index, columns=MASTER_COLUMNS)
    master_df.fillna("", inplace=True)

    # 2. Load SKU Reference Data
    # 1-based: 2(SKU), 3(SELLER), 4(PRODUCT), 5(MEAL TYPE), 6(MEAL PLAN), 7(DELIVERY), 8(LABEL)
    # 0-based: 1(SKU), 2(SELLER), 3(PRODUCT), 4(MEAL TYPE), 5(MEAL PLAN), 6(DELIVERY), 7(LABEL)
    ref_path = "data/sku-ref.csv"
    ref_dict = {}
    if os.path.exists(ref_path):
        try:
            ref_data = pd.read_csv(ref_path)
            for _, row in ref_data.iterrows():
                sku_key = str(row['SKU']).strip()
                ref_dict[sku_key] = {
                    "SELLER": str(row['SELLER']),
                    "DELIVERY": str(row['DELIVERY']),
                    "MEAL TYPE": str(row['MEAL TYPE']),
                    "MEAL PLAN": str(row['MEAL PLAN']),
                    "PRODUCT": str(row['PRODUCT']),
                    "LABEL": str(row['LABEL']),
                    "DESCRIPTION": str(row['DESCRIPTION'])
                }
        except Exception as e:
            print(f"Error loading SKU ref: {e}")

    # 3. Base Mapping from Export Data (A-J mapping)
    for i in range(10):
        if i < len(export_df.columns):
            master_df.iloc[:, i] = export_df.iloc[:, i]
            
    # 4. Perform Lookups and Fill 10-15 and DESCRIPTION
    for idx, row in export_df.iterrows():
        sku = str(row.iloc[9]).strip() if len(row) > 9 else ""
        if sku in ref_dict:
            m = ref_dict[sku]
            master_df.iloc[master_df.index.get_loc(idx), 10] = m["SELLER"]
            master_df.iloc[master_df.index.get_loc(idx), 11] = m["DELIVERY"]
            master_df.iloc[master_df.index.get_loc(idx), 12] = m["MEAL TYPE"]
            master_df.iloc[master_df.index.get_loc(idx), 13] = m["MEAL PLAN"]
            master_df.iloc[master_df.index.get_loc(idx), 14] = m["PRODUCT"]
            master_df.iloc[master_df.index.get_loc(idx), 15] = m["LABEL"]
            
            # Fill Description at its named position
            if 'DESCRIPTION' in master_df.columns:
                master_df.loc[idx, 'DESCRIPTION'] = m["DESCRIPTION"]

    # 5. Fill remaining Master slots from Export data
    # Alignment:
    # Master 16 (CLABL) <- Export 16
    # Master 17 (LABEL) <- Export 17
    # Master 18 (DRIVER NOTE) <- Export 18
    # Master 19 (SELLER NOTE) <- Export 19
    # Master 20 (UPSTAIR) <- Export 20
    # Master 21 (DELIVERY TIME) <- Logic
    # Master 22 (QUANTITY) <- Export 22
    # Master 23 (DAYS) <- calculated Logic
    # Master 24 (COUNT) <- from Export? (user list has "COUNT")
    # Master 25 (START DATE) <- Export 23
    
    # Map index 16 to 22 precisely (CLABL to DELIVERY TIME)
    for i in range(16, 23):
        if i < len(export_df.columns):
            master_df.iloc[:, i] = export_df.iloc[:, i]
            
    # Map Start Date (Master 25 <- Export 25)
    if len(export_df.columns) > 25:
        master_df.iloc[:, 25] = export_df.iloc[:, 25]

    # Map City Mismatch if present in export_df
    if "City Mismatch" in export_df.columns:
        master_df["City Mismatch"] = export_df["City Mismatch"]

    # 6. Specialized logic for Column DAYS (Index 23)
    x_mapping = {
        'Trial': 1, 'Weekly': 5, 'Monthly': 20,
        'Weekly (4 Days)': 4, 'Monthly (16 Days)': 16,
        'Weekly (3 Days)': 3, 'Monthly (12 Days)': 12
    }
    # Use the looked-up "MEAL PLAN" (Index 13 in master)
    def calc_days(plan):
        val = str(plan).strip()
        return x_mapping.get(val, "")
    
    master_df.iloc[:, 23] = master_df.iloc[:, 13].apply(calc_days)

    # 7. Defaults for Hyphen/Zero columns
    zero_indices = list(range(27, 48)) # END DATE through SKIP18
    for idx in zero_indices: master_df.iloc[:, idx] = "0"
    
    hyphen_indices = [48, 49, 50] # SKIP19, 20, DELSAT
    for idx in hyphen_indices: master_df.iloc[:, idx] = "-"

    return master_df


def update_label(master_df: pd.DataFrame) -> pd.DataFrame:
    """
    Update LABEL column:
    If CLABL is not blank, use CLABL. Otherwise use PRODUCT CODE.
    """
    def get_label(row):
        # Using column names from MASTER_COLUMNS
        clabel = str(row.get('CLABL', '')).strip()
        # Check for meaningful content
        if clabel and clabel not in ['0', '0.0', 'nan', 'None', '']:
            return clabel
        return row.get('PRODUCT CODE', '')
        
    master_df['LABEL'] = master_df.apply(get_label, axis=1)
    return master_df

def fill_end_date(master_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the END DATE based on DAYS, holidays (SKIPs), and weekends (DELSAT/DELSUN).
    """
    from pandas.tseries.offsets import CustomBusinessDay

    def calculate_end_date_row(row):
        start_val = str(row.get('START DATE', '')).strip()
        days_val = row.get('DAYS', 0)
        
        if start_val == 'P':
            return 'PAUSE'
        if start_val == '-' or not start_val or start_val == '0':
            return '-'
            
        try:
            start_dt = pd.to_datetime(start_val)
        except:
            return start_val
            
        # Collect Holidays from SKIP1-SKIP20
        holidays = []
        for i in range(28, 48):
            h_val = str(row.iloc[i]).strip()
            if h_val and h_val not in ['0', '0.0', 'nan', 'None', '-']:
                try: holidays.append(pd.to_datetime(h_val))
                except: pass
        
        # Determine Weekmask
        sat_delivery = str(row.iloc[48]).strip().lower() == "yes"
        sun_delivery = str(row.iloc[49]).strip().lower() == "yes"
        mask = [1, 1, 1, 1, 1, 1 if sat_delivery else 0, 1 if sun_delivery else 0]
        
        try:
            num_days = int(float(days_val)) if days_val else 1
            if num_days > 1:
                cbd = CustomBusinessDay(holidays=holidays, weekmask=mask)
                end_dt = start_dt + (num_days - 1) * cbd
            else:
                end_dt = start_dt
            return end_dt.strftime("%Y-%m-%d")
        except:
            return start_dt.strftime("%Y-%m-%d")

    if not master_df.empty:
        master_df['END DATE'] = master_df.apply(calculate_end_date_row, axis=1)
    return master_df

def fill_status(master_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the STATUS based on today's date relative to START DATE and END DATE.
    """
    today = pd.Timestamp.now().normalize()

    def calculate_status_row(row):
        start_val = str(row.get('START DATE', '')).strip()
        end_val = str(row.get('END DATE', '')).strip()
        
        if start_val == 'P' or end_val == 'PAUSE':
            return 'PAUSE'
        if start_val == '-' or end_val == '-':
            return 'CANCELLED'
            
        try:
            start_dt = pd.to_datetime(start_val).normalize()
            end_dt = pd.to_datetime(end_val).normalize()
        except:
            return "ERROR"
            
        if today == end_dt:
            return "LAST DAY"
        elif start_dt <= today <= end_dt:
            return "WIP"
        elif today < start_dt:
            return "TBS"
        else:
            return "DELIVERED"

    if not master_df.empty:
        master_df['STATUS'] = master_df.apply(calculate_status_row, axis=1)
    return master_df

def create_master_transformations(export_df: pd.DataFrame) -> pd.DataFrame:
    master_df = vlookup_sku(export_df)
    master_df = update_label(master_df)
    master_df = fill_end_date(master_df)
    master_df = fill_status(master_df)
    
    return master_df

import pandas as pd
from datetime import timedelta
from src.utils.constants import SHOPIFY_ORDER_FIELDNAMES

# Source Column Mapping (based on SHOPIFY_ORDER_FIELDNAMES index)
IDX_ORDER_ID = 0
IDX_DATE = 1
IDX_NAME = 2
IDX_PHONE_NUMERIC = 3
IDX_PHONE_EDIT = 4
IDX_EMAIL = 5
IDX_HOUSE_NO = 6
IDX_ADDRESS_1 = 7
IDX_SELECT_DELIVERY_CITY = 8
IDX_SHIPPING_CITY = 9
IDX_ZIP = 10
IDX_SKU = 11
IDX_DELIVERY_INSTRUCTIONS = 12
IDX_ORDER_SELLER_NOTES = 13
IDX_DELIVERY_TIME = 14
IDX_DINNER_DELIVERY = 15
IDX_LUNCH_DELIVERY = 16
IDX_LUNCH_DELIVERY_TIME = 17
IDX_LUNCH_TIME = 18
IDX_DELIVERY_BETWEEN = 19
IDX_DELIVERY_TIME_EDIT = 20
IDX_QUANTITY = 21
IDX_SELECT_START_DATE = 22
IDX_DELIVERY_CITY = 23

# Defined Export Columns based on User Request
EXPORT_COLUMNS = [
    "ORDER ID", "DATE", "NAME", "PHONE", "EMAIL ID", "HOUSE UNIT NO", "ADDRESS LINE 1", "CITY", "ZIP CODE", "SKU",
    " ", "  ", "   ", "    ", "     ", "      ", # 6 Empty columns (K-P)
    "CLABL", "LABEL", "DRIVER NOTE", "SELLER NOTE", "UPSTAIR", "DELIVERY TIME", "QUANTITY",
    "       ", "        ", # 2 Empty columns (X-Y)
    "START DATE", # Z
    "City Mismatch"
]

def create_export_dataframe(source_df: pd.DataFrame) -> pd.DataFrame:
    """Map source columns to the finalized export layout."""
    new_data = []
    def get_val(row, idx):
        col_name = SHOPIFY_ORDER_FIELDNAMES[idx]
        return row[col_name] if col_name in row else ""

    for _, row in source_df.iterrows():
        new_row = {
            "ORDER ID": get_val(row, IDX_ORDER_ID),
            "DATE": get_val(row, IDX_DATE),
            "NAME": get_val(row, IDX_NAME),
            "PHONE": get_val(row, IDX_PHONE_EDIT),
            "EMAIL ID": get_val(row, IDX_EMAIL),
            "HOUSE UNIT NO": get_val(row, IDX_HOUSE_NO),
            "ADDRESS LINE 1": get_val(row, IDX_ADDRESS_1),
            "CITY": get_val(row, IDX_DELIVERY_CITY),
            "ZIP CODE": get_val(row, IDX_ZIP),
            "SKU": get_val(row, IDX_SKU),
            " ": "", "  ": "", "   ": "", "    ": "", "     ": "", "      ": "",
            "CLABL": "", 
            "LABEL": "",
            "DRIVER NOTE": get_val(row, IDX_DELIVERY_INSTRUCTIONS),
            "SELLER NOTE": get_val(row, IDX_ORDER_SELLER_NOTES),
            "UPSTAIR": "",
            "DELIVERY TIME": get_val(row, IDX_DELIVERY_TIME_EDIT),
            "QUANTITY": get_val(row, IDX_QUANTITY),
            "       ": "", "        ": "",
            "START DATE": get_val(row, IDX_SELECT_START_DATE),
            "City Mismatch": row.get("City Mismatch", "")
        }
        new_data.append(new_row)
    return pd.DataFrame(new_data, columns=EXPORT_COLUMNS)

def convert_time_ranges_and_add_suffixes(df: pd.DataFrame) -> pd.DataFrame:
    """Map time ranges to DINNER/LUNCH and add -WTD/-GTD suffixes."""
    time_mapping = {
        'Dinner (1.30 PM - 7.30 PM)': 'DINNER',
        'Lunch (9.00 AM - 2.00 PM)': 'LUNCH',
        'Lunch (9.00 AM - 3.00 PM)': 'LUNCH',
        'Lunch (9.30 AM - 2.30 PM)': 'LUNCH',
        'Lunch (4.00 AM - 8.00 AM)': 'LUNCH',
        'Lunch (10.30 AM - 2.00 PM)': 'LUNCH',
        'Lunch (6.00 AM - 1.00 PM)': 'LUNCH',
        'Lunch (6.00 AM - 2.00 PM)': 'LUNCH',
        'Lunch (6.00 AM - 11.00 AM)': 'LUNCH',
        'Lunch (7.00 AM - 1.00 PM)': 'LUNCH',
        'Dinner (2.00 PM - 8.00 PM)': 'DINNER',
        'Dinner (6.00 PM - 9.00 PM)': 'DINNER',
        'Lunch (4.00 AM - 11.00 AM)': 'LUNCH',
        'Lunch (8.00 AM - 11.00 AM)': 'LUNCH',
        'Lunch (9.00 AM - 1.00 PM)': 'LUNCH',
        'Lunch (10.00 AM - 3.00 PM)': 'LUNCH',
    }
    if 'DELIVERY TIME' in df.columns:
        df['DELIVERY TIME'] = df['DELIVERY TIME'].map(lambda x: time_mapping.get(x, x))
    
    wtd_skus = [
      'STASH-TD-TS01-W05-ONCA-VEG08', 'STASH-TD-TS02-W05-ONCA-VEG08',
      'STASH-TD-TS03-W05-ONCA-VEG12', 'STASH-TD-TS04-W05-ONCA-VEG12',
      'STASH-TD-TS05-W05-ONCA-VEG12', 'STASH-TD-TS06-W05-ONCA-NVG12',
      'STASH-TD-TS07-W05-ONCA-NVG12', 'STASH-TD-TS08-W05-ONCA-NVG12',
      'STASH-TD-TS10-W05-ONCA-VEG08', 'STASH-TD-TS11-W05-ONCA-VEG08',
      'STASH-TD-TS12-W05-ONCA-VEG08', 'STASH-TD-TS13-W05-ONCA-VEG08',
      'STASH-TD-TS14-W05-ONCA-VEG12', 'STASH-TD-TS15-W05-ONCA-VEG12',
      'STASH-TD-TS16-W05-ONCA-VEG12'
    ]
    gtd_skus = ['STASH-TD-TS09-W05-ONCA-GUJ01']
    
    def add_suffix(row):
        sku = str(row.get('SKU', ''))
        order_id = str(row.get('ORDER ID', ''))
        if sku in wtd_skus: return order_id + '-WTD'
        if sku in gtd_skus: return order_id + '-GTD'
        return order_id

    if 'ORDER ID' in df.columns:
        df['ORDER ID'] = df.apply(add_suffix, axis=1)
    return df

def get_next_business_days(start_date, num_days=5):
    days = []
    curr = start_date
    while len(days) < num_days:
        if curr.weekday() < 5: days.append(curr)
        curr += timedelta(days=1)
    return days

def expand_subscriptions(df: pd.DataFrame) -> pd.DataFrame:
    """Expand specific SKUs into 5 daily rows."""
    sku_map = {
        'STASH-TD-TS01-W05-ONCA-VEG08': ['TPROS-TD-MT91-T01-ONCA-TPROS', 'FIERY-TD-MT01-T01-ONCA-FGBVG', 'LALKT-TD-MT31-T01-ONCA-SWAGT', 'ANGTH-TD-MT40-T01-ONCA-ANGVG', 'KRISK-TD-MT01-T01-ONCA-KRIVG'],
        'STASH-TD-TS02-W05-ONCA-VEG08': ['TPROS-TD-MT92-T01-ONCA-TPROS', 'FIERY-TD-MT02-T01-ONCA-FGBVG', 'LALKT-TD-MT30-T01-ONCA-SWAGT', 'ANGTH-TD-MT41-T01-ONCA-ANGVG', 'KRISK-TD-MT02-T01-ONCA-KRIVG'],
        'STASH-TD-TS03-W05-ONCA-VEG12': ['TPROS-TD-MT93-T01-ONCA-TPROS', 'FIERY-TD-MT06-T01-ONCA-FGPVG', 'LALKT-TD-MT01-T01-ONCA-LEELA', 'ANGTH-TD-MT40-T01-ONCA-ANGVG', 'KRISK-TD-MT07-T01-ONCA-KRIVG'],
        'STASH-TD-TS04-W05-ONCA-VEG12': ['TPROS-TD-MT94-T01-ONCA-TPROS', 'FIERY-TD-MT09-T01-ONCA-FGPVG', 'LALKT-TD-MT03-T01-ONCA-LEELA', 'ANGTH-TD-MT47-T01-ONCA-ANGVG', 'KRISK-TD-MT92-T01-ONCA-KRIVG'],
        'STASH-TD-TS05-W05-ONCA-VEG12': ['TPROS-TD-MT95-T01-ONCA-TPROS', 'FIERY-TD-MT12-T01-ONCA-FGPVG', 'LALKT-TD-MT04-T01-ONCA-LEELA', 'ANGTH-TD-MT50-T01-ONCA-ANGVG', 'KRISK-TD-MT93-T01-ONCA-KRIVG'],
        'STASH-TD-TS06-W05-ONCA-NVG12': ['LALKT-TD-MT20-T01-ONCA-LALIT', 'FIERY-TD-MT19-T01-ONCA-FGPNV', 'WAKHR-TD-MT19-T01-ONCA-KTDNV', 'ANGTH-TD-MT58-T01-ONCA-ANGNV', 'FEAST-TD-MT34-T01-ONCA-SPFNV'],
        'STASH-TD-TS07-W05-ONCA-NVG12': ['LALKT-TD-MT24-T01-ONCA-LALIT', 'FIERY-TD-MT20-T01-ONCA-FGPNV', 'WAKHR-TD-MT20-T01-ONCA-KTDNV', 'ANGTH-TD-MT60-T01-ONCA-ANGNV', 'FEAST-TD-MT21-T01-ONCA-SPFNV'],
        'STASH-TD-TS08-W05-ONCA-NVG12': ['LALKT-TD-MT83-T01-ONCA-LALIT', 'FIERY-TD-MT23-T01-ONCA-FGPNV', 'WAKHR-TD-MT23-T01-ONCA-KTDNV', 'ANGTH-TD-MT61-T01-ONCA-ANGNV', 'FEAST-TD-MT22-T01-ONCA-SPFNV'],
        'STASH-TD-TS09-W05-ONCA-GUJ01': ['SRIJI-TD-MT03-T01-ONCA-SRIJI', 'SPBAR-TD-MT27-T01-ONCA-SBPGJ', 'TSWAD-TD-MT04-T01-ONCA-FRESH', 'RADHA-TD-MT08-T01-ONCA-RRBVG', 'MUMMA-TD-MT04-T01-ONCA-MMGUJ'],
        'STASH-TD-TS10-W05-ONCA-VEG08': ['TPROS-TD-MT96-T01-ONCA-TPROS', 'FIERY-TD-MT05-T01-ONCA-FGBVG', 'LALKT-TD-MT35-T01-ONCA-SWAGT', 'ANGTH-TD-MT44-T01-ONCA-ANGVG', 'KRISK-TD-MT91-T01-ONCA-KRIVG'],
        'STASH-TD-TS11-W05-ONCA-VEG08': ['LALKT-TD-MT31-T01-ONCA-SWAGT', 'FIERY-TD-MT01-T01-ONCA-FGBVG', 'WAKHR-TD-MT01-T01-ONCA-WCBVG', 'INFLV-TD-MT94-T01-ONCA-INFVG', 'FEAST-TD-MT01-T01-ONCA-SPFVG'],
        'STASH-TD-TS12-W05-ONCA-VEG08': ['LALKT-TD-MT30-T01-ONCA-SWAGT', 'FIERY-TD-MT02-T01-ONCA-FGBVG', 'WAKHR-TD-MT02-T01-ONCA-WCBVG', 'INFLV-TD-MT95-T01-ONCA-INFVG', 'FEAST-TD-MT02-T01-ONCA-SPFVG'],
        'STASH-TD-TS13-W05-ONCA-VEG08': ['LALKT-TD-MT35-T01-ONCA-SWAGT', 'FIERY-TD-MT05-T01-ONCA-FGBVG', 'WAKHR-TD-MT03-T01-ONCA-WCBVG', 'INFLV-TD-MT93-T01-ONCA-INFVG', 'FEAST-TD-MT05-T01-ONCA-SPFVG'],
        'STASH-TD-TS14-W05-ONCA-VEG12': ['LALKT-TD-MT01-T01-ONCA-LEELA', 'FIERY-TD-MT06-T01-ONCA-FGPVG', 'WAKHR-TD-MT08-T01-ONCA-WCPVG', 'INFLV-TD-MT96-T01-ONCA-INFVG', 'FEAST-TD-MT08-T01-ONCA-SPFVG'],
        'STASH-TD-TS15-W05-ONCA-VEG12': ['LALKT-TD-MT03-T01-ONCA-LEELA', 'FIERY-TD-MT09-T01-ONCA-FGPVG', 'WAKHR-TD-MT04-T01-ONCA-KTDVG', 'INFLV-TD-MT91-T01-ONCA-INFVG', 'FEAST-TD-MT11-T01-ONCA-SPFVG'],
        'STASH-TD-TS16-W05-ONCA-VEG12': ['LALKT-TD-MT04-T01-ONCA-LEELA', 'FIERY-TD-MT12-T01-ONCA-FGPVG', 'WAKHR-TD-MT11-T01-ONCA-WCPVG', 'INFLV-TD-MT92-T01-ONCA-INFVG', 'FEAST-TD-MT14-T01-ONCA-SPFVG']
    }
    new_rows = []
    for _, row in df.iterrows():
        sku = row.get('SKU', '')
        if sku not in sku_map:
            new_rows.append(row)
            continue
        try:
            start_date = pd.to_datetime(row.get('START DATE', ''))
        except:
            new_rows.append(row)
            continue
        business_days = get_next_business_days(start_date, 5)
        for i, new_sku in enumerate(sku_map[sku]):
            if i >= len(business_days): break
            expanded_row = row.copy()
            expanded_row['SKU'] = new_sku
            expanded_row['START DATE'] = business_days[i].strftime("%Y-%m-%d")
            new_rows.append(expanded_row)
    return pd.DataFrame(new_rows, columns=EXPORT_COLUMNS)

def update_clabl_and_upstair(df: pd.DataFrame) -> pd.DataFrame:
    """
    Logic from updateColumnQ Apps Script:
    1. If 'SELLER NOTE' is not empty/0, set 'CLABL' to firstName + truncated lastName (3 chars).
    2. If 'UPSTAIR' is empty or '0', set it to 'No'.
    """
    def format_name(name):
        if not name or not isinstance(name, str):
            return ""
        parts = name.split()
        first = parts[0] if len(parts) > 0 else ""
        last = parts[1][:3] if len(parts) > 1 else ""
        return f"{first} {last}".strip()

    if 'SELLER NOTE' in df.columns and 'NAME' in df.columns:
        # Check for non-empty and non-zero
        mask = (df['SELLER NOTE'].astype(str).str.strip() != "") & (df['SELLER NOTE'].astype(str) != "0")
        df.loc[mask, 'CLABL'] = df.loc[mask, 'NAME'].apply(format_name)

    if 'UPSTAIR' in df.columns:
        # Check for empty or '0'
        upstair_mask = (df['UPSTAIR'].astype(str).str.strip() == "") | (df['UPSTAIR'].astype(str) == "0")
        df.loc[upstair_mask, 'UPSTAIR'] = 'No'
    
    return df

def run_post_edit_transformations(df: pd.DataFrame) -> pd.DataFrame:
    """Run Phase 2 (Export Mapping) and Phase 3 (Expansion) transforms."""
    df = create_export_dataframe(df)
    df = convert_time_ranges_and_add_suffixes(df)
    df = expand_subscriptions(df)
    df = update_clabl_and_upstair(df)
    return df

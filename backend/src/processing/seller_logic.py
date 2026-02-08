"""
Logic for processing seller data from Google Sheets.
"""
from datetime import datetime

def update_column_k(val: str) -> str:
    """Map seller codes to full names."""
    if not val:
        return val
    v = str(val).lower()
    mapping = {
        'kt': 'KHAOT', 'lk': 'LALKT', 'sw': 'TSWAD', 'tp': 'TPROS', 'mj': 'MIJOY',
        'vs': 'VISWA', 'if': 'INFLV', 'kk': 'KHAOK', 'bv': 'BHAVS', 'an': 'ANGTH',
        'sp': 'SPICE', 'ca': 'CHEFA', 'fg': 'FIERY', 'fm': 'FMONK', 'ks': 'KRISK',
        'kl': 'KERAL', 'sb': 'SPBAR', 'rd': 'RADHA', 'dn': 'DELHI', 'sc': 'SATVK',
        'rn': 'RNBIT', 'sm': 'SUBMA', 'hk': 'HEMIK', 'pr': 'PINDI', 'ms': 'MOKSH',
        'mc': 'MASCO', 'cb': 'CBAKE', 'hf': 'HOMEF', 'rv': 'RITAJ', 'mu': 'MUMKT',
        'dr': 'DSRAS', 'mz': 'MITZI', 'mn': 'AMINA'
    }
    for k, mapped in mapping.items():
        if k in v:
            return mapped
    return val

def update_seller_delivery(val: str) -> str:
    """Normalize seller delivery status."""
    if not val or (isinstance(val, str) and not val.strip()):
        return "No"
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("no", "yes"):
            return v.capitalize()
        if v == "yes ($1.99/day)":
            return "Yes"
    return val

def apply_td_to_vd(v_val: str, l_val: str) -> str:
    """Switch TD to VD for Midday deliveries."""
    if v_val == "MIDDAY" and l_val == "TD":
        return "VD"
    return l_val

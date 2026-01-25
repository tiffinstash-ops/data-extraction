import pandas as pd
import numpy as np
from src.processing.find_city import get_city_from_address

def removeRowsWithBlankSKU(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df['SKU'].astype(str).str.strip() != '']
    df = df[~df['SKU'].isin(['0'])]
    return df
    
def updateColumnDeliveryInstructionsforDrivers(df: pd.DataFrame) -> pd.DataFrame:
    col = 'Delivery Instructions (for drivers)'
    df[col] = df[col].astype(str).str.replace(f'{col}:', '', regex=False).str.replace('\n', '. ', regex=False)
    return df

def moveDeliveryCitytoSelectDeliveryCity(df: pd.DataFrame) -> pd.DataFrame:
    mask = df['Delivery city'].notna() & (df['Delivery city'].astype(str).str.strip() != '')
    df.loc[mask, 'Select Delivery City'] = df.loc[mask, 'Delivery city']
    df.loc[mask, 'Delivery city'] = ''
    return df

def fillZeros(df: pd.DataFrame) -> pd.DataFrame:
    df.fillna(0, inplace=True)
    return df

def highlightMismatchedDeliveryCity(df: pd.DataFrame) -> pd.DataFrame:
    df['City Mismatch'] = np.where(df['Select Delivery City'] != df['Shipping address city'], 'Mismatch', '')
    return df

def findCity(df: pd.DataFrame) -> pd.DataFrame:
    def get_row_city(row):
        if row.get('City Mismatch') == 'Mismatch':
            # Combine Address Line 1 and ZIP (Postal Code)
            # Internal column names are all caps as defined in constants.py/utils.py
            address = row.get('ADDRESS LINE 1', '')
            zip_code = row.get('ZIP', '')
            
            if not address and not zip_code:
                return "Address/ZIP missing"
                
            full_address = f"{address}, {zip_code}"
            return get_city_from_address(full_address)
        else:
            # For rows without mismatch, copy Select Delivery City
            return row.get('Select Delivery City', '')
            
    df['Delivery city'] = df.apply(get_row_city, axis=1)
    return df

def apply_all_transformations(df: pd.DataFrame) -> pd.DataFrame:
    df = removeRowsWithBlankSKU(df)
    df = updateColumnDeliveryInstructionsforDrivers(df)
    # df = moveDeliveryCitytoSelectDeliveryCity(df)
    df = fillZeros(df)
    df = highlightMismatchedDeliveryCity(df)
    df = findCity(df)
    return df

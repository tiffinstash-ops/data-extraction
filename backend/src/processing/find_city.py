import os
import googlemaps
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

def get_city_from_address(address_string):
    # Retrieve the key from the environment
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key:
        raise ValueError("API Key not found. Ensure GOOGLE_MAPS_API_KEY is set in your .env file or environment.")

    gmaps = googlemaps.Client(key=api_key)
    
    try:
        # Geocode the address
        geocode_result = gmaps.geocode(address_string)

        if not geocode_result:
            return "No results found."

        # Extract city (locality)
        components = geocode_result[0].get('address_components', [])
        print(components)
        
        # Generator expression to find the 'locality' component
        city = next((c['long_name'] for c in components if 'sublocality' in c['types']), None)
        if city:
            return city
        else:
            city = next((c['long_name'] for c in components if 'locality' in c['types']), None)
            return city if city else "City/Locality not found in results."

    except Exception as e:
        return f"An error occurred: {e}"

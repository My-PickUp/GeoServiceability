from geopy.geocoders import Nominatim
from pydantic import BaseModel
import requests

def get_address_pincode_from_laton(latitude, longitude):
    geolocator = Nominatim(user_agent="my-geocoder")
    
    location = geolocator.reverse((latitude, longitude), language='en')
    address = location.address if location else None 
    pincode = location.raw.get('address', {}).get('postcode') if location else None 
    
    return address, pincode 

def get_lat_long_from_address(address):
    geolocator = Nominatim(user_agent="my-geocoder")
    
    location = geolocator.geocode(address)
    
    latitude = location.latitude if location else None
    longitude = location.longitude if location else None
    return latitude, longitude


def get_pincode_from_address(address):
    geolocator = Nominatim(user_agent="my-geocoder")
    location = geolocator.geocode(address)
    
    if location:
        print("Raw Data:", location.raw)
        pincode = location.raw.get('address', {}).get('postcode')
        if pincode:
            return pincode
        else:
            print("Postal code not found in raw data.")
            return None
    else:
        print("Geocoding failed for address:", address)
        return None
    
def geocodeing_data(address, api_key):
    base_url = "https://geocode.search.hereapi.com/v1/geocode"
    parmas = {
        "q" : address,
        "apiKey" : api_key
    }
    
    response = requests.get(base_url, params=parmas)
    data = response.json()
    
    if response.status_code == 200 and data.get("items"):
        location = data["items"][0]["position"]
        address_details = data["items"][0]["address"]
        
        latitude = location["lat"]
        longitude = location["lng"]
        postal_code = address_details.get("postlaCode")
        
        return {"lat":latitude,
                "long":longitude, "pincode":postal_code}
    else:
        print(f"Error : {response.status_code} {data.get('title')}")

x = geocodeing_data("UNITED CRICKET CLUB , NOIDA","NONtRb0nM3nqpEos8Z8ulTyYAFlt2RQIeSEgYJThoR0")
print("Result:", x)

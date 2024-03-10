from typing import List
import csv,json
from fastapi import FastAPI, HTTPException
from fastapi import FastAPI, HTTPException, Depends, Query
import googlemaps
import asyncio
from datetime import datetime
from itertools import combinations
from typing import List

from fastapi import FastAPI, Depends,UploadFile,File, HTTPException
from concurrent.futures import ThreadPoolExecutor
from fastapi.params import Body
import io
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
import time
from geolocation import get_address_pincode_from_laton
from schema import Pincode,Check_Serv,ZipCode,Ingest_cities, Update_cities
import models
from fastapi.middleware.cors import CORSMiddleware
from database import engine, SessionLocal
from sqlalchemy.orm import Session
import pandas as pd
import os
from geopy.distance import geodesic
from itertools import combinations

models.Base.metadata.create_all(bind=engine)
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/mypickup/")
def read_root():
    return {"Hello": "World"}

@app.post("/mypickup/geolocation")
def get_geoloc(locat: Pincode):
    address, zipcode = get_address_pincode_from_laton(locat.lat, locat.lon)
    return {zipcode}

@app.post("/mypickup/ingest-geolocation-pincode")
def ingest_geoloc_using_pincode(Serv: Check_Serv):
    db = SessionLocal()
    temp_zipcode = Serv.zip_code
    servic = Serv.is_serviceable
    city = Serv.city_id
    
    temp_pincode = db.query(models.Serviceable_area).filter(models.Serviceable_area.zip_code == temp_zipcode).first()
    temp_city = db.query(models.Cities.id).filter(models.Cities.id == city).first()
    
    if temp_pincode is not None:
        return {'message':"pincode already exists"}
    
    if temp_city is None:
        return {'message':'city is not serviceable'}
    
    data = models.Serviceable_area(
        city_id = city,
        is_serviceable=servic,
        zip_code = temp_zipcode
    )
    
    if (temp_zipcode) is not None:
        db.add(data)
        db.commit()
        #db.refresh(new_data)
        return {"message": f"The complete data is {data}, Zip Code: {temp_zipcode}"}
    else:
        return {"error": "Unable to get pincode from address"}
    
@app.post("/mypickup/ingest-geolocation-pincode-file")
async def ingest_geo_file(file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))

        # Convert column names to lowercase and remove leading/trailing spaces
        df.columns = df.columns.str.lower().str.strip()

        if 'pincode' not in df.columns:
            return {"error": "Column 'Pincode' not found in the file."}

        # List to store unique zip codes
        unique_zip_codes: List[int] = []

        for index, row in df.iterrows():
            temp_zipcode = row['pincode']
            temp_serv = row['servicable']
            temp_city_name = row['district']

            new_city = db.query(models.Cities.id).filter(models.Cities.city == temp_city_name).first()

            if new_city is None:
                return {"error": f"City not found for zipcode {temp_zipcode}"}

            new_zipcode = int(temp_zipcode)
            print(temp_zipcode)

            # Check if the zip_code already exists in the list
            if new_zipcode in unique_zip_codes:
                continue  # Skip if already processed

            # Check if the zip_code already exists in the database
            existing_zipcode = db.query(models.Serviceable_area).filter(models.Serviceable_area.zip_code == new_zipcode).first()
            print(existing_zipcode)

            if existing_zipcode is None:
                print("ok")
                # Add the zip_code to the list
                unique_zip_codes.append(new_zipcode)

                # Proceed with insertion
                new_city_id = new_city[0]
                new_serv = 1 if str(temp_serv).lower() == "yes" else 0

                # Create a new record only if the zip_code doesn't exist
                new_record = models.Serviceable_area(
                    city_id=new_city_id,
                    is_serviceable=new_serv,
                    zip_code=new_zipcode
                )
                db.add(new_record)

        # Commit changes to the database after processing all rows
        db.commit()

        return {"message": "Data successfully ingested"}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")
   

@app.post("/mypickup/ingest-geolocation-latlon")
def ingest_geoloc_using_latlon(Serv: Pincode):
    db = SessionLocal()
    lat = Serv.lat
    lon = Serv.lon
    
    temp_lat = db.query(models.Serviceable_area).filter(models.Serviceable_area.lat == lat).first()
    temp_lon = db.query(models.Serviceable_area).filter(models.Serviceable_area.lon == lon).first()
    
    
    if((temp_lat is not None) and (temp_lon is not None)):
        print(temp_lat,temp_lon)
        return {'message': 'Data already exists'}
    
    address, pincode = get_address_pincode_from_laton(lat, lon)
    
    temp_pincode = db.query(models.Serviceable_area).filter(models.Serviceable_area.zip_code == pincode).first()
    
    if temp_pincode is not None:
        return {'message':"pincode already exists"}
    
    data = models.Serviceable_area(
        lat=lat,
        lon=lon,
        city_id = 1,
        is_serviceable=Serv.is_serviceable,
        zip_code = pincode
    )

    if (pincode) is not None:
        db.add(data)
        db.commit()
        #db.refresh(new_data)
        return {"message": f"The complete data is {data}, Zip Code: {pincode}"}
    else:
        return {"error": "Unable to get pincode from address"}
    

@app.post("/mypickup/check-pincode")
def checkpincode(zipcode: ZipCode):
    db = SessionLocal()
    zip_code_value = zipcode.zip_code 

    zips = db.query(models.Serviceable_area).filter(models.Serviceable_area.zip_code == zip_code_value)

    if not zips.first():
        return {0}
    else:
        serv = zips.first().is_serviceable
        return {f"The pin code {zip_code_value} is available, and the serviceability condition is {serv}"}
    
@app.put('/mypickup/update-serviceability')
def update_Servi(zipcode : Check_Serv):
    db = SessionLocal()
    zip_code_value = zipcode.zip_code 
    new_Serviceabilty = zipcode.is_serviceable
    serviceable_area = db.query(models.Serviceable_area).filter(models.Serviceable_area.zip_code == zip_code_value).first()

    if serviceable_area:
        # Update the serviceability
        serviceable_area.is_serviceable = new_Serviceabilty
        db.commit()
        return {"message": f"Serviceability for pin code {zip_code_value} updated successfully."}
    else:
        return {"message" : f"pincode {zip_code_value} not found"}
    
     

@app.post('/mypickup/ingest-cities')
def ingest_cities(city_data: Ingest_cities):
    db = SessionLocal()
    city_temp_name = city_data.city_name
    user_email = city_data.user_email
    city_serv = city_data.serviceability

    present_city = db.query(models.Cities.id).filter(models.Cities.city == city_temp_name).first()

    if present_city is not None:
        return {"city is already present"}

    # Insert the new city
    city_datas = models.Cities(
        city=city_temp_name,
        serviceability=city_serv
    )
    db.add(city_datas)
    db.commit()

    # Get the id of the newly inserted city
    city_id = city_datas.id

    # Create User_cities instance
    user_data = models.User_cities(
        city_id=city_id,
        user_email=user_email
    )

    db.add(user_data)
    db.commit()

@app.put('/mypickup/ingest-cities/update')
def update_cities(city_data: Update_cities):
    db = SessionLocal()
    city_temp_id = city_data.city_id
    user_email = city_data.user_email
    city_serv = city_data.serviceability

    present_city = db.query(models.Cities).filter(models.Cities.id == city_temp_id).first()

    if present_city is None:
        return {"city is not present"}

    present_city.serviceability = city_serv

    user_data = models.User_cities(
        city_id=city_temp_id,
        user_email=user_email
    )

    db.add(user_data)
    db.commit()



import googlemaps
import math
from itertools import combinations
from datetime import datetime

# Initialize Google Maps client with API key
api_key = 'AIzaSyCNrNiAIsXKD84dZbamrDLCofJ_NNMoLNM'  # Replace 'YOUR_API_KEY' with your actual API key
gmaps = googlemaps.Client(key=api_key)

# def read_customer_data_from_csv(csv_file_path):
#     customers = []
#     with open(csv_file_path, "r", newline='') as csvfile:
#         reader = csv.reader(csvfile)
#         # Skip header if present
#         next(reader, None)
#         for row in reader:
#             # Assuming the CSV structure is: Name, Start Location, End Location, Time
#             name = row[1]  # Name
#             pickup_location = f"{row[2]}, {row[3]}"  # Start Location
#             drop_location = f"{row[4]}, {row[5]}"  # End Location
#             time = remove_seconds_from_time(row[6])  # Time
#             customers.append({'name': name, 'pickup_location': pickup_location, 'drop_location': drop_location, 'time': time})
#     return customers
#
# def remove_seconds_from_time(time_str):
#     """
#     Removes seconds from the time string.
#     If the time string contains a date part, removes the date part as well.
#     """
#     # Split the time string by space to handle scenarios with a date part
#     time_parts = time_str.split(' ')
#     if len(time_parts) >= 2:  # Check if there is a date part
#         # Split the time part by colon to handle scenarios with seconds
#         time_time_parts = time_parts[1].split(':')
#         if len(time_time_parts) >= 2:  # Ensure there are at least two parts (hours and minutes)
#             return time_parts[1]  # Keep only the second part (time)
#         else:
#             return time_parts[1]  # Return the time part with removed date
#     else:
#         # Split the time string by colon to handle scenarios without a date part
#         time_parts = time_str.split(':')
#         if len(time_parts) >= 2:  # Ensure there are at least two parts (hours and minutes)
#             return ':'.join(time_parts[0:2])  # Keep only the first two parts (hours and minutes)
#         else:
#             return time_str
#
# csv_file_path = '/Users/saionmukherjeesmacbookpro/Downloads/lead_customers_data.csv'  # Replace with the path to your CSV file
# customers = read_customer_data_from_csv(csv_file_path)
#
# # Convert list of dictionaries to JSON
# json_customers = json.dumps(customers, indent=4)
#
# print(json_customers)

gmaps = googlemaps.Client(key=api_key)

# Cache for route planning and distance calculation results
route_cache = {}
json_customers = [
    {
        "name": "Seenu",
        "pickup_location": "12.77913462, 77.72965295",
        "drop_location": "12.8411118, 77.6734777",
        "time": "08:30"
    },
    {
        "name": "Abhijit",
        "pickup_location": "12.81950564, 77.66406878",
        "drop_location": "12.8420274, 77.6731427",
        "time": "08:44"
    },
    {
        "name": "Sona Brahma",
        "pickup_location": "12.83036971, 77.6843494",
        "drop_location": "12.9257955, 77.6864417",
        "time": "08:00"
    },
    {
        "name": "SUPRIYO Banerjee",
        "pickup_location": "12.84027127, 77.6482609",
        "drop_location": "12.9271463, 77.6810426",
        "time": "08:59"
    },
    {
        "name": "SUPRIYO Banerjee",
        "pickup_location": "12.8402922, 77.64823408",
        "drop_location": "12.92971619, 77.69056052",
        "time": "08:00"
    },
    {
        "name": "Shreeya Wagh",
        "pickup_location": "12.84031312, 77.64821262",
        "drop_location": "12.8311384, 77.6803371",
        "time": "09:30"
    },
    {
        "name": "Ronald Dsouza",
        "pickup_location": "12.85855325, 77.60905757",
        "drop_location": "12.975273, 77.6375176",
        "time": "09:00"
    },
    {
        "name": "Gune",
        "pickup_location": "12.86404178, 77.61422904",
        "drop_location": "12.9200227, 77.6708365",
        "time": "09:50"
    },
    {
        "name": "Kalyani Menon",
        "pickup_location": "12.86689655, 77.60656661",
        "drop_location": "12.97919322, 77.64391028",
        "time": "08:30"
    },
    {
        "name": "Asha",
        "pickup_location": "12.86727547, 77.62437115",
        "drop_location": "12.91645388, 77.63647847",
        "time": "09:00"
    },
    {
        "name": "Sayan Ghosh",
        "pickup_location": "12.86748066, 77.6445688",
        "drop_location": "12.9618657, 77.5992083",
        "time": "07:30"
    },
    {
        "name": "Pratibha",
        "pickup_location": "12.86853295, 77.68638865",
        "drop_location": "12.92597498, 77.6805886",
        "time": "11:45"
    },
    {
        "name": "Anithaa Nagaraja",
        "pickup_location": "12.86952744, 77.61734352",
        "drop_location": "12.9161916, 77.6247894",
        "time": "09:30"
    },
    {
        "name": "Shanika Patel",
        "pickup_location": "12.87246069, 77.61604034",
        "drop_location": "12.920436, 77.6673345",
        "time": "09:00"
    },
    {
        "name": "Bidisha",
        "pickup_location": "12.87483388, 77.60944849",
        "drop_location": "12.96661024, 77.6083946",
        "time": "09:00"
    },
    {
        "name": "Nisha",
        "pickup_location": "12.8786638, 77.60693904",
        "drop_location": "12.89617839, 77.57018205",
        "time": "09:15"
    },
    {
        "name": "Qwerty",
        "pickup_location": "12.88153903, 77.63164425",
        "drop_location": "12.9208775, 77.68509118",
        "time": "10:00"
    },
    {
        "name": "Divya",
        "pickup_location": "12.88196291, 77.64302832",
        "drop_location": "12.91198025, 77.65263863",
        "time": "08:30"
    },
    {
        "name": "Priyanjali",
        "pickup_location": "12.88196569, 77.6430314",
        "drop_location": "12.91198025, 77.65263863",
        "time": "08:30"
    },
    {
        "name": "Suno",
        "pickup_location": "12.88211375, 77.64816581",
        "drop_location": "12.91695235, 77.61435405",
        "time": "09:35"
    },
    {
        "name": "Ram Kasuru",
        "pickup_location": "12.88311745, 77.64706874",
        "drop_location": "12.9199584, 77.645706",
        "time": "09:45"
    },
    {
        "name": "Sulbha",
        "pickup_location": "12.88428113, 77.66820498",
        "drop_location": "12.95975897, 77.64198",
        "time": "09:00"
    },
    {
        "name": "Rama",
        "pickup_location": "12.88433812, 77.6681988",
        "drop_location": "12.8444691, 77.6690607",
        "time": "08:15"
    },
    {
        "name": "Sonali Kumari",
        "pickup_location": "12.88452779, 77.66684942",
        "drop_location": "12.8375, 77.6555556",
        "time": "09:30"
    },
    {
        "name": "Sooraj Tom",
        "pickup_location": "12.88487507, 77.59485235",
        "drop_location": "12.92244912, 77.66927877",
        "time": "10:00"
    },
    {
        "name": "Simran",
        "pickup_location": "12.88507651, 77.616481",
        "drop_location": "12.92882457, 77.6329717",
        "time": "09:30"
    },
    {
        "name": "Swathi",
        "pickup_location": "12.88533061, 77.64873238",
        "drop_location": "12.9516254, 77.6424887",
        "time": "19:40"
    },
    {
        "name": "Riya",
        "pickup_location": "12.88538151, 77.70420988",
        "drop_location": "12.8991401, 77.6309785",
        "time": "09:35"
    },
    {
        "name": "Shreya",
        "pickup_location": "12.8853832, 77.74947028",
        "drop_location": "12.97883449, 77.65908257",
        "time": "09:00"
    },
    {
        "name": "Anisha Patnaik",
        "pickup_location": "12.88562428, 77.66746178",
        "drop_location": "12.934332, 77.6128238",
        "time": "08:15"
    },
    {
        "name": "H",
        "pickup_location": "12.8885945, 77.56197775",
        "drop_location": "12.88502075, 77.59632452",
        "time": "08:00"
    },
    {
        "name": "R Agarwal",
        "pickup_location": "12.89029156, 77.66796637",
        "drop_location": "12.95351606, 77.64326427",
        "time": "09:10"
    },
    {
        "name": "Shubham",
        "pickup_location": "12.89046702, 77.63727421",
        "drop_location": "12.9567938, 77.6998929",
        "time": "10:00"
    },
    {
        "name": "Arundhati",
        "pickup_location": "12.89050886, 77.63729567",
        "drop_location": "12.9258108, 77.6745834",
        "time": "10:00"
    },
    {
        "name": "Asha",
        "pickup_location": "12.89055682, 77.66876893",
        "drop_location": "12.88424792, 77.66820148",
        "time": "12:30"
    },
    {
        "name": "Mayank Kumar",
        "pickup_location": "12.89056115, 77.63725275",
        "drop_location": "12.9710483, 77.6407453",
        "time": "20:30"
    },
    {
        "name": "Amar Kant Gupta",
        "pickup_location": "12.89144341, 77.64373867",
        "drop_location": "12.9806326, 77.6952716",
        "time": "09:30"
    },
    {
        "name": "Anurag",
        "pickup_location": "12.89172479, 77.6195874",
        "drop_location": "12.98426586, 77.5970997",
        "time": "08:45"
    },
    {
        "name": "Lakshmi",
        "pickup_location": "12.8931672, 77.61256207",
        "drop_location": "12.90127374, 77.65084404",
        "time": "09:25"
    },
    {
        "name": "Navya R",
        "pickup_location": "12.89400809, 77.65326167",
        "drop_location": "12.98574534, 77.69150844",
        "time": "02:45"
    },
    {
        "name": "Sahana",
        "pickup_location": "12.8940813, 77.65329385",
        "drop_location": "12.9110285, 77.63526021",
        "time": "09:00"
    },
    {
        "name": "Prasanna Subramanian",
        "pickup_location": "12.89444584, 77.63644734",
        "drop_location": "13.0169992, 77.7044335",
        "time": "10:23"
    },
    {
        "name": "Sunita Rajput",
        "pickup_location": "12.89454565, 77.59713292",
        "drop_location": "12.9119545, 77.6526297",
        "time": "12:00"
    },
    {
        "name": "Anjali",
        "pickup_location": "12.89569247, 77.67781956",
        "drop_location": "12.9513154, 77.6464534",
        "time": "09:30"
    },
    {
        "name": "Ashika Drolia",
        "pickup_location": "12.89600932, 77.65678725",
        "drop_location": "12.9021042, 77.5947684",
        "time": "08:30"
    },
    {
        "name": "Dhiraj",
        "pickup_location": "12.8961699, 77.6460176",
        "drop_location": "12.8421412, 77.66306",
        "time": "08:23"
    },
    {
        "name": "krissel Monteiro",
        "pickup_location": "12.89662304, 77.63216615",
        "drop_location": "12.94132913, 77.62129397",
        "time": "08:25"
    },
    {
        "name": "Neha",
        "pickup_location": "12.89712813, 77.63254625",
        "drop_location": "12.9145027, 77.6325496",
        "time": "10:40"
    },
    {
        "name": "Palak",
        "pickup_location": "12.89714369, 77.65534425",
        "drop_location": "12.97388182, 77.61242181",
        "time": "08:40"
    },
    {
        "name": "Lubna Malhotra",
        "pickup_location": "12.89782214, 77.66785692",
        "drop_location": "12.90121256, 77.65152925",
        "time": "11:45"
    },
    {
        "name": "Smriti",
        "pickup_location": "12.89899252, 77.6681444",
        "drop_location": "12.92448284, 77.6700857",
        "time": "10:15"
    },
    {
        "name": "Smriti",
        "pickup_location": "12.89903435, 77.66816585",
        "drop_location": "12.92438873, 77.67009642",
        "time": "10:15"
    },
    {
        "name": "Shubham Barbaile",
        "pickup_location": "12.89956655, 77.65198412",
        "drop_location": "12.97979847, 77.66484245",
        "time": "11:30"
    },
    {
        "name": "Susmita",
        "pickup_location": "12.89968975, 77.65295264",
        "drop_location": "12.91871036, 77.67100077",
        "time": "08:40"
    },
    {
        "name": "Indu",
        "pickup_location": "12.89978345, 77.64142461",
        "drop_location": "12.93282429, 77.60283408",
        "time": "09:20"
    },
    {
        "name": "Apoorv",
        "pickup_location": "12.89978805, 77.64136104",
        "drop_location": "12.90426789, 77.6487017",
        "time": "10:00"
    },
    {
        "name": "Apurva pattela",
        "pickup_location": "12.90014635, 77.60825278",
        "drop_location": "12.9781683, 77.5723312",
        "time": "09:33"
    },
    {
        "name": "Apurva pattela",
        "pickup_location": "12.90016726, 77.60824205",
        "drop_location": "12.9160004, 77.6159078",
        "time": "09:45"
    },
    {
        "name": "Shiladitya Chatterjee",
        "pickup_location": "12.90096039, 77.61818292",
        "drop_location": "12.8501975, 77.6638659",
        "time": "09:30"
    },
    {
        "name": "Samiksha Kapoor",
        "pickup_location": "12.90181746, 77.62843995",
        "drop_location": "12.9256972, 77.6319306",
        "time": "09:30"
    },
    {
        "name": "Abhinav",
        "pickup_location": "12.902191, 77.644315",
        "drop_location": "12.99181606, 77.7136066",
        "time": "08:02"
    },
    {
        "name": "Pranita",
        "pickup_location": "12.90222139, 77.66154178",
        "drop_location": "12.989014, 77.592265",
        "time": "08:00"
    },
    {
        "name": "Prerna",
        "pickup_location": "12.90228451, 77.67002904",
        "drop_location": "12.91224387, 77.63310405",
        "time": "08:50"
    },
    {
        "name": "Sukalpa",
        "pickup_location": "12.9024866, 77.67007001",
        "drop_location": "12.91714171, 77.57977182",
        "time": "08:45"
    },
    {
        "name": "Prasanth",
        "pickup_location": "12.902534, 77.677299",
        "drop_location": "12.92736588, 77.6810426",
        "time": "09:51"
    },
    {
        "name": "Aayushi",
        "pickup_location": "12.90275062, 77.68435285",
        "drop_location": "12.9158542, 77.6343158",
        "time": "09:30"
    },
    {
        "name": "Abhipsa",
        "pickup_location": "12.90316234, 77.67648572",
        "drop_location": "12.936763, 77.6890143",
        "time": "10:30"
    },
    {
        "name": "Deepa",
        "pickup_location": "12.90333125, 77.66190224",
        "drop_location": "12.89788071, 77.71293074",
        "time": "11:00"
    },
    {
        "name": "Sujatha",
        "pickup_location": "12.9033417, 77.66194515",
        "drop_location": "12.9021042, 77.5947684",
        "time": "08:00"
    },
    {
        "name": "Ramya",
        "pickup_location": "12.90351166, 77.64296042",
        "drop_location": "12.9208218, 77.6806839",
        "time": "09:30"
    },
    {
        "name": "Jaswin Anand",
        "pickup_location": "12.90433156, 77.62858211",
        "drop_location": "12.9150268, 77.63677",
        "time": "08:30"
    },
    {
        "name": "Sneha Manjunath",
        "pickup_location": "12.90506447, 77.51010852",
        "drop_location": "12.9287723, 77.6329717",
        "time": "09:15"
    },
    {
        "name": "Smita Swain",
        "pickup_location": "12.90516981, 77.65037932",
        "drop_location": "12.92430183, 77.64966416",
        "time": "07:45"
    },
    {
        "name": "Mona Lisa",
        "pickup_location": "12.90521307, 77.68865861",
        "drop_location": "12.9147008, 77.6445964",
        "time": "09:00"
    },
    {
        "name": "Shikha T",
        "pickup_location": "12.90524302, 77.6503686",
        "drop_location": "12.92597498, 77.6805886",
        "time": "10:30"
    },
    {
        "name": "Monika",
        "pickup_location": "12.90533823, 77.64798045",
        "drop_location": "12.8900824, 77.6654022",
        "time": "09:30"
    },
    {
        "name": "Nishant",
        "pickup_location": "12.90565214, 77.67566887",
        "drop_location": "12.9120763, 77.6379148",
        "time": "10:30"
    },
    {
        "name": "Hamsini",
        "pickup_location": "12.90601975, 77.5981328",
        "drop_location": "12.97361097, 77.5861962",
        "time": "09:55"
    },
    {
        "name": "Meet Ahuja",
        "pickup_location": "12.90627949, 77.69879524",
        "drop_location": "12.92658949, 77.69493104",
        "time": "10:00"
    },
    {
        "name": "Subin",
        "pickup_location": "12.90665787, 77.63918728",
        "drop_location": "12.9358189, 77.6178125",
        "time": "08:46"
    },
    {
        "name": "Ragini",
        "pickup_location": "12.90686045, 77.67598293",
        "drop_location": "12.9879659, 77.6895248",
        "time": "08:00"
    },
    {
        "name": "Aniz",
        "pickup_location": "12.90717353, 77.6303849",
        "drop_location": "12.9343199, 77.6021912",
        "time": "09:30"
    },
    {
        "name": "Prakshi",
        "pickup_location": "12.90741353, 77.69022907",
        "drop_location": "12.9264733, 77.6657512",
        "time": "09:45"
    },
    {
        "name": "Apurba Saha",
        "pickup_location": "12.90748657, 77.70574083",
        "drop_location": "12.925723, 77.6656428",
        "time": "11:45"
    },
    {
        "name": "Arshdeep",
        "pickup_location": "12.9076818, 77.68341091",
        "drop_location": "12.93018208, 77.68676272",
        "time": "09:30"
    },
    {
        "name": "Shruti Waghmare",
        "pickup_location": "12.90779841, 77.63411682",
        "drop_location": "12.9618989, 77.5996331",
        "time": "09:30"
    },
    {
        "name": "Divya",
        "pickup_location": "12.908052, 77.642268",
        "drop_location": "12.9134783, 77.6664892",
        "time": "08:25"
    },
    {
        "name": "Asha",
        "pickup_location": "12.90807412, 77.64842216",
        "drop_location": "12.93283475, 77.60281262",
        "time": "08:30"
    },
    {
        "name": "Aruna P",
        "pickup_location": "12.90816163, 77.67840084",
        "drop_location": "12.91492294, 77.64458092",
        "time": "09:20"
    },
    {
        "name": "Kumari Trishya",
        "pickup_location": "12.90817323, 77.67981435",
        "drop_location": "12.9341053, 77.6128593",
        "time": "11:30"
    },
    {
        "name": "Prasanthi",
        "pickup_location": "12.90826656, 77.67914018",
        "drop_location": "12.93188306, 77.61444762",
        "time": "08:45"
    },
    {
        "name": "Jill",
        "pickup_location": "12.9083108, 77.63788405",
        "drop_location": "12.9489545, 77.6902283",
        "time": "09:10"
    },
    {
        "name": "Rushabh Hemani",
        "pickup_location": "12.90832126, 77.63780895",
        "drop_location": "13.0934032, 77.5950404",
        "time": "08:15"
    },
    {
        "name": "Subhashree",
        "pickup_location": "12.90840154, 77.67865094",
        "drop_location": "12.9520661, 77.6439282",
        "time": "08:45"
    },
    {
        "name": "Shreya Gupta",
        "pickup_location": "12.90852298, 77.65160735",
        "drop_location": "12.93351269, 77.60121566",
        "time": "08:40"
    },
    {
        "name": "Arun",
        "pickup_location": "12.90866655, 77.63203157",
        "drop_location": "12.93734612, 77.6247213",
        "time": "10:30"
    },
    {
        "name": "Prachi Gautam",
        "pickup_location": "12.90876329, 77.66254519",
        "drop_location": "12.9275331, 77.6331478",
        "time": "10:00"
    },
    {
        "name": "Devi s",
        "pickup_location": "12.90876718, 77.65165457",
        "drop_location": "12.9148847, 77.6382957",
        "time": "01:40"
    },
    {
        "name": "Amit Singh",
        "pickup_location": "12.90892207, 77.67493865",
        "drop_location": "12.9397242, 77.6897052",
        "time": "08:40"
    },
    {
        "name": "Divya",
        "pickup_location": "12.90893503, 77.68483981",
        "drop_location": "12.91251344, 77.641341",
        "time": "21:10"
    },
    {
        "name": "Ananya Dey",
        "pickup_location": "12.90965518, 77.69711724",
        "drop_location": "12.92687182, 77.69493104",
        "time": "10:15"
    },
    {
        "name": "Alisha Hafiz",
        "pickup_location": "12.91008094, 77.68153006",
        "drop_location": "12.93944813, 77.68944408",
        "time": "11:00"
    },
    {
        "name": "Sona",
        "pickup_location": "12.91029229, 77.68451921",
        "drop_location": "12.98797469, 77.58732877",
        "time": "11:00"
    },
    {
        "name": "D",
        "pickup_location": "12.910306, 77.64199",
        "drop_location": "12.8994981, 77.597125",
        "time": "08:00"
    },
    {
        "name": "Rahul chhipa",
        "pickup_location": "12.91040971, 77.6224818",
        "drop_location": "12.9140177, 77.6448404",
        "time": "21:10"
    },
    {
        "name": "Mamta Nawalgaria",
        "pickup_location": "12.910842, 77.67554417",
        "drop_location": "12.9786313, 77.6590812",
        "time": "17:05"
    },
    {
        "name": "Nitin",
        "pickup_location": "12.91104357, 77.57400871",
        "drop_location": "12.9029967, 77.631917",
        "time": "09:30"
    },
    {
        "name": "Simran Kaur",
        "pickup_location": "12.91141474, 77.65177998",
        "drop_location": "13.0043911, 77.7173522",
        "time": "10:00"
    },
    {
        "name": "Namitha",
        "pickup_location": "12.91180036, 77.6641601",
        "drop_location": "12.9081024, 77.6435134",
        "time": "19:00"
    },
    {
        "name": "Avani",
        "pickup_location": "12.91215055, 77.60625597",
        "drop_location": "12.9405997, 77.5737633",
        "time": "15:45"
    },
    {
        "name": "Trishi Saxena",
        "pickup_location": "12.91239159, 77.64054404",
        "drop_location": "12.96459196, 77.7144272",
        "time": "16:50"
    },
    {
        "name": "Srushti",
        "pickup_location": "12.91276849, 77.62849367",
        "drop_location": "12.9416401, 77.69093007",
        "time": "09:30"
    },
    {
        "name": "Samreen",
        "pickup_location": "12.91332504, 77.66462045",
        "drop_location": "12.95783075, 77.57642594",
        "time": "07:30"
    },
    {
        "name": "Poornima Prabhu",
        "pickup_location": "12.91402652, 77.61614057",
        "drop_location": "12.93321583, 77.60164769",
        "time": "09:30"
    },
    {
        "name": "Abhidha Pandit",
        "pickup_location": "12.91405105, 77.67082422",
        "drop_location": "12.92670334, 77.66572974",
        "time": "10:25"
    },
    {
        "name": "Chithra Muralidhar",
        "pickup_location": "12.91417245, 77.71634222",
        "drop_location": "12.8879314, 77.7447326",
        "time": "07:40"
    },
    {
        "name": "Pallavi Bhagat",
        "pickup_location": "12.91439582, 77.70251628",
        "drop_location": "12.9111547, 77.6837388",
        "time": "11:00"
    },
    {
        "name": "Uma",
        "pickup_location": "12.91529265, 77.71025535",
        "drop_location": "12.92070677, 77.6806839",
        "time": "09:00"
    },
    {
        "name": "Sahana Patil",
        "pickup_location": "12.91534179, 77.50390162",
        "drop_location": "12.91146915, 77.52097256",
        "time": "07:00"
    },
    {
        "name": "Roshanjit Kar Bhowmik",
        "pickup_location": "12.91590438, 77.60836384",
        "drop_location": "12.9124674, 77.6396905",
        "time": "09:30"
    },
    {
        "name": "Raghav",
        "pickup_location": "12.91736489, 77.68924057",
        "drop_location": "12.9222875, 77.6796457",
        "time": "10:30"
    },
    {
        "name": "Swathi kumaraswamy",
        "pickup_location": "12.91765953, 77.5451581",
        "drop_location": "12.9500029, 77.6441439",
        "time": "08:00"
    },
    {
        "name": "Videsha",
        "pickup_location": "12.9184638, 77.63211315",
        "drop_location": "12.9362362, 77.6061888",
        "time": "06:10"
    },
    {
        "name": "Videsha Bansal",
        "pickup_location": "12.91872623, 77.63221282",
        "drop_location": "12.9362362, 77.6061888",
        "time": "06:00"
    },
    {
        "name": "Kedar",
        "pickup_location": "12.91872749, 77.64805532",
        "drop_location": "12.9434156, 77.6986434",
        "time": "07:45"
    },
    {
        "name": "Poorna",
        "pickup_location": "12.91914186, 77.63062575",
        "drop_location": "12.901678, 77.6329394",
        "time": "10:09"
    },
    {
        "name": "Kush",
        "pickup_location": "12.91928408, 77.63504668",
        "drop_location": "12.9940544, 77.661129",
        "time": "09:30"
    },
    {
        "name": "Sanjeev koyad",
        "pickup_location": "12.91965869, 77.61561032",
        "drop_location": "12.93771758, 77.62754259",
        "time": "09:30"
    },
    {
        "name": "Anupriya",
        "pickup_location": "12.92003285, 77.68354318",
        "drop_location": "12.89034385, 77.66792345",
        "time": "16:30"
    },
    {
        "name": "Piyush Mayank",
        "pickup_location": "12.92030912, 77.66545824",
        "drop_location": "12.9196873, 77.6456448",
        "time": "10:30"
    },
    {
        "name": "Eranna",
        "pickup_location": "12.9204277, 77.51683534",
        "drop_location": "13.04770457, 77.61991768",
        "time": "08:33"
    },
    {
        "name": "Zamra",
        "pickup_location": "12.92066494, 77.68070535",
        "drop_location": "12.9468099, 77.7087789",
        "time": "17:30"
    },
    {
        "name": "Manoj",
        "pickup_location": "12.92072769, 77.68069462",
        "drop_location": "12.9864651, 77.59551",
        "time": "08:45"
    },
    {
        "name": "Sachin",
        "pickup_location": "12.92085248, 77.63475052",
        "drop_location": "12.9181269, 77.5918946",
        "time": "07:45"
    },
    {
        "name": "Vishal",
        "pickup_location": "12.92121593, 77.6186117",
        "drop_location": "12.91156945, 77.64921486",
        "time": "08:30"
    },
    {
        "name": "Sowmya",
        "pickup_location": "12.92123003, 77.60816265",
        "drop_location": "12.8922997, 77.5853648",
        "time": "15:00"
    },
    {
        "name": "Geetha M",
        "pickup_location": "12.92219159, 77.64887918",
        "drop_location": "12.9753127, 77.7313669",
        "time": "23:20"
    },
    {
        "name": "HSR",
        "pickup_location": "12.92222217, 77.63354961",
        "drop_location": "12.9265514, 77.66545885",
        "time": "10:38"
    },
    {
        "name": "Sai mani",
        "pickup_location": "12.9243216, 77.62420586",
        "drop_location": "12.9816856, 77.5875978",
        "time": "09:30"
    },
    {
        "name": "Michelle",
        "pickup_location": "12.92513444, 77.67091976",
        "drop_location": "12.91389474, 77.62436053",
        "time": "07:40"
    },
    {
        "name": "Ann",
        "pickup_location": "12.92517853, 77.63261785",
        "drop_location": "12.87312403, 77.61136537",
        "time": "17:22"
    },
    {
        "name": "siddartha reddy",
        "pickup_location": "12.92532533, 77.67816925",
        "drop_location": "12.92237592, 77.6692895",
        "time": "10:20"
    },
    {
        "name": "Mahak Garg",
        "pickup_location": "12.92548474, 77.66473967",
        "drop_location": "12.9261339, 77.6811843",
        "time": "10:00"
    },
    {
        "name": "Chelsi",
        "pickup_location": "12.92558045, 77.67092886",
        "drop_location": "12.91863716, 77.67102222",
        "time": "09:45"
    },
    {
        "name": "Sai",
        "pickup_location": "12.92573766, 77.67757331",
        "drop_location": "12.9268079, 77.6916992",
        "time": "10:14"
    },
    {
        "name": "Varun Baruah",
        "pickup_location": "12.92629493, 77.6669695",
        "drop_location": "12.9391577, 77.6254838",
        "time": "09:45"
    },
    {
        "name": "Ambujam Saranya",
        "pickup_location": "12.92637105, 77.61467841",
        "drop_location": "12.9269902, 77.68282531",
        "time": "09:10"
    },
    {
        "name": "Baiju",
        "pickup_location": "12.92670197, 77.61600678",
        "drop_location": "12.9393719, 77.6977842",
        "time": "11:05"
    },
    {
        "name": "Shinjini Paul",
        "pickup_location": "12.92690692, 77.67237455",
        "drop_location": "12.9369014, 77.6888371",
        "time": "10:00"
    },
    {
        "name": "Pushkar",
        "pickup_location": "12.92693678, 77.51986101",
        "drop_location": "12.9368649, 77.5201338",
        "time": "10:00"
    },
    {
        "name": "Mugdha",
        "pickup_location": "12.92698197, 77.67263618",
        "drop_location": "12.9414129, 77.6905938",
        "time": "10:10"
    },
    {
        "name": "Mary",
        "pickup_location": "12.92723651, 77.60866392",
        "drop_location": "12.96260414, 77.5964362",
        "time": "11:15"
    },
    {
        "name": "Sushmita",
        "pickup_location": "12.92758795, 77.63880342",
        "drop_location": "12.9717926, 77.6182882",
        "time": "09:15"
    },
    {
        "name": "Dinesh",
        "pickup_location": "12.92774223, 77.63311561",
        "drop_location": "12.9050356, 77.5738518",
        "time": "16:00"
    },
    {
        "name": "Ravi Pingali",
        "pickup_location": "12.92820177, 77.62855751",
        "drop_location": "12.935438, 77.6151299",
        "time": "10:15"
    },
    {
        "name": "Harsheen Kaur",
        "pickup_location": "12.92824571, 77.67489321",
        "drop_location": "12.9521251, 77.6406988",
        "time": "10:15"
    },
    {
        "name": "Ayushi Gaurav",
        "pickup_location": "12.92844107, 77.66995064",
        "drop_location": "12.8911655, 77.5962236",
        "time": "09:00"
    },
    {
        "name": "Arwa",
        "pickup_location": "12.92846647, 77.67073195",
        "drop_location": "12.9332801, 77.6835518",
        "time": "08:58"
    },
    {
        "name": "Swathi",
        "pickup_location": "12.92898142, 77.63301461",
        "drop_location": "12.9285954, 77.5793767",
        "time": "18:15"
    },
    {
        "name": "Priyanka",
        "pickup_location": "12.92943379, 77.70400807",
        "drop_location": "12.94348222, 77.69458827",
        "time": "10:40"
    },
    {
        "name": "Pujitha",
        "pickup_location": "12.92977352, 77.67427925",
        "drop_location": "12.9823463, 77.7080483",
        "time": "08:30"
    },
    {
        "name": "Prachi",
        "pickup_location": "12.93010569, 77.67351887",
        "drop_location": "12.9407349, 77.6893115",
        "time": "10:15"
    },
    {
        "name": "Somya Gupta",
        "pickup_location": "12.93020439, 77.74283221",
        "drop_location": "13.08462774, 77.640471",
        "time": "08:40"
    },
    {
        "name": "Jd",
        "pickup_location": "12.930223, 77.67646945",
        "drop_location": "12.931869, 77.68523",
        "time": "07:45"
    },
    {
        "name": "Tanima Das",
        "pickup_location": "12.93150289, 77.60879715",
        "drop_location": "12.969847, 77.6107682",
        "time": "08:45"
    },
    {
        "name": "Vaishnavi",
        "pickup_location": "12.93266757, 77.63661742",
        "drop_location": "12.9326438, 77.6031313",
        "time": "08:10"
    },
    {
        "name": "SWARNALI Roy",
        "pickup_location": "12.93275109, 77.60283408",
        "drop_location": "12.9275518, 77.638287",
        "time": "18:30"
    },
    {
        "name": "Bhawana",
        "pickup_location": "12.93277201, 77.60289845",
        "drop_location": "13.0382099, 77.5182395",
        "time": "18:45"
    },
    {
        "name": "Tanmay Agarwal",
        "pickup_location": "12.93296888, 77.63443541",
        "drop_location": "12.9800399, 77.6403289",
        "time": "09:30"
    },
    {
        "name": "Rahul sarkar",
        "pickup_location": "12.93398819, 77.7493254",
        "drop_location": "12.93395982, 77.62373071",
        "time": "11:00"
    },
    {
        "name": "Sapna Goyal",
        "pickup_location": "12.933998, 77.628265",
        "drop_location": "12.9602407, 77.6483417",
        "time": "09:15"
    },
    {
        "name": "Rahul sarkar",
        "pickup_location": "12.93399865, 77.74934685",
        "drop_location": "12.93387616, 77.6237629",
        "time": "10:30"
    },
    {
        "name": "Kiran",
        "pickup_location": "12.93476594, 77.62947284",
        "drop_location": "12.9255714, 77.6078815",
        "time": "18:30"
    },
    {
        "name": "Megha Mogra",
        "pickup_location": "12.93574975, 77.70580997",
        "drop_location": "12.97568027, 77.60323002",
        "time": "10:00"
    },
    {
        "name": "Unnar",
        "pickup_location": "12.93590821, 77.63198942",
        "drop_location": "12.9313462, 77.6164506",
        "time": "10:45"
    },
    {
        "name": "Anitha",
        "pickup_location": "12.937124, 77.624382",
        "drop_location": "12.97260316, 77.5999614",
        "time": "21:05"
    },
    {
        "name": "Ayushi Agarwal",
        "pickup_location": "12.9372183, 77.6293398",
        "drop_location": "12.95178633, 77.64235828",
        "time": "09:07"
    },
    {
        "name": "Sanchita",
        "pickup_location": "12.937375, 77.621936",
        "drop_location": "12.97188325, 77.59588305",
        "time": "09:15"
    },
    {
        "name": "Yaash Agarwal",
        "pickup_location": "12.93787466, 77.62695401",
        "drop_location": "12.9592308, 77.6468614",
        "time": "09:00"
    },
    {
        "name": "Vanishree KN",
        "pickup_location": "12.938021, 77.568683",
        "drop_location": "12.96584, 77.603725",
        "time": "08:30"
    },
    {
        "name": "Aniket Chakraborty",
        "pickup_location": "12.93804396, 77.61764408",
        "drop_location": "12.9312742, 77.6894981",
        "time": "11:00"
    },
    {
        "name": "Sowmiya Manoharan",
        "pickup_location": "12.93861675, 77.72531135",
        "drop_location": "12.9591274, 77.7464049",
        "time": "08:30"
    },
    {
        "name": "Kriti Agarwal",
        "pickup_location": "12.93931122, 77.73761025",
        "drop_location": "12.93528328, 77.6942932",
        "time": "09:30"
    },
    {
        "name": "Chinmayee Dande",
        "pickup_location": "12.93934258, 77.73767462",
        "drop_location": "12.9402154, 77.6891012",
        "time": "09:15"
    },
    {
        "name": "sudharsana",
        "pickup_location": "12.93953112, 77.63175622",
        "drop_location": "12.9372847, 77.6099462",
        "time": "10:00"
    },
    {
        "name": "Shivangi",
        "pickup_location": "12.94017081, 77.63141535",
        "drop_location": "12.97172643, 77.5959367",
        "time": "10:30"
    },
    {
        "name": "Rhea",
        "pickup_location": "12.94159064, 77.69063671",
        "drop_location": "12.9299812, 77.6032879",
        "time": "17:00"
    },
    {
        "name": "Twinkle Mali",
        "pickup_location": "12.94162201, 77.69054015",
        "drop_location": "12.953106, 77.6924979",
        "time": "18:30"
    },
    {
        "name": "Jothirmaya Sanjith",
        "pickup_location": "12.94180688, 77.70318208",
        "drop_location": "12.98291222, 77.72487544",
        "time": "15:35"
    },
    {
        "name": "Sneha Agarwal",
        "pickup_location": "12.94303027, 77.65396357",
        "drop_location": "12.8495209, 77.6636614",
        "time": "10:10"
    },
    {
        "name": "Manish",
        "pickup_location": "12.94318861, 77.74998915",
        "drop_location": "12.96677536, 77.72324098",
        "time": "11:30"
    },
    {
        "name": "Prasad D",
        "pickup_location": "12.94342435, 77.62718046",
        "drop_location": "12.92895058, 77.63297798",
        "time": "10:40"
    },
    {
        "name": "AYUSHI SINGH",
        "pickup_location": "12.94439582, 77.59983725",
        "drop_location": "12.9751082, 77.6024699",
        "time": "09:45"
    },
    {
        "name": "Sonia",
        "pickup_location": "12.94460621, 77.70786728",
        "drop_location": "12.9489545, 77.6902283",
        "time": "09:00"
    },
    {
        "name": "Distant",
        "pickup_location": "12.94491955, 77.7537999",
        "drop_location": "12.9093746, 77.64322",
        "time": "08:50"
    },
    {
        "name": "Rimi",
        "pickup_location": "12.94514957, 77.62879961",
        "drop_location": "12.9876626, 77.5945186",
        "time": "08:15"
    },
    {
        "name": "Swati",
        "pickup_location": "12.94597306, 77.67876846",
        "drop_location": "12.98162079, 77.64564502",
        "time": "11:15"
    },
    {
        "name": "Sikha",
        "pickup_location": "12.94617751, 77.71424801",
        "drop_location": "12.97313257, 77.6087617",
        "time": "10:00"
    },
    {
        "name": "Swati Pritam",
        "pickup_location": "12.94685221, 77.71404338",
        "drop_location": "12.931274, 77.6895012",
        "time": "12:10"
    },
    {
        "name": "Mayank Tyagi",
        "pickup_location": "12.94782813, 77.67606414",
        "drop_location": "12.9779691, 77.6436622",
        "time": "10:00"
    },
    {
        "name": "Pratima",
        "pickup_location": "12.94922131, 77.64536379",
        "drop_location": "12.89470204, 77.65838082",
        "time": "03:30"
    },
    {
        "name": "Shivendra Pratap Singh",
        "pickup_location": "12.94981707, 77.71284376",
        "drop_location": "12.9429928, 77.6924308",
        "time": "10:01"
    },
    {
        "name": "Poulamita Mondal",
        "pickup_location": "12.95184478, 77.71689887",
        "drop_location": "12.9791899, 77.709438",
        "time": "08:30"
    },
    {
        "name": "Yamini",
        "pickup_location": "12.95308489, 77.71253252",
        "drop_location": "12.95863157, 77.64882567",
        "time": "08:30"
    },
    {
        "name": "Megha",
        "pickup_location": "12.95311912, 77.71595654",
        "drop_location": "12.9253831, 77.6315577",
        "time": "10:10"
    },
    {
        "name": "Priyanka",
        "pickup_location": "12.95337385, 77.71289202",
        "drop_location": "12.9356633, 77.695532",
        "time": "12:12"
    },
    {
        "name": "Melissa",
        "pickup_location": "12.95361466, 77.62121267",
        "drop_location": "12.97312438, 77.61415324",
        "time": "09:15"
    },
    {
        "name": "Nishali",
        "pickup_location": "12.95398853, 77.65082466",
        "drop_location": "12.9287884, 77.63297267",
        "time": "08:45"
    },
    {
        "name": "Sourav Jain",
        "pickup_location": "12.95518, 77.71719827",
        "drop_location": "12.98924064, 77.7309907",
        "time": "09:50"
    },
    {
        "name": "Rohit Agarwal",
        "pickup_location": "12.95519561, 77.717229",
        "drop_location": "12.9853241, 77.7040855",
        "time": "10:30"
    },
    {
        "name": "Dipraj",
        "pickup_location": "12.95555396, 77.65400484",
        "drop_location": "12.9184368, 77.6709389",
        "time": "09:55"
    },
    {
        "name": "Ananya Agarwal",
        "pickup_location": "12.95557902, 77.65079932",
        "drop_location": "12.95953253, 77.643414",
        "time": "09:00"
    },
    {
        "name": "Charu",
        "pickup_location": "12.95572699, 77.65249156",
        "drop_location": "12.9561584, 77.64073353",
        "time": "09:00"
    },
    {
        "name": "Nusrath Sultana",
        "pickup_location": "12.95650218, 77.63792207",
        "drop_location": "12.97844916, 77.6383839",
        "time": "09:30"
    },
    {
        "name": "Dinesh Murugan",
        "pickup_location": "12.95663785, 77.63726517",
        "drop_location": "12.9782819, 77.6383839",
        "time": "12:20"
    },
    {
        "name": "Alice Shobhana",
        "pickup_location": "12.95670208, 77.73390114",
        "drop_location": "12.9834663, 77.7217595",
        "time": "09:30"
    },
    {
        "name": "Rihana",
        "pickup_location": "12.95737042, 77.71048738",
        "drop_location": "12.9718875, 77.6127853",
        "time": "08:00"
    },
    {
        "name": "Rupali",
        "pickup_location": "12.95760589, 77.70550487",
        "drop_location": "12.92820602, 77.63689501",
        "time": "08:30"
    },
    {
        "name": "Arshiya",
        "pickup_location": "12.9576895, 77.65906417",
        "drop_location": "12.9716935, 77.6192229",
        "time": "09:20"
    },
    {
        "name": "Muthuram",
        "pickup_location": "12.95779823, 77.70829761",
        "drop_location": "12.9073316, 77.5996453",
        "time": "08:30"
    },
    {
        "name": "Arjun",
        "pickup_location": "12.958082, 77.614452",
        "drop_location": "12.9797318, 77.6068566",
        "time": "09:45"
    },
    {
        "name": "Tejaswini Sahoo",
        "pickup_location": "12.9596851, 77.699783",
        "drop_location": "12.94024759, 77.68857314",
        "time": "12:45"
    },
    {
        "name": "Rishita Singh",
        "pickup_location": "12.96009076, 77.64200747",
        "drop_location": "12.9287723, 77.6329717",
        "time": "09:30"
    },
    {
        "name": "Puneet",
        "pickup_location": "12.96028774, 77.64322668",
        "drop_location": "12.9358018, 77.6266229",
        "time": "19:00"
    },
    {
        "name": "sreenivasa",
        "pickup_location": "12.96043995, 77.64687947",
        "drop_location": "12.8575579, 77.7864057",
        "time": "10:00"
    },
    {
        "name": "Kirti",
        "pickup_location": "12.96079998, 77.6558958",
        "drop_location": "12.9287884, 77.63297267",
        "time": "08:30"
    },
    {
        "name": "Niketa",
        "pickup_location": "12.9609713, 77.59778735",
        "drop_location": "12.9519715, 77.6086723",
        "time": "10:50"
    },
    {
        "name": "Kirti Acharjya",
        "pickup_location": "12.96099698, 77.65589154",
        "drop_location": "12.92889777, 77.63292878",
        "time": "08:45"
    },
    {
        "name": "Aloka",
        "pickup_location": "12.9617239, 77.64690712",
        "drop_location": "12.98602297, 77.64508208",
        "time": "08:30"
    },
    {
        "name": "Shaziya",
        "pickup_location": "12.96230108, 77.66906408",
        "drop_location": "12.9691935, 77.635805",
        "time": "08:50"
    },
    {
        "name": "Ashutosh",
        "pickup_location": "12.96262555, 77.64217261",
        "drop_location": "12.9574265, 77.5858298",
        "time": "09:35"
    },
    {
        "name": "Syed",
        "pickup_location": "12.96316732, 77.54830409",
        "drop_location": "12.9658618, 77.5418466",
        "time": "14:35"
    },
    {
        "name": "Aashish Pereira",
        "pickup_location": "12.96366308, 77.59845674",
        "drop_location": "12.97569624, 77.60511738",
        "time": "09:45"
    },
    {
        "name": "Richa",
        "pickup_location": "12.96453621, 77.58538848",
        "drop_location": "12.89575676, 77.60854691",
        "time": "18:30"
    },
    {
        "name": "Dhruv Kant Ladia",
        "pickup_location": "12.96491619, 77.64598255",
        "drop_location": "12.9029365, 77.648394",
        "time": "09:45"
    },
    {
        "name": "Dr Janhavi",
        "pickup_location": "12.96556788, 77.59997435",
        "drop_location": "12.972946, 77.636794",
        "time": "18:00"
    },
    {
        "name": "Vikrant Sakharwade",
        "pickup_location": "12.96595073, 77.72096875",
        "drop_location": "12.9743998, 77.7120655",
        "time": "09:45"
    },
    {
        "name": "Ruhi Soni",
        "pickup_location": "12.96613914, 77.64830758",
        "drop_location": "12.97181007, 77.59591524",
        "time": "09:00"
    },
    {
        "name": "Suhas",
        "pickup_location": "12.966158, 77.634376",
        "drop_location": "12.9783692, 77.6408356",
        "time": "08:23"
    },
    {
        "name": "Rosemary Alex",
        "pickup_location": "12.96617886, 77.61441839",
        "drop_location": "12.9564997, 77.5852551",
        "time": "08:30"
    },
    {
        "name": "Bhavya Shree",
        "pickup_location": "12.96633741, 77.6144159",
        "drop_location": "12.97324954, 77.61686095",
        "time": "18:00"
    },
    {
        "name": "Shweta",
        "pickup_location": "12.96637548, 77.76143175",
        "drop_location": "12.985608, 77.7469171",
        "time": "11:05"
    },
    {
        "name": "Nandani",
        "pickup_location": "12.966953, 77.735975",
        "drop_location": "12.96279, 77.7147137",
        "time": "08:30"
    },
    {
        "name": "Rajnandani",
        "pickup_location": "12.96697585, 77.73622932",
        "drop_location": "12.96279, 77.7147137",
        "time": "08:25"
    },
    {
        "name": "Hima Greshma",
        "pickup_location": "12.96718403, 77.73975731",
        "drop_location": "12.92477158, 77.67028662",
        "time": "07:50"
    },
    {
        "name": "Mahima",
        "pickup_location": "12.96730885, 77.72484694",
        "drop_location": "12.9819251, 77.7226787",
        "time": "08:45"
    },
    {
        "name": "Vendi Prasanthi",
        "pickup_location": "12.96770998, 77.61039642",
        "drop_location": "12.97163626, 77.60075121",
        "time": "21:45"
    },
    {
        "name": "Dibyajyoti Dash",
        "pickup_location": "12.96880752, 77.71622531",
        "drop_location": "12.931563, 77.6155746",
        "time": "08:45"
    },
    {
        "name": "Visalakshi",
        "pickup_location": "12.96885032, 77.6741179",
        "drop_location": "12.9598508, 77.6490955",
        "time": "14:30"
    },
    {
        "name": "Janesh",
        "pickup_location": "12.96997052, 77.76827578",
        "drop_location": "12.9845336, 77.7058598",
        "time": "11:10"
    },
    {
        "name": "Kaustuv Sahu",
        "pickup_location": "12.97029639, 77.68227728",
        "drop_location": "12.9794203, 77.6661495",
        "time": "10:00"
    },
    {
        "name": "Keshav Gupta",
        "pickup_location": "12.97034867, 77.68226655",
        "drop_location": "12.9794203, 77.6661495",
        "time": "10:00"
    },
    {
        "name": "Yashodha",
        "pickup_location": "12.9706209, 77.64922987",
        "drop_location": "12.99427355, 77.66115071",
        "time": "17:30"
    },
    {
        "name": "Latha",
        "pickup_location": "12.97087778, 77.63008576",
        "drop_location": "12.9837242, 77.5754252",
        "time": "21:40"
    },
    {
        "name": "Sreejani",
        "pickup_location": "12.97172843, 77.70340608",
        "drop_location": "12.9414129, 77.6905938",
        "time": "11:45"
    },
    {
        "name": "Ruella D",
        "pickup_location": "12.97174329, 77.628696",
        "drop_location": "12.98580352, 77.67105926",
        "time": "12:45"
    },
    {
        "name": "Sindhu",
        "pickup_location": "12.97185443, 77.62859282",
        "drop_location": "12.97389217, 77.65466517",
        "time": "14:30"
    },
    {
        "name": "Venkat Suman",
        "pickup_location": "12.97209049, 77.6458445",
        "drop_location": "12.9350282, 77.6284492",
        "time": "10:05"
    },
    {
        "name": "Mahesh",
        "pickup_location": "12.97214594, 77.52349084",
        "drop_location": "12.9252069, 77.6376701",
        "time": "08:00"
    },
    {
        "name": "Gopika",
        "pickup_location": "12.97415182, 77.63947862",
        "drop_location": "12.97245178, 77.60422028",
        "time": "08:45"
    },
    {
        "name": "Shruti",
        "pickup_location": "12.97454028, 77.66519737",
        "drop_location": "13.0488944, 77.6202282",
        "time": "09:30"
    },
    {
        "name": "Sangeetha",
        "pickup_location": "12.97464151, 77.74381187",
        "drop_location": "12.9873558, 77.7397588",
        "time": "10:00"
    },
    {
        "name": "Kavinaya P",
        "pickup_location": "12.97516893, 77.65294553",
        "drop_location": "12.95153111, 77.64004287",
        "time": "09:30"
    },
    {
        "name": "Mouparna Ghosal",
        "pickup_location": "12.97550109, 77.70680451",
        "drop_location": "12.9207576, 77.6686651",
        "time": "09:15"
    },
    {
        "name": "Sambhavi",
        "pickup_location": "12.97553245, 77.7067616",
        "drop_location": "12.92696474, 77.6916992",
        "time": "10:00"
    },
    {
        "name": "Jay",
        "pickup_location": "12.97572952, 77.53134192",
        "drop_location": "12.9362362, 77.6061888",
        "time": "08:15"
    },
    {
        "name": "Riya",
        "pickup_location": "12.9763138, 77.68309635",
        "drop_location": "12.94911133, 77.69019611",
        "time": "09:07"
    },
    {
        "name": "Sneha Basu",
        "pickup_location": "12.97715156, 77.67837685",
        "drop_location": "12.9208758, 77.6831638",
        "time": "08:00"
    },
    {
        "name": "Manasvi Patel",
        "pickup_location": "12.97754038, 77.63922387",
        "drop_location": "12.936329, 77.610998",
        "time": "10:00"
    },
    {
        "name": "Latha",
        "pickup_location": "12.97766132, 77.62355801",
        "drop_location": "12.9837242, 77.5754252",
        "time": "09:45"
    },
    {
        "name": "Srushty",
        "pickup_location": "12.97788137, 77.6703809",
        "drop_location": "12.9620518, 77.6457629",
        "time": "21:30"
    },
    {
        "name": "Jayanthi",
        "pickup_location": "12.97829892, 77.62327584",
        "drop_location": "12.92522175, 77.62963663",
        "time": "07:30"
    },
    {
        "name": "Sijal",
        "pickup_location": "12.97976273, 77.68049115",
        "drop_location": "12.9693618, 77.637923",
        "time": "09:00"
    },
    {
        "name": "Biswashree Mishra",
        "pickup_location": "12.98164946, 77.68234767",
        "drop_location": "12.9414178, 77.6905818",
        "time": "09:45"
    },
    {
        "name": "Krishna Jyothi",
        "pickup_location": "12.98231006, 77.65811806",
        "drop_location": "12.9773006, 77.6724627",
        "time": "16:40"
    },
    {
        "name": "Mika9875390734",
        "pickup_location": "12.98244093, 77.6610653",
        "drop_location": "12.88755308, 77.57903816",
        "time": "08:15"
    },
    {
        "name": "Nisha Mehta",
        "pickup_location": "12.98250311, 77.70805902",
        "drop_location": "12.913821, 77.6708135",
        "time": "17:50"
    },
    {
        "name": "Reeba",
        "pickup_location": "12.98318542, 77.64051827",
        "drop_location": "13.00865445, 77.65093847",
        "time": "17:40"
    },
    {
        "name": "Yashasvi Singh",
        "pickup_location": "12.98330584, 77.67396747",
        "drop_location": "12.9786313, 77.6590812",
        "time": "11:00"
    },
    {
        "name": "Nuzhat",
        "pickup_location": "12.98361587, 77.67921525",
        "drop_location": "12.9924312, 77.6646575",
        "time": "08:46"
    },
    {
        "name": "Santosh Nair",
        "pickup_location": "12.98496278, 77.66654044",
        "drop_location": "12.93244805, 77.60989414",
        "time": "21:00"
    },
    {
        "name": "Akshita Gupta",
        "pickup_location": "12.98567208, 77.66792841",
        "drop_location": "12.9716428, 77.5959367",
        "time": "09:15"
    },
    {
        "name": "Swarnim",
        "pickup_location": "12.98765631, 77.73714918",
        "drop_location": "12.90647253, 77.67475608",
        "time": "20:45"
    },
    {
        "name": "Sangita",
        "pickup_location": "12.98900248, 77.52712288",
        "drop_location": "12.9020982, 77.5954663",
        "time": "08:50"
    },
    {
        "name": "Akshatha Prabhu",
        "pickup_location": "12.99044023, 77.68610322",
        "drop_location": "12.93072304, 77.69130295",
        "time": "08:45"
    },
    {
        "name": "Varsha",
        "pickup_location": "12.9912623, 77.67192592",
        "drop_location": "13.0334862, 77.6373028",
        "time": "09:00"
    },
    {
        "name": "Juanita Marietta Luiz",
        "pickup_location": "12.99128269, 77.6623218",
        "drop_location": "12.95184367, 77.64029784",
        "time": "13:00"
    },
    {
        "name": "Shobana Mathews",
        "pickup_location": "12.99152566, 77.65892068",
        "drop_location": "12.9362362, 77.6061888",
        "time": "08:30"
    },
    {
        "name": "Kavya",
        "pickup_location": "12.99313124, 77.68061134",
        "drop_location": "12.9488534, 77.6889881",
        "time": "09:00"
    },
    {
        "name": "Ganapati Hegde",
        "pickup_location": "12.99684921, 77.69251634",
        "drop_location": "12.9855709, 77.691609",
        "time": "08:45"
    },
    {
        "name": "Tabrez alam khan",
        "pickup_location": "12.99752547, 77.61435836",
        "drop_location": "13.0017633, 77.5815814",
        "time": "02:00"
    },
    {
        "name": "TANZIL B",
        "pickup_location": "12.99780427, 77.76557065",
        "drop_location": "12.8526685, 77.6635812",
        "time": "22:14"
    },
    {
        "name": "Amy",
        "pickup_location": "12.99804497, 77.53429923",
        "drop_location": "12.99873074, 77.54238572",
        "time": "05:30"
    },
    {
        "name": "Lohet",
        "pickup_location": "13.00321015, 77.63109508",
        "drop_location": "13.0112928, 77.5569265",
        "time": "09:00"
    },
    {
        "name": "Bharathkumar",
        "pickup_location": "13.00578313, 77.62784725",
        "drop_location": "12.9758535, 77.6167626",
        "time": "09:45"
    },
    {
        "name": "Jogesh",
        "pickup_location": "13.01105112, 77.64509999",
        "drop_location": "12.93741525, 77.60117419",
        "time": "08:30"
    },
    {
        "name": "Ammu",
        "pickup_location": "13.01253945, 77.76459499",
        "drop_location": "12.98160299, 77.72504381",
        "time": "12:00"
    },
    {
        "name": "Dinakar Subramaniam",
        "pickup_location": "13.013531, 77.535407",
        "drop_location": "12.9381104, 77.6187175",
        "time": "10:00"
    },
    {
        "name": "Shikha",
        "pickup_location": "13.01534231, 77.71593635",
        "drop_location": "12.98316043, 77.75122447",
        "time": "10:00"
    },
    {
        "name": "Poojashree Mohapatra",
        "pickup_location": "13.01934658, 77.59917155",
        "drop_location": "12.97351242, 77.6157371",
        "time": "09:15"
    },
    {
        "name": "Ablin",
        "pickup_location": "13.01998094, 77.6652966",
        "drop_location": "13.0125985, 77.6672872",
        "time": "13:00"
    },
    {
        "name": "Tejasvi",
        "pickup_location": "13.02251805, 77.7624633",
        "drop_location": "12.98792607, 77.7491344",
        "time": "08:50"
    },
    {
        "name": "Pranavi N",
        "pickup_location": "13.02253607, 77.76245236",
        "drop_location": "12.99595293, 77.757761",
        "time": "08:50"
    },
    {
        "name": "karthik",
        "pickup_location": "13.022681, 77.697622",
        "drop_location": "12.9736564, 77.7176694",
        "time": "09:00"
    },
    {
        "name": "karthik",
        "pickup_location": "13.0228582, 77.69766467",
        "drop_location": "12.9736564, 77.7176694",
        "time": "09:00"
    },
    {
        "name": "Simran Agarwal",
        "pickup_location": "13.02610704, 77.60565695",
        "drop_location": "13.04441496, 77.61884167",
        "time": "10:30"
    },
    {
        "name": "Punita Singh",
        "pickup_location": "13.02990922, 77.66046408",
        "drop_location": "12.9260437, 77.6329834",
        "time": "08:30"
    },
    {
        "name": "Sanchit S",
        "pickup_location": "13.03121601, 77.66070582",
        "drop_location": "12.9865438, 77.7335383",
        "time": "11:30"
    },
    {
        "name": "Bharath K R",
        "pickup_location": "13.03194772, 77.56412448",
        "drop_location": "12.9786313, 77.6590812",
        "time": "08:15"
    },
    {
        "name": "Farhan",
        "pickup_location": "13.03399073, 77.63633902",
        "drop_location": "12.9728809, 77.6155746",
        "time": "09:04"
    },
    {
        "name": "Prapti",
        "pickup_location": "13.03638003, 77.69286664",
        "drop_location": "12.9840862, 77.5798617",
        "time": "08:30"
    },
    {
        "name": "Sujata",
        "pickup_location": "13.03975032, 77.66051063",
        "drop_location": "13.0180686, 77.6458978",
        "time": "09:45"
    },
    {
        "name": "Keyur",
        "pickup_location": "13.04532543, 77.62976317",
        "drop_location": "12.8159214, 77.6793813",
        "time": "08:30"
    },
    {
        "name": "Smitha",
        "pickup_location": "13.06850464, 77.56051911",
        "drop_location": "12.95017432, 77.64409984",
        "time": "09:05"
    },
    {
        "name": "Anilkumar",
        "pickup_location": "13.07711116, 77.56354081",
        "drop_location": "12.9600656, 77.6438689",
        "time": "09:00"
    },
    {
        "name": "Mahalakshmi B",
        "pickup_location": "13.07932624, 77.51726341",
        "drop_location": "12.9263281, 77.5154694",
        "time": "08:40"
    },
    {
        "name": "Sharon",
        "pickup_location": "13.08289034, 77.65033186",
        "drop_location": "13.03918653, 77.6021213",
        "time": "07:30"
    },
    {
        "name": "Smrity",
        "pickup_location": "13.11989456, 77.61902387",
        "drop_location": "13.18743463, 77.6749454",
        "time": "09:00"
    },
    {
        "name": "Anand",
        "pickup_location": "13.1380532, 77.5696956",
        "drop_location": "12.9271463, 77.6810426",
        "time": "20:30"
    }
]

optimized_pairs_list = []

@app.get("/optimize-pooling/")
async def optimize_pooling(max_distance_threshold: float = 5, max_time_interval: int = 20):

    print("Optimize Pooling API called.")

    optimized_pairs = []

    for i in range(len(json_customers)):
        for j in range(i+1, len(json_customers)):
            customer1 = json_customers[i]
            customer2 = json_customers[j]

            result = await process_pair(customer1, customer2, max_distance_threshold, max_time_interval)
            if result:
                optimized_pairs.append(result)

    if not optimized_pairs:
        print("No optimized pairs found within the given thresholds.")
        raise HTTPException(status_code=404, detail="No optimized pairs found within the given thresholds.")

    optimized_pairs.sort(key=lambda x: (x[0], x[2]))  # Sort pairs based on distance and customer name

    print("Optimization completed successfully.")
    return {"optimized_pairs": optimized_pairs}


async def process_pair(customer1, customer2, max_distance_threshold, max_time_interval):
    print(f"Processing pair: {customer1['name']} - {customer2['name']}")

    key = (customer1['pickup_location'], customer1['drop_location'], customer2['pickup_location'], customer2['drop_location'])
    if key in route_cache:
        route1, route2 = route_cache[key]
    else:
        print("Fetching routes from cache.")
        route1 = await plan_route(customer1['pickup_location'], customer1['drop_location'])
        route2 = await plan_route(customer2['pickup_location'], customer2['drop_location'])
        route_cache[key] = (route1, route2)

    if await check_route_overlap(route1, route2):
        distance = await calculate_distance(customer1['pickup_location'], customer2['pickup_location'])
        time_interval = abs(await get_time_difference(customer1['time'], customer2['time']))
        if distance <= max_distance_threshold and time_interval <= max_time_interval:
            optimized_pair = (customer1['name'], customer2['name'], distance, customer1['time'], customer2['time'])
            optimized_pairs_list.append(optimized_pair)
            print(f"Optimized pair found: {customer1['name']} - {customer2['name']}")
            return optimized_pair
    return None

async def plan_route(start_point, end_point):
    """
    Plan the route from start_point to end_point.
    """
    print(f"Planning route from {start_point} to {end_point}.")
    directions_result = gmaps.directions(start_point, end_point, mode="driving", departure_time=datetime.now())
    return directions_result

async def check_route_overlap(route1, route2):
    """
    Check if route1 passes through any point in route2.
    Extract start and end locations from each step in both routes
    """
    print("Checking route overlap.")

    route1_coordinates = get_route_coordinates(route1)
    route2_coordinates = get_route_coordinates(route2)

    for coord1 in route1_coordinates:
        for coord2 in route2_coordinates:
            if coord1 == coord2:
                return True

    return False

def get_route_coordinates(route):
    """
    Extract coordinates from each step in the route.
    """
    route_coordinates = set()

    for leg in route[0]['legs']:
        for step in leg['steps']:
            start_coord = (step['start_location']['lat'], step['start_location']['lng'])
            end_coord = (step['end_location']['lat'], step['end_location']['lng'])
            route_coordinates.add(start_coord)
            route_coordinates.add(end_coord)

    return route_coordinates

async def calculate_distance(coord1, coord2):
    """
    Calculate the distance between two coordinates using Google Maps Distance Matrix API.
    """
    print(f"Calculating distance between {coord1} and {coord2}.")
    result = gmaps.distance_matrix(coord1, coord2, mode='driving', units='metric')
    distance = result['rows'][0]['elements'][0]['distance']['value'] / 1000  # Convert meters to kilometers
    return distance

async def get_time_difference(time1, time2):
    '''
    Function to calculate the time difference in minutes between two time strings.
    '''
    print(f"Calculating time difference between {time1} and {time2}.")
    fmt = "%H:%M"
    t1 = datetime.strptime(time1, fmt)
    t2 = datetime.strptime(time2, fmt)
    delta = abs(t1 - t2)
    return delta.total_seconds() / 60

# max_distance_threshold = 5  # Maximum distance threshold in kilometers
# max_time_interval = 20  # Maximum time interval in minutes
#
# optimized_pairs = find_optimized_pooling(customers, max_distance_threshold, max_time_interval)
#
# print(
#     f"Optimized Pairs for Pooling (within {max_distance_threshold} km and at least {max_time_interval} minutes time interval):")
# for pair in optimized_pairs:
#     print(f"{pair[0]} and {pair[1]} - Distance: {pair[2]} km, Timings: {pair[3]} and {pair[4]}")

# customers = [
#     ("Jayanthi", "12.97829892, 77.62327584", "07:30"),
#     ("Michelle", "12.92513444, 77.67091976", "07:40"),
#     ("Divya", "12.88196291, 77.64302832", "08:30"),
#     ("Priyanjali", "12.88196569, 77.6430314", "08:30"),
#     ("Vishal", "12.92121593, 77.6186117", "08:30"),
#     ("Kirti", "12.96079998, 77.6558958", "08:30"),
#     ("Nishali", "12.95398853, 77.65082466", "08:45"),
#     ("Prasanthi", "12.90826656, 77.67914018", "08:45"),
#     ("Prerna", "12.90228451, 77.67002904", "08:50"),
#     ("Sulbha", "12.88428113, 77.66820498", "09:00"),
#     ("Aruna P", "12.90816163, 77.67840084", "09:20"),
#     ("Poornima Prabhu", "12.91402652, 77.61614057", "09:30"),
#     ("Srushti", "12.91276849, 77.62849367", "09:30"),
#     ("Alisha Hafiz", "12.91008094, 77.68153006", "11:00"),
#     ("Swati", "12.94597306, 77.67876846", "11:15"),
#     ("Lubna Malhotra", "12.89782214, 77.66785692", "11:45"),
#     ("Asha", "12.89055682, 77.66876893", "12:30"),
#     ("Ruella D", "12.97174329, 77.628696", "12:45"),
#     ("Juanita Marietta Luiz", "12.99128269, 77.6623218", "13:00"),
#     ("Sindhu", "12.97185443, 77.62859282", "14:30"),
# ]

# # Initialize Google Maps client with API key
# api_key = 'AIzaSyCNrNiAIsXKD84dZbamrDLCofJ_NNMoLNM'  # Replace 'YOUR_API_KEY' with your actual API key
# gmaps = googlemaps.Client(key=api_key)
#
#
# drop_prasanthi = "12.93188306, 77.61444762"
# drop_sulbha = "12.95975897, 77.64198"
#
#
# route_prasanthi_to_sulbha = gmaps.directions(drop_prasanthi, drop_sulbha, mode="driving")
# route_sulbha_to_prasanthi = gmaps.directions(drop_sulbha, drop_prasanthi, mode="driving")
#
# # Check if the routes overlap
# if route_prasanthi_to_sulbha and route_sulbha_to_prasanthi:
#     print("The drop points of Prasanthi and Sulbha lie on the same route.")
# else:
#     print("The drop points of Prasanthi and Sulbha do not lie on the same route.")
#


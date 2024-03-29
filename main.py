from typing import List
import csv,json
from fastapi import File, UploadFile
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi import FastAPI, HTTPException, Depends, Query
import googlemaps
from itertools import combinations
import math
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



# Initialize Google Maps client with API key
# api_key = 'AIzaSyCNrNiAIsXKD84dZbamrDLCofJ_NNMoLNM'  # Replace 'YOUR_API_KEY' with your actual API key
# gmaps = googlemaps.Client(key=api_key)
#
# route_cache = {}
#
# optimized_pairs_list = []
#
# def read_customer_data_from_csv(csv_data):
#     customers = []
#     reader = csv.DictReader(csv_data.decode("utf-8").splitlines())
#     for row in reader:
#         customers.append({
#             'name': row.get('customer_name'),
#             'pickup_location': f"{row.get('customer_lat_pickup')}, {row.get('customer_lon_pickup')}",
#             'drop_location': f"{row.get('customer_lat_drop')}, {row.get('customer_lon_drop')}",
#             'time': remove_seconds_from_time(row.get('ride_date_time'))
#         })
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
# @app.post("/optimize-pooling/")
# async def optimize_pooling(max_distance_threshold: float = 5, max_time_interval: int = 20, file: UploadFile = File(...)):
#
#     print("Optimize Pooling API called.")
#
#     optimized_pairs = []
#     customer_count = 0  # Counter for the number of customers processed
#
#     customers = read_customer_data_from_csv(await file.read())
#
#     i = 0
#     j = 1
#
#     while i < len(customers) - 1:
#         customer1 = customers[i]
#         customer2 = customers[j]
#
#         customer_count += 1  # Increment the counter for each pair of customers
#
#         print(f"Processing pair: {customer1['name']} - {customer2['name']}")  # Print the pair of customer names
#
#         if await check_same_route(customer1, customer2, max_distance_threshold):
#             result = await process_pair(customer1, customer2, max_distance_threshold, max_time_interval)
#             if result:
#                 optimized_pairs.append(result)
#                 print(optimized_pairs)
#
#         j += 1
#         if j == len(customers):
#             i += 1
#             j = i + 1
#
#     if not optimized_pairs:
#         print("No optimized pairs found within the given thresholds.")
#         raise HTTPException(status_code=404, detail="No optimized pairs found within the given thresholds.")
#
#     optimized_pairs.sort(key=lambda x: (x[0], x[2]))  # Sort pairs based on distance and customer name
#
#     print("Optimization completed successfully.")
#     print(f"Number of customers processed: {customer_count}")  # Print the number of customers processed
#     return {"optimized_pairs": optimized_pairs}
#
#
# async def process_pair(customer1, customer2, max_distance_threshold, max_time_interval):
#     print(f"Processing pair: {customer1['name']} - {customer2['name']}")
#
#     key = (customer1['pickup_location'], customer1['drop_location'], customer2['pickup_location'], customer2['drop_location'])
#     if key in route_cache:
#         route1, route2 = route_cache[key]
#     else:
#         print("Fetching routes from cache.")
#         route1 = await plan_route(customer1['pickup_location'], customer1['drop_location'])
#         route2 = await plan_route(customer2['pickup_location'], customer2['drop_location'])
#         route_cache[key] = (route1, route2)
#
#     if await check_route_overlap(route1, route2):
#         distance = await calculate_distance(customer1['pickup_location'], customer2['pickup_location'])
#         time_interval = abs(await get_time_difference(customer1['time'], customer2['time']))
#         if distance <= max_distance_threshold and time_interval <= max_time_interval:
#             optimized_pair = (customer1['name'], customer2['name'], distance, customer1['time'], customer2['time'])
#             optimized_pairs_list.append(optimized_pair)  # Append to optimized_pairs_list
#             print(f"Optimized pair found: {customer1['name']} - {customer2['name']}")
#             return optimized_pair
#     return None
#
# async def plan_route(start_point, end_point):
#     """
#     Plan the route from start_point to end_point.
#     """
#     print(f"Planning route from {start_point} to {end_point}.")
#     directions_result = gmaps.directions(start_point, end_point, mode="driving", departure_time=datetime.now())
#     return directions_result
#
# async def check_route_overlap(route1, route2):
#     """
#     Check if route1 passes through any point in route2.
#     Extract start and end locations from each step in both routes
#     """
#     print("Checking route overlap.")
#
#     route1_coordinates = get_route_coordinates(route1)
#     route2_coordinates = get_route_coordinates(route2)
#
#     for coord1 in route1_coordinates:
#         for coord2 in route2_coordinates:
#             if coord1 == coord2:
#                 return True
#
#     return False
#
# async def check_same_route(customer1, customer2, max_distance_threshold):
#     """
#     Check if both customers have pickup and drop points on the same route
#     and if the distance between their pickup points is less than the threshold.
#     """
#     pickup_distance = await calculate_distance(customer1['pickup_location'], customer2['pickup_location'])
#     if pickup_distance <= max_distance_threshold:
#         route1 = await plan_route(customer1['pickup_location'], customer1['drop_location'])
#         route2 = await plan_route(customer2['pickup_location'], customer2['drop_location'])
#         return await check_route_overlap(route1, route2)
#     return False
#
# def get_route_coordinates(route):
#     """
#     Extract coordinates from each step in the route.
#     """
#     route_coordinates = set()
#
#     for leg in route[0]['legs']:
#         for step in leg['steps']:
#             start_coord = (step['start_location']['lat'], step['start_location']['lng'])
#             end_coord = (step['end_location']['lat'], step['end_location']['lng'])
#             route_coordinates.add(start_coord)
#             route_coordinates.add(end_coord)
#
#     return route_coordinates
#
# async def calculate_distance(coord1, coord2):
#     """
#     Calculate the distance between two coordinates using Google Maps Distance Matrix API.
#     """
#     print(f"Calculating distance between {coord1} and {coord2}.")
#     result = gmaps.distance_matrix(coord1, coord2, mode='driving', units='metric')
#     distance = result['rows'][0]['elements'][0]['distance']['value'] / 1000  # Convert meters to kilometers
#     return distance
#
# async def get_time_difference(time1, time2):
#     '''
#     Function to calculate the time difference in minutes between two time strings.
#     '''
#     print(f"Calculating time difference between {time1} and {time2}.")
#     fmt = "%H:%M"
#     t1 = datetime.strptime(time1, fmt)
#     t2 = datetime.strptime(time2, fmt)
#     delta = abs(t1 - t2)
#     return delta.total_seconds() / 60


# pairs = [('Ronald Dsouza', 'Asha', 2.961, '9:00', '9:00'), ('Ronald Dsouza', 'Anurag', 4.632, '9:00', '8:45'), ('Gune', 'Anithaa Nagaraja', 0.973, '9:50', '9:30'), ('Gune', 'Sooraj Tom', 4.99, '9:50', '10:00'), ('Asha', 'Shanika Patel', 2.252, '9:00', '9:00'), ('Divya', 'Priyanjali', 0.0, '8:30', '8:30'), ('Divya', 'Dhiraj', 2.407, '8:30', '8:23'), ('Divya', 'Palak', 3.987, '8:30', '8:40'), ('Priyanjali', 'Dhiraj', 2.407, '8:30', '8:23'), ('Priyanjali', 'Palak', 3.987, '8:30', '8:40'), ('Suno', 'Ram Kasuru', 0.171, '9:35', '9:45'), ('Suno', 'Indu', 3.078, '9:35', '9:20'), ('Suno', 'Samiksha Kapoor', 3.773, '9:35', '9:30'), ('Suno', 'Aniz', 4.016, '9:35', '9:30'), ('Suno', 'Shruti Waghmare', 4.337, '9:35', '9:30'), ('Sulbha', 'R Agarwal', 0.883, '9:00', '9:10'), ('Sulbha', 'Sahana', 2.788, '9:00', '9:00'), ('Rama', 'Anisha Patnaik', 0.331, '8:15', '8:15'), ('Simran', 'Lakshmi', 1.551, '9:30', '9:25'), ('Simran', 'Shiladitya Chatterjee', 2.518, '9:30', '9:30'), ('Simran', 'Samiksha Kapoor', 4.246, '9:30', '9:30'), ('Simran', 'Aniz', 4.085, '9:30', '9:30'), ('Simran', 'Shruti Waghmare', 4.406, '9:30', '9:30'), ('Anisha Patnaik', 'Ashika Drolia', 2.405, '8:15', '8:30'), ('Anisha Patnaik', 'Dhiraj', 4.888, '8:15', '8:23'), ('Anisha Patnaik', 'Asha', 4.777, '8:15', '8:30'), ('R Agarwal', 'Amar Kant Gupta', 3.654, '9:10', '9:30'), ('R Agarwal', 'Sahana', 2.021, '9:10', '9:00'), ('R Agarwal', 'Anjali', 1.892, '9:10', '9:30'), ('R Agarwal', 'Indu', 4.29, '9:10', '9:20'), ('R Agarwal', 'Monika', 3.898, '9:10', '9:30'), ('Shubham', 'Arundhati', 0.001, '10:00', '10:00'), ('Anurag', 'krissel Monteiro', 2.348, '8:45', '8:25'), ('Anurag', 'Jaswin Anand', 2.337, '8:45', '8:30'), ('Lakshmi', 'Shiladitya Chatterjee', 1.632, '9:25', '9:30'), ('Lakshmi', 'Samiksha Kapoor', 4.035, '9:25', '9:30'), ('Lakshmi', 'Aniz', 3.874, '9:25', '9:30'), ('Lakshmi', 'Shruti Waghmare', 4.195, '9:25', '9:30'), ('Prasanna Subramanian', 'Neha', 0.664, '10:23', '10:40'), ('Prasanna Subramanian', 'Arun', 2.89, '10:23', '10:30'), ('Anjali', 'Aayushi', 2.443, '9:30', '9:30'), ('Anjali', 'Prakshi', 4.075, '9:30', '9:45'), ('Anjali', 'Aruna P', 3.478, '9:30', '9:20'), ('Ashika Drolia', 'Dhiraj', 3.113, '8:30', '8:23'), ('Ashika Drolia', 'krissel Monteiro', 4.315, '8:30', '8:25'), ('Ashika Drolia', 'Sukalpa', 4.475, '8:30', '8:45'), ('krissel Monteiro', 'Asha', 4.61, '8:25', '8:30'), ('krissel Monteiro', 'Rushabh Hemani', 3.3, '8:25', '8:15'), ('Palak', 'Subin', 2.395, '8:40', '8:46'), ('Palak', 'Shreya Gupta', 1.827, '8:40', '8:40'), ('Lubna Malhotra', 'Shubham Barbaile', 2.341, '11:45', '11:30'), ('Smriti', 'Smriti', 0.004, '10:15', '10:15'), ('Smriti', 'Prachi Gautam', 2.136, '10:15', '10:00'), ('Smriti', 'Prachi Gautam', 2.139, '10:15', '10:00'), ('Susmita', 'Divya', 2.165, '8:40', '8:25'), ('Indu', 'Samiksha Kapoor', 3.416, '9:20', '9:30'), ('Indu', 'Aniz', 1.875, '9:20', '9:30'), ('Indu', 'Shruti Waghmare', 1.453, '9:20', '9:30'), ('Shiladitya Chatterjee', 'Samiksha Kapoor', 2.715, '9:30', '9:30'), ('Samiksha Kapoor', 'Aniz', 1.899, '9:30', '9:30'), ('Samiksha Kapoor', 'Shruti Waghmare', 2.22, '9:30', '9:30'), ('Abhinav', 'Smita Swain', 1.415, '8:02', '7:45'), ('Pranita', 'Rushabh Hemani', 4.032, '8:00', '8:15'), ('Prerna', 'Sukalpa', 0.08, '8:50', '8:45'), ('Prerna', 'Prasanthi', 3.517, '8:50', '8:45'), ('Prerna', 'Subhashree', 3.548, '8:50', '8:45'), ('Prerna', 'Amit Singh', 2.347, '8:50', '8:40'), ('Sukalpa', 'Prasanthi', 3.564, '8:45', '8:45'), ('Sukalpa', 'Subhashree', 3.595, '8:45', '8:45'), ('Sukalpa', 'Amit Singh', 2.394, '8:45', '8:40'), ('Prasanth', 'Prakshi', 3.899, '9:51', '9:45'), ('Aayushi', 'Prakshi', 2.731, '9:30', '9:45'), ('Aayushi', 'Arshdeep', 0.776, '9:30', '9:30'), ('Aayushi', 'Aruna P', 2.288, '9:30', '9:20'), ('Abhipsa', 'Nishant', 0.352, '10:30', '10:30'), ('Ramya', 'Jill', 1.204, '9:30', '9:10'), ('Mona Lisa', 'Aruna P', 2.734, '9:00', '9:20'), ('Mona Lisa', 'Prasanthi', 2.689, '9:00', '8:45'), ('Mona Lisa', 'Subhashree', 2.721, '9:00', '8:45'), ('Mona Lisa', 'Amit Singh', 3.237, '9:00', '8:40'), ('Subin', 'Asha', 1.452, '8:46', '8:30'), ('Aniz', 'Shruti Waghmare', 0.578, '9:30', '9:30'), ('Apurba Saha', 'Kumari Trishya', 4.212, '11:45', '11:30'), ('Divya', 'Shreya Gupta', 1.333, '8:25', '8:40'), ('Asha', 'Rushabh Hemani', 1.411, '8:30', '8:15'), ('Asha', 'Shreya Gupta', 0.421, '8:30', '8:40'), ('Prasanthi', 'Subhashree', 0.042, '8:45', '8:45'), ('Prasanthi', 'Amit Singh', 1.954, '8:45', '8:40'), ('Subhashree', 'Amit Singh', 1.996, '8:45', '8:40')]
# formatted_pairs = '\n'.join([f"{pair[0]} - {pair[1]}: Distance = {pair[2]} km, Time1 = {pair[3]}, Time2 = {pair[4]}" for pair in pairs])
#
# print(formatted_pairs)


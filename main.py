from fastapi import FastAPI, Depends
from fastapi.params import Body
import psycopg2
from psycopg2.extras import RealDictCursor
import time
from .geolocation import get_address_pincode_from_laton
from .schema import Pincode,Check_Serv,ZipCode
from . import models
from .database import engine, get_db
from sqlalchemy.orm import Session

models.Base.metadata.create_all(bind=engine)

app = FastAPI() 

while True:
    try:
        conn = psycopg2.connect(host = 'localhost', database = 'MyPickup_db', user = 'postgres', password='Sandyis100%sexy',
                                cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        print("Database connection was successfull")
        break
    except Exception as error:
        print("Connection ti database failed")
        print("Error : ", error)
        time.sleep(3)

@app.get("/mypickup/")
def read_root():
    return {"Hello": "World"}

@app.post("/mypickup/geolocation")
def get_geoloc(locat: Pincode):
    address, zipcode = get_address_pincode_from_laton(locat.lat, locat.lon)
    return {zipcode}

@app.post("/mypickup/ingest-geolocation-pincode")
def ingest_geoloc_using_pincode(Serv: Check_Serv, db:Session = Depends(get_db)):
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
    
    


@app.post("/mypickup/ingest-geolocation-latlon")
def ingest_geoloc_using_latlon(Serv: Pincode, db: Session = Depends(get_db)):
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
    
@app.get("/mypickup/check-pincode")
def checkpincode(zipcode: ZipCode, db: Session = Depends(get_db)):
    zip_code_value = zipcode.zip_code 

    zips = db.query(models.Serviceable_area).filter(models.Serviceable_area.zip_code == zip_code_value)

    if not zips.first():
        return {0}
    else:
        serv = zips.first().is_serviceable
        return {f"The pin code {zip_code_value} is available, and the serviceability condition is {serv}"}
    
@app.put('/mypickup/update-serviceability')
def update_Servi(zipcode : Check_Serv, db:Session = Depends(get_db)):
    zip_code_value = zipcode.zip_code 
    new_Serviceabilty = zipcode.servicability
    serviceable_area = db.query(models.Serviceable_area).filter(models.Serviceable_area.zip_code == zip_code_value).first()

    if serviceable_area:
        # Update the serviceability
        serviceable_area.is_serviceable = new_Serviceabilty
        db.commit()
        return {"message": f"Serviceability for pin code {zip_code_value} updated successfully."}
    else:
        return {"message" : f"pincode {zip_code_value} not found"}



    
    


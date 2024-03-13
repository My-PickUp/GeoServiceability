from pydantic import BaseModel
from datetime import datetime


class Pincode(BaseModel):
    lat : float
    lon : float
    is_serviceable: bool
    
class ZipCode(BaseModel):
    zip_code: int
    
class Check_Serv(BaseModel):
    zip_code: int
    is_serviceable: bool  
    city_id: int
    
class Serv_area(BaseModel):
    Area_id  : int
    Area_name : str
    is_serviceable : bool  

class Ingest_cities(BaseModel):
    city_name : str
    user_email : str 
    serviceability : bool
    
class Update_cities(BaseModel):
    city_id : int
    user_email : str 
    serviceability : bool

class LeadCustomers(BaseModel):
    id: int
    name: str
    phone: str
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float
    pickup_cell_id: str
    drop_cell_id: str

    class Config:
        orm_mode = True

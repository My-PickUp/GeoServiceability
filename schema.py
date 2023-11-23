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
    
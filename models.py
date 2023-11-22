from .database import Base
from sqlalchemy import Column, Integer, String, Boolean, Float
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text

class Customer_inventory(Base):
    __tablename__ = 'customer_inventory'
    
    Customer_id = Column(Integer, primary_key=True, nullable=False)
    
class Serviceable_area(Base):
    __tablename__ = "Serviceable_area"
    
    city_id = Column(Integer, nullable=False)
    zip_code = Column(Integer, nullable=False,unique=True)
    area_name = Column(String, nullable=False)
    is_serviceable = Column(Boolean, nullable= False, server_default='false')
    Geo_uuid = Column(Integer, primary_key=True, unique=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)   
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    
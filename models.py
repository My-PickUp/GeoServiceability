from database import Base
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text

class Customer_inventory(Base):
    __tablename__ = 'customer_inventory'
    
    Customer_id = Column(Integer, primary_key=True, nullable=False)
    
class Serviceable_area(Base):
    __tablename__ = "Serviceable_area"
    
    city_id = Column(Integer, nullable=False)
    zip_code = Column(Integer, nullable=False,unique=True)
    is_serviceable = Column(Boolean, nullable= False, server_default='false')
    Geo_uuid = Column(Integer, primary_key=True, unique=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)   
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    
    
class Cities(Base):
    
    __tablename__ = "cities"
    
    id = Column(Integer, primary_key=True, unique=True)
    city = Column(String, unique=True, nullable=False)
    serviceability = Column(Boolean, nullable=False)

    
class User_cities(Base):
    __tablename__ = "user_changes_for_cities"
    
    id = Column(Integer,primary_key=True,unique=True, nullable=False)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    user_email = Column(String, nullable=False)
    done_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))



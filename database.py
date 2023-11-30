from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


DATABASE_URL = 'postgresql://telkestech%40gmail.com:ShXixZT5YV6u@ep-red-bird-68334114.ap-southeast-1.aws.neon.tech/GeoServiceability?sslmode=require'

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

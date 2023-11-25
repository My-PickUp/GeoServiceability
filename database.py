from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import settings

SQLALCHEMY_DATABASE_URL = 'postgresql://chityanjs:Nfqyolj4Swz1@ep-plain-wildflower-79539467.ap-southeast-1.aws.neon.tech/tess?sslmode=require'

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit = False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()

import urllib.parse
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

SERVER = "localhost"
DATABASE = "gameDB"
DRIVER = "ODBC Driver 17 for SQL Server"

params = urllib.parse.quote_plus(
    f"DRIVER={{{DRIVER}}};"
    f"DATABASE={DATABASE};"
    f"SERVER={SERVER};"
    f"Trusted_Connection=yes;"
    f"TrustServerCertificate=yes;"
)

DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Location(Base):
    __tablename__ = "locations"
    location_id = Column(Integer, primary_key=True, index=True)
    location_name = Column(String(50), default="Таверна")

class Character(Base):
    __tablename__ = "characters"
    character_id = Column(Integer, primary_key=True, index=True)
    character_name = Column(String(50), unique=True, index=True)
    character_health = Column(Integer, default=100)
    character_level = Column(Integer, default=1)

    inventory_items = relationship("Inventory", back_populates="character")

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.character_id"))
    username = Column(String(50), unique=True, index=True)
    userpassword = Column(String(50))
    location_id = Column(Integer, ForeignKey("locations.location_id"))
    create_at = Column(DateTime, default=datetime.utcnow)

    character = relationship("Character")
    location = relationship("Location")

class Item(Base):
    __tablename__ = "items"
    item_id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(50))
    item_quantity = Column(Integer)
    max_stack = Column(Integer, default=10)

class Inventory(Base):
    __tablename__ = "inventory"
    inventory_id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.item_id"))
    character_id = Column(Integer, ForeignKey("characters.character_id"))
    quantity = Column(Integer)
    slot_index = Column(Integer)

    character = relationship("Character", back_populates="inventory_items")
    item = relationship("Item")

class UserSession(Base):
    __tablename__ = "usersessions"
    session_token = Column(String(100), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id")) 
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    user = relationship("User")

def init_db():
    Base.metadata.create_all(bind=engine)

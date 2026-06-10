from sqlalchemy import create_engine

# Configure your database URL here or load from environment variables
DATABASE_URL = "postgresql+psycopg://user:pass@localhost/mydb"

def get_engine():
    return create_engine(DATABASE_URL)

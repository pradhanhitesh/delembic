[delembic]
script_location = ${script_location}
# sqlalchemy.url = postgresql+psycopg://user:pass@localhost/mydb
# If not set, Delembic will call get_engine() from ${script_location}/env.py
alembic_config = alembic.ini
filename_template = %(year)s_%(month)s_%(day)s_%(hour)s%(minute)s%(second)s_%(revision)s_%(slug)s

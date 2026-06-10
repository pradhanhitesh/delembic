from delembic import DataMigration

class ${class_name}(DataMigration):
    revision = "${revision}"
    depends_on = ${depends_on}
    description = "${description}"

    def upgrade(self, conn):
        # conn is a SQLAlchemy Connection.
        #
        # For standard SQL:
        #   from sqlalchemy import text
        #   conn.execute(text("INSERT INTO my_table SELECT * FROM staging.my_table"))
        #
        # For bulk COPY (psycopg3):
        #   raw = conn.connection.driver_connection
        #   with raw.cursor() as cur:
        #       with cur.copy("COPY my_table FROM STDIN WITH (FORMAT csv)") as copy:
        #           copy.write(data)
        #   raw.commit()
        pass

    def validate(self, conn):
        pass

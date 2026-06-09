# Writing Migrations

## Migration Class

Every migration is a Python class that inherits from `DataMigration`:

```python
from delembic import DataMigration
from sqlalchemy import text


class LoadVocabulary(DataMigration):

    revision = "D001"
    depends_on = []
    description = "Load OMOP vocabulary tables"

    def upgrade(self, conn):
        conn.execute(text("INSERT INTO concept SELECT * FROM concept_staging"))

    def validate(self, conn):
        count = conn.execute(text("SELECT COUNT(*) FROM concept")).scalar()
        assert count > 0, "vocabulary load produced no rows"
```

## Class Attributes

`revision`
: **Required.** Unique string identifier for this migration. Convention is `D001`, `D002`, … but any string works. Must be unique across all migrations.

`depends_on`
: List of revision IDs that must be applied before this one runs. Can mix Delembic revisions (`D001`) and Alembic revisions (`3d1e3e6abc12`). **Default:** `[]`

`description`
: Human-readable description. Shown in `delembic history` output.

## Methods

### `upgrade(self, conn)`

**Required.** Receives an open SQLAlchemy `Connection`. Do your data work here.

```python
def upgrade(self, conn):
    conn.execute(
        text("""
            INSERT INTO person (person_id, birth_year)
            SELECT source_id, year_of_birth FROM staging.person
        """)
    )
```

The connection is managed by Delembic:
- Auto-committed on success
- Rolled back on any exception (including `validate` failure)

### `validate(self, conn)`

**Optional.** Runs after `upgrade()` on the same connection (before commit). If it raises, the migration is marked failed and the work is rolled back.

```python
def validate(self, conn):
    count = conn.execute(text("SELECT COUNT(*) FROM person")).scalar()
    if count == 0:
        raise ValueError("person table is empty after migration")
```

Use `validate` for post-condition checks that should block the commit.

## File Naming

Generated files follow the pattern `{REVISION}_{slug}.py`. The class name is derived from the message slug.

```bash
delembic revision -m "load person demographics"
# → D002_load_person_demographics.py  (class: LoadPersonDemographics)
```

You can rename files freely — Delembic identifies migrations by the `revision` attribute, not the filename.

## Using SQLAlchemy

`conn` is a `sqlalchemy.engine.Connection`. Use `text()` for raw SQL or SA Core constructs:

```python
from sqlalchemy import text, table, column, insert

# Raw SQL
conn.execute(text("UPDATE concept SET valid = true WHERE domain_id = 'Drug'"))

# SA Core
concept = table("concept", column("concept_id"), column("concept_name"))
conn.execute(insert(concept).values(concept_id=1, concept_name="Aspirin"))
```

## Retry Behavior

If a migration fails, `delembic_version` records `status = failed`. On next `delembic upgrade head`:
- Delembic treats it as pending and re-runs
- Old failure record is replaced with the new outcome

This means migrations are idempotent at the framework level — your `upgrade()` logic should also be idempotent (use `INSERT ... ON CONFLICT DO NOTHING`, truncate-then-insert, etc.).

## Example: Bulk Load from Staging

```python
from delembic import DataMigration
from sqlalchemy import text


class LoadDrugExposure(DataMigration):

    revision = "D003"
    depends_on = ["D001", "D002"]
    description = "Load drug_exposure from staging"

    def upgrade(self, conn):
        conn.execute(text("TRUNCATE drug_exposure"))
        conn.execute(text("""
            INSERT INTO drug_exposure
            SELECT
                de.drug_exposure_id,
                de.person_id,
                c.concept_id AS drug_concept_id,
                de.drug_exposure_start_date
            FROM staging.drug_exposure de
            JOIN concept c ON c.concept_code = de.ndc_code
        """))

    def validate(self, conn):
        orphans = conn.execute(text("""
            SELECT COUNT(*) FROM drug_exposure de
            LEFT JOIN person p ON p.person_id = de.person_id
            WHERE p.person_id IS NULL
        """)).scalar()
        assert orphans == 0, f"{orphans} drug_exposure rows have no matching person"
```

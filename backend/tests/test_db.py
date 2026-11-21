from alembic import command
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from revalo.db.migrate import alembic_config, upgrade
from revalo.db.models import Job, Piece, PieceKind, Workshop, new_piece_code
from revalo.db.session import make_engine


def db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_migrations_create_every_table(tmp_path):
    url = db_url(tmp_path)
    upgrade(url)
    tables = set(inspect(make_engine(url)).get_table_names())
    assert {"workshops", "jobs", "pieces", "piece_events", "alembic_version"} <= tables


def test_models_and_migrations_agree(tmp_path):
    url = db_url(tmp_path)
    upgrade(url)
    # Raises if the models changed without a matching migration.
    command.check(alembic_config(url))


def test_piece_codes_are_readable():
    code = new_piece_code()
    assert code.startswith("RV-") and len(code) == 9
    assert not set(code[3:]) & set("ILOU")


def test_round_trip(tmp_path):
    url = db_url(tmp_path)
    upgrade(url)
    with Session(make_engine(url)) as session:
        shop = Workshop(name="Atelier pilote")
        session.add(shop)
        session.flush()  # ids are assigned on flush
        job = Job(
            workshop_id=shop.id,
            file_name="nest.dxf",
            file_format="dxf",
            file_sha256="0" * 64,
            file_key="ab/nest.dxf",
            kerf_mm=0.2,
            sheet_count=1,
            part_count=3,
            analysis={"sheets": []},
        )
        job.pieces.append(
            Piece(
                workshop_id=shop.id,
                position=0,
                kind=PieceKind.REMNANT,
                sheet_index=0,
                label="S1-R1",
                area_m2=0.5,
                weight_est_kg=11.8,
            )
        )
        session.add(job)
        session.commit()
        piece = session.query(Piece).one()
        assert piece.code.startswith("RV-")
        assert piece.weight_kg == 11.8
        piece.weight_actual_kg = 11.2
        assert piece.weight_kg == 11.2


def test_migrations_upgrade_a_database_that_already_has_data(tmp_path):
    """Table rebuilds on SQLite must not trip over existing foreign keys."""
    url = db_url(tmp_path)
    command.upgrade(alembic_config(url), "0003")
    engine = make_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO workshops (id, name, created_at) VALUES ('w1', 'Atelier', '2026-11-01')"
        )
        conn.exec_driver_sql(
            "INSERT INTO jobs (id, workshop_id, file_name, file_format, file_sha256, file_key,"
            " kerf_mm, sheet_count, part_count, status, analysis, created_at)"
            " VALUES ('j1', 'w1', 'a.dxf', 'dxf', 'x', 'k', 0.2, 1, 1, 'draft', '{}', '2026-11-01')"
        )
        conn.exec_driver_sql(
            "INSERT INTO pieces (id, code, job_id, workshop_id, position, kind, status,"
            " sheet_index, label, area_m2, created_at, updated_at)"
            " VALUES ('p1', 'RV-AAAAAA', 'j1', 'w1', 0, 'remnant', 'draft', 0, 'S1-R1', 0.5,"
            " '2026-11-01', '2026-11-01')"
        )
    engine.dispose()
    upgrade(url)
    with make_engine(url).connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM pieces").scalar() == 1
        assert conn.exec_driver_sql("SELECT machine_id FROM jobs").scalar() is None


def test_a_failed_migration_leaves_nothing_half_applied(tmp_path):
    url = db_url(tmp_path)
    command.upgrade(alembic_config(url), "0003")
    engine = make_engine(url)
    with engine.begin() as conn:
        # Batch mode rebuilds `jobs` through this temporary table: taking the name
        # makes migration 0004 fail after it has already created `machines`.
        conn.exec_driver_sql("CREATE TABLE _alembic_tmp_jobs (x INTEGER)")
    engine.dispose()
    try:
        upgrade(url)
    except Exception:
        pass
    else:
        raise AssertionError("the migration should have failed")
    tables = set(inspect(make_engine(url)).get_table_names())
    assert "machines" not in tables

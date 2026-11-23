"""A demo workshop with a month of believable activity, for pitches and trials.

It runs only on an empty database (no accounts yet), so it can never mix demo
data into a real workshop. Everything goes through the same services the API
uses, so the demo shows exactly what the product does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from revalo.db.models import Job, Piece, PieceKind, PieceStatus, Role
from revalo.engine.fit import PartSize
from revalo.engine.materials import default_kerf
from revalo.engine.pipeline import AnalysisOptions
from revalo.services.auth import create_user, user_count
from revalo.services.fit import mark_reused
from revalo.services.jobs import create_job, default_workshop
from revalo.services.machines import MachineInput, apply_machine, save_machine
from revalo.services.market import RequestInput, create_request, list_piece, update_listing
from revalo.services.opportunities import save_planned
from revalo.services.pickups import request_pickup, update_pickup
from revalo.services.pieces import approve_job
from revalo.services.prices import price_book
from revalo.services.sourcing import OfferInput, create_offer
from revalo.storage import FileStorage

DEMO_DOMAIN = "atelier-demo.test"
PEOPLE = [
    ("Slim", "slim", Role.OWNER),
    ("Leila", "leila", Role.MANAGER),
    ("Sami", "sami", Role.OPERATOR),
]


class DemoError(Exception):
    pass


@dataclass
class DemoSummary:
    accounts: list[tuple[str, str, str]] = field(default_factory=list)
    jobs: int = 0
    in_stock: int = 0
    listings: int = 0
    buyers: int = 0
    offers: int = 0


def _remnants(job: Job) -> list[Piece]:
    pieces = [p for p in job.pieces if p.kind == PieceKind.REMNANT]
    return sorted(pieces, key=lambda p: -(p.weight_kg or 0))


def _scrap(job: Job) -> list[Piece]:
    return [p for p in job.pieces if p.kind == PieceKind.SCRAP]


def seed_demo(session: Session, storage: FileStorage, samples: Path, password: str) -> DemoSummary:
    if user_count(session) > 0:
        raise DemoError("This database already has accounts: the demo only seeds an empty one.")

    shop = default_workshop(session)
    shop.name = "Atelier Ben Arous (demo)"
    shop.governorate = "Ben Arous"
    session.commit()

    summary = DemoSummary()
    for name, handle, role in PEOPLE:
        email = f"{handle}@{DEMO_DOMAIN}"
        create_user(session, shop, email, name, role, password)
        summary.accounts.append((role.value, email, name))
    manager, operator = "Leila", "Sami"

    laser = save_machine(
        session,
        shop.id,
        MachineInput(
            name="Fibre laser 3 kW",
            process="fiber_laser",
            material_code="steel_mild",
            thickness_mm=3,
            sheet_width_mm=3000,
            sheet_height_mm=1500,
        ),
    )
    save_machine(session, shop.id, MachineInput(name="Plasma table", process="plasma"))
    router = save_machine(
        session,
        shop.id,
        MachineInput(
            name="CNC router",
            process="router",
            material_code="mdf",
            thickness_mm=18,
            sheet_width_mm=2440,
            sheet_height_mm=1220,
        ),
    )

    def upload(file: str, machine=None) -> Job:
        path = samples / file
        if not path.is_file():
            raise DemoError(f"Sample file missing: {path}")
        options = AnalysisOptions()
        if machine is not None:
            options = apply_machine(options, machine)
        return create_job(
            session, storage, path.read_bytes(), path.name, options, operator, machine
        )

    steel = upload("synthetic/laser_S235_3mm_3000x1500.dxf", laser)
    inox = upload("synthetic/inox_304_1.5mm_2500x1250.dxf")
    mdf = upload("synthetic/router_MDF_18mm_2440x1220.nc", router)
    upload("synthetic/plasma_S355_10mm_2000x1000.nc")  # left for review: shows an alert
    for job in (steel, inox, mdf):
        approve_job(session, job, manager)
    summary.jobs = 4

    # Buyers: two who reuse offcuts, one recycler who buys steel by weight.
    create_request(
        session,
        RequestInput(
            kind="reuse",
            name="Karim",
            organization="Menuiserie Karim",
            phone="+216 20 123 456",
            governorate="Tunis",
            materials=("mdf", "plywood"),
            min_length_mm=300,
            min_width_mm=200,
        ),
    )
    hela = create_request(
        session,
        RequestInput(
            kind="reuse",
            name="Hela",
            organization="Métallerie Hela",
            phone="+216 22 654 321",
            governorate="Ben Arous",
            materials=("steel_mild", "stainless_304"),
            thickness_min_mm=1,
            thickness_max_mm=4,
        ),
    )
    recycler = create_request(
        session,
        RequestInput(
            kind="recycler",
            name="Récupération Ben Arous",
            phone="+216 71 000 111",
            governorate="Ben Arous",
            materials=("steel_mild", "stainless_304", "aluminium"),
            offered_tnd_per_kg=0.3,
            min_lot_kg=5,
            pickup_note="Tuesdays and Fridays, light truck",
        ),
    )
    summary.buyers = 3

    book = price_book(session, shop.id)
    steel_remnants = _remnants(steel)
    # Two remnants already went into a new order; one sold to Hela; one on sale.
    mark_reused(session, [p.id for p in steel_remnants[:2]], "Order 2026-131", operator)
    sold = list_piece(session, steel_remnants[2], book, None, manager)
    update_listing(session, sold, "sell", manager, buyer_request_id=hela.id)
    list_piece(session, steel_remnants[3], book, None, manager)
    mdf_remnants = _remnants(mdf)
    if mdf_remnants:
        list_piece(session, mdf_remnants[0], book, None, manager)
    summary.listings = 3

    # The steel skeleton was collected and paid; the stainless one waits for a date.
    collected = request_pickup(
        session, recycler.id, [p.id for p in _scrap(steel)], manager, shop.id
    )
    update_pickup(session, collected, "schedule", manager, scheduled_for=datetime.now(UTC).date())
    weighed = round(collected.estimated_kg * 0.97, 1)
    update_pickup(session, collected, "collect", manager, weighed_kg=weighed)
    request_pickup(session, recycler.id, [p.id for p in _scrap(inox)], manager, shop.id)

    # A coming job too big for the racks, and two workshops offering offcuts to us:
    # one would hold that job, the other is simply cheaper than new.
    save_planned(
        session,
        shop.id,
        "Gate panels, order 2026-142",
        "steel_mild",
        3,
        default_kerf(None, "steel_mild"),
        [PartSize(f"Panel {i + 1}", 900, 600) for i in range(2)],
        manager,
    )
    create_offer(
        session,
        OfferInput(
            seller_name="Nabil",
            organization="Atelier Nabil",
            phone="+216 55 111 222",
            governorate="Sousse",
            material_code="steel_mild",
            thickness_mm=3,
            width_mm=1000,
            height_mm=700,
            quantity=2,
            price_tnd=60,
            note="Clean edges, collect in Sousse or we deliver on Thursdays.",
        ),
    )
    create_offer(
        session,
        OfferInput(
            seller_name="Sonia",
            organization="Alu Pro Sfax",
            phone="+216 74 222 333",
            governorate="Sfax",
            material_code="aluminium",
            thickness_mm=2,
            width_mm=600,
            height_mm=400,
            quantity=4,
            price_tnd=45,
        ),
        source="workshop",
    )
    summary.offers = 2

    # Give a few pieces some age, so the review stages show in stock.
    steel.approved_at = datetime.now(UTC) - timedelta(days=35)
    session.commit()

    summary.in_stock = sum(
        1 for job in (steel, inox, mdf) for p in job.pieces if p.status == PieceStatus.IN_STOCK
    )
    return summary

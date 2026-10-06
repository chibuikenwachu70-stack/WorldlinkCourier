from app import app, db
from sqlalchemy import inspect, text


with app.app_context():

    print()
    print("======================================")
    print(" WORLDLINK RENDER DATABASE MIGRATION")
    print("======================================")
    print()

    inspector = inspect(db.engine)

    if not inspector.has_table("shipment"):
        print("ERROR: shipment table does not exist.")
        raise SystemExit(1)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("shipment")
    }

    # ----------------------------------
    # SERVICE TYPE
    # ----------------------------------

    if "service_type" not in existing_columns:

        print("Adding shipment.service_type...")

        db.session.execute(
            text(
                "ALTER TABLE shipment "
                "ADD COLUMN service_type "
                "VARCHAR(100) "
                "DEFAULT 'International Express'"
            )
        )

        db.session.commit()

        print("Added shipment.service_type")

    else:
        print("OK: shipment.service_type already exists")

    # ----------------------------------
    # PACKAGE DESCRIPTION
    # ----------------------------------

    if "package_description" not in existing_columns:

        print("Adding shipment.package_description...")

        db.session.execute(
            text(
                "ALTER TABLE shipment "
                "ADD COLUMN package_description "
                "VARCHAR(255) "
                "DEFAULT 'Parcel'"
            )
        )

        db.session.commit()

        print("Added shipment.package_description")

    else:
        print("OK: shipment.package_description already exists")

    # ----------------------------------
    # WEIGHT
    # ----------------------------------

    if "weight" not in existing_columns:

        print("Adding shipment.weight...")

        db.session.execute(
            text(
                "ALTER TABLE shipment "
                "ADD COLUMN weight "
                "DOUBLE PRECISION "
                "DEFAULT 0"
            )
        )

        db.session.commit()

        print("Added shipment.weight")

    else:
        print("OK: shipment.weight already exists")

    # ----------------------------------
    # ESTIMATED DELIVERY
    # ----------------------------------

    if "estimated_delivery" not in existing_columns:

        print("Adding shipment.estimated_delivery...")

        db.session.execute(
            text(
                "ALTER TABLE shipment "
                "ADD COLUMN estimated_delivery DATE"
            )
        )

        db.session.commit()

        print("Added shipment.estimated_delivery")

    else:
        print("OK: shipment.estimated_delivery already exists")

    # ----------------------------------
    # CREATED AT
    # ----------------------------------

    if "created_at" not in existing_columns:

        print("Adding shipment.created_at...")

        db.session.execute(
            text(
                "ALTER TABLE shipment "
                "ADD COLUMN created_at "
                "TIMESTAMP "
                "DEFAULT CURRENT_TIMESTAMP"
            )
        )

        db.session.commit()

        print("Added shipment.created_at")

    else:
        print("OK: shipment.created_at already exists")

    # ----------------------------------
    # VERIFY
    # ----------------------------------

    print()
    print("Checking final shipment schema...")

    inspector = inspect(db.engine)

    final_columns = {
        column["name"]
        for column in inspector.get_columns("shipment")
    }

    required_columns = [
        "service_type",
        "package_description",
        "weight",
        "estimated_delivery",
        "created_at",
    ]

    missing = [
        column
        for column in required_columns
        if column not in final_columns
    ]

    if missing:

        print()
        print("ERROR: Migration incomplete.")
        print("Missing:", ", ".join(missing))
        raise SystemExit(1)

    print()
    print("======================================")
    print(" MIGRATION COMPLETE")
    print("======================================")
    print()
    print("Existing shipments were preserved.")
    print("Existing WLC tracking numbers were preserved.")
    print("======================================")
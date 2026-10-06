from app import app, db
from sqlalchemy import text, inspect
from datetime import datetime


def column_exists(table_name, column_name):
    inspector = inspect(db.engine)

    columns = inspector.get_columns(table_name)

    return any(
        column["name"] == column_name
        for column in columns
    )


def add_column(table_name, column_name, definition):
    if column_exists(table_name, column_name):
        print(f"✓ {table_name}.{column_name} already exists")
        return

    print(f"Adding {table_name}.{column_name}...")

    db.session.execute(
        text(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {definition}"
        )
    )

    db.session.commit()

    print(f"✓ Added {table_name}.{column_name}")


with app.app_context():

    print()
    print("======================================")
    print(" WORLDLINK DATABASE UPGRADE")
    print("======================================")
    print()

    db.create_all()

    # ----------------------------------
    # NEW SHIPMENT COLUMNS
    # ----------------------------------

    add_column(
        "shipment",
        "service_type",
        "VARCHAR(100) DEFAULT 'Standard'"
    )

    add_column(
        "shipment",
        "package_description",
        "VARCHAR(255) DEFAULT 'Not provided'"
    )

    add_column(
        "shipment",
        "weight",
        "FLOAT DEFAULT 0"
    )

    add_column(
        "shipment",
        "estimated_delivery",
        "VARCHAR(100) DEFAULT 'To be confirmed'"
    )

    # SQLite does not allow:
    #
    # DEFAULT CURRENT_TIMESTAMP
    #
    # when adding a column with ALTER TABLE.
    #
    # Therefore we add the column first,
    # then populate existing records.

    if not column_exists("shipment", "created_at"):

        print("Adding shipment.created_at...")

        db.session.execute(
            text(
                "ALTER TABLE shipment "
                "ADD COLUMN created_at DATETIME"
            )
        )

        db.session.commit()

        print("✓ Added shipment.created_at")

        # Give existing shipments a creation timestamp.
        db.session.execute(
            text(
                "UPDATE shipment "
                "SET created_at = :created_at "
                "WHERE created_at IS NULL"
            ),
            {
                "created_at": datetime.utcnow()
            }
        )

        db.session.commit()

        print("✓ Existing shipments received created_at")

    else:

        print("✓ shipment.created_at already exists")

    # ----------------------------------
    # TRACKING EVENT NOTE
    # ----------------------------------

    if inspect(db.engine).has_table("tracking_event"):

        add_column(
            "tracking_event",
            "note",
            "VARCHAR(255) DEFAULT ''"
        )

    print()
    print("======================================")
    print(" DATABASE UPGRADE COMPLETE")
    print("======================================")
    print()
    print("Existing shipments were preserved.")
    print("Existing WLC tracking numbers were preserved.")
    print("Existing tracking history was preserved.")
    print()
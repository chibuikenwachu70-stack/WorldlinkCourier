import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "instance",
    "courier.db"
)

print("=" * 60)
print("WORLDLINK COURIER - CUSTOMS DATABASE UPGRADE")
print("=" * 60)

if not os.path.exists(DB_PATH):
    print(f"\nERROR: Database not found:")
    print(DB_PATH)
    raise SystemExit(1)

print(f"\nDatabase:")
print(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ---------------------------------------------------------
# Check existing columns
# ---------------------------------------------------------

cursor.execute("PRAGMA table_info(shipment)")
columns = {row[1] for row in cursor.fetchall()}

print("\nExisting shipment columns:")
for column in sorted(columns):
    print(f"  - {column}")

# ---------------------------------------------------------
# Add customs_reason
# ---------------------------------------------------------

if "customs_reason" not in columns:
    print("\nAdding customs_reason...")
    cursor.execute("""
        ALTER TABLE shipment
        ADD COLUMN customs_reason VARCHAR(255)
    """)
else:
    print("\ncustoms_reason already exists.")

# ---------------------------------------------------------
# Add customs_action_required
# ---------------------------------------------------------

if "customs_action_required" not in columns:
    print("Adding customs_action_required...")
    cursor.execute("""
        ALTER TABLE shipment
        ADD COLUMN customs_action_required VARCHAR(255)
    """)
else:
    print("customs_action_required already exists.")

# ---------------------------------------------------------
# Add customs_reference
# ---------------------------------------------------------

if "customs_reference" not in columns:
    print("Adding customs_reference...")
    cursor.execute("""
        ALTER TABLE shipment
        ADD COLUMN customs_reference VARCHAR(100)
    """)
else:
    print("customs_reference already exists.")

# ---------------------------------------------------------
# Commit
# ---------------------------------------------------------

conn.commit()

# ---------------------------------------------------------
# Verify
# ---------------------------------------------------------

cursor.execute("PRAGMA table_info(shipment)")
updated_columns = {row[1] for row in cursor.fetchall()}

print("\n" + "=" * 60)
print("UPGRADE COMPLETE")
print("=" * 60)

print("\nCustoms fields:")
print(
    "  customs_reason:",
    "OK" if "customs_reason" in updated_columns else "MISSING"
)

print(
    "  customs_action_required:",
    "OK" if "customs_action_required" in updated_columns else "MISSING"
)

print(
    "  customs_reference:",
    "OK" if "customs_reference" in updated_columns else "MISSING"
)

# ---------------------------------------------------------
# Shipment count
# ---------------------------------------------------------

cursor.execute("SELECT COUNT(*) FROM shipment")
shipment_count = cursor.fetchone()[0]

print(f"\nExisting shipments preserved: {shipment_count}")

conn.close()

print("\nYour existing shipment data has NOT been deleted.")
print("You can now update app.py.")
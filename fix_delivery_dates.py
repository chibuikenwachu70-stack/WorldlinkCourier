import sqlite3

DB_FILE = r"instance\courier.db"

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

print("Checking shipment delivery dates...")
print()

cursor.execute("""
    SELECT id, tracking_number, estimated_delivery
    FROM shipment
""")

rows = cursor.fetchall()

fixed = 0

for shipment_id, tracking_number, estimated_delivery in rows:

    if estimated_delivery == "To be confirmed":
        cursor.execute(
            """
            UPDATE shipment
            SET estimated_delivery = NULL
            WHERE id = ?
            """,
            (shipment_id,)
        )

        print(
            f"Fixed {tracking_number}: "
            f"'To be confirmed' -> NULL"
        )

        fixed += 1

conn.commit()
conn.close()

print()
print(f"Finished. Fixed {fixed} shipment(s).")
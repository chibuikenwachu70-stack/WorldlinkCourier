WORLDLINK COURIER SERVICE — COMPLETE STARTER

This package is a clean rebuild of the Worldlink Courier Flask application.

FEATURES
- Professional customer homepage
- Courier-photo placeholders
- Shipment tracking
- Tracking event timeline
- Shipment status and current location
- Services page
- Rates/transit foundation
- Support page
- Admin login
- Admin dashboard
- Search and status filtering
- Create shipment
- Edit/live tracking updates
- Delete parcel with confirmation
- Shipment receipt
- SQLite locally or PostgreSQL/Supabase via DATABASE_URL
- Cascade deletion of tracking history when a parcel is deleted
- JSON tracking API endpoint

IMPORTANT
1. Copy the entire project into your WorldlinkCourier folder, or use this as a clean upgraded version.
2. Add your own licensed courier images:
   static/images/courier-hero.jpg
   static/images/courier-logistics.jpg
   static/images/courier-express.jpg
   static/images/courier-international.jpg
   static/images/courier-business.jpg
3. Set environment variables before production:
   SECRET_KEY
   ADMIN_USERNAME
   ADMIN_PASSWORD
   DATABASE_URL
4. Do not keep real production credentials inside source code.
5. Existing SQLite data is NOT automatically merged by this package. Back up courier.db before replacing application files.

RUN LOCALLY
conda activate worldlink
pip install -r requirements.txt
python app.py

Then open:
http://127.0.0.1:5000

DEFAULT DEVELOPMENT ADMIN
Username: admin
Password: change-this-password

Change these before deployment.

DATABASE
The application uses DATABASE_URL when supplied and SQLite otherwise.
For Supabase/PostgreSQL, install psycopg[binary] and set DATABASE_URL.

NEXT DEVELOPMENT PHASE
- Preserve/migrate your existing shipment records
- Add real rate rules
- Add customer accounts
- Add pickup scheduling
- Add email/WhatsApp notifications
- Add map/location visualization
- Add stronger CSRF protection
- Add audit logs for admin actions

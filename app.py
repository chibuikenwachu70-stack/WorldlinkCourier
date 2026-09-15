import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random

app = Flask(__name__)

app.config["SECRET_KEY"] = "worldlink-admin-secret-key-change-later"
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///courier.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================
# ADMIN LOGIN INFORMATION
# =========================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = generate_password_hash("Mbappe7979")


# =========================
# SHIPMENT DATABASE MODEL
# =========================

class Shipment(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    tracking_number = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    sender = db.Column(
        db.String(100),
        nullable=False
    )

    sender_address = db.Column(
        db.String(200),
        nullable=False,
        default="Not provided"
    )

    receiver = db.Column(
        db.String(100),
        nullable=False
    )

    receiver_address = db.Column(
        db.String(200),
        nullable=False,
        default="Not provided"
    )

    receiver_phone = db.Column(
        db.String(50),
        nullable=False,
        default="Not provided"
    )

    origin = db.Column(
        db.String(100),
        nullable=False
    )

    destination = db.Column(
        db.String(100),
        nullable=False
    )

    current_location = db.Column(
        db.String(100),
        nullable=False,
        default="Not updated"
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="Shipment Received"
    )


# =========================
# TRACKING HISTORY MODEL
# =========================

class TrackingEvent(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    shipment_id = db.Column(
        db.Integer,
        db.ForeignKey("shipment.id"),
        nullable=False
    )

    status = db.Column(
        db.String(100),
        nullable=False
    )

    location = db.Column(
        db.String(100),
        nullable=False
    )

    event_time = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )


# =========================
# GENERATE TRACKING NUMBER
# =========================

def generate_tracking_number():
    while True:
        number = random.randint(100000000, 999999999)

        tracking_number = f"WLC{number}"

        existing = Shipment.query.filter_by(
            tracking_number=tracking_number
        ).first()

        if existing is None:
            return tracking_number


# =========================
# HOME PAGE
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# PUBLIC SHIPMENT TRACKING
# =========================

@app.route("/track", methods=["GET", "POST"])
def track():
    shipment = None
    message = None
    tracking_events = []

    if request.method == "POST":
        tracking_number = request.form.get(
            "tracking_number",
            ""
        ).strip()

        shipment = Shipment.query.filter_by(
            tracking_number=tracking_number
        ).first()

        if shipment is None:
            message = (
                "Tracking number not found. "
                "Please check the number and try again."
            )
        else:
            tracking_events = TrackingEvent.query.filter_by(
                shipment_id=shipment.id
            ).order_by(
                TrackingEvent.event_time.desc()
            ).all()

    return render_template(
        "tracking.html",
        shipment=shipment,
        message=message,
        tracking_events=tracking_events
    )


# =========================
# ADMIN LOGIN
# =========================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    message = None

    if request.method == "POST":
        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USERNAME
            and check_password_hash(
                ADMIN_PASSWORD_HASH,
                password
            )
        ):
            session["admin_logged_in"] = True

            return redirect(
                url_for("admin_dashboard")
            )

        message = "Invalid username or password."

    return render_template(
        "admin_login.html",
        message=message
    )


# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(
            url_for("admin_login")
        )

    shipments = Shipment.query.order_by(
        Shipment.id.desc()
    ).all()

    return render_template(
        "admin_dashboard.html",
        shipments=shipments
    )


# =========================
# CREATE NEW SHIPMENT
# =========================

@app.route(
    "/admin/create-shipment",
    methods=["GET", "POST"]
)
def create_shipment():
    if not session.get("admin_logged_in"):
        return redirect(
            url_for("admin_login")
        )

    message = None
    tracking_number = None

    if request.method == "POST":

        sender = request.form.get(
            "sender",
            ""
        ).strip()

        sender_address = request.form.get(
            "sender_address",
            ""
        ).strip()

        receiver = request.form.get(
            "receiver",
            ""
        ).strip()

        receiver_address = request.form.get(
            "receiver_address",
            ""
        ).strip()

        receiver_phone = request.form.get(
            "receiver_phone",
            ""
        ).strip()

        origin = request.form.get(
            "origin",
            ""
        ).strip()

        destination = request.form.get(
            "destination",
            ""
        ).strip()

        current_location = request.form.get(
            "current_location",
            origin
        ).strip()

        if not current_location:
            current_location = origin

        status = request.form.get(
            "status",
            "Shipment Received"
        ).strip()

        tracking_number = generate_tracking_number()

        shipment = Shipment(
            tracking_number=tracking_number,
            sender=sender,
            sender_address=sender_address,
            receiver=receiver,
            receiver_address=receiver_address,
            receiver_phone=receiver_phone,
            origin=origin,
            destination=destination,
            current_location=current_location,
            status=status
        )

        db.session.add(shipment)
        db.session.commit()

        # Create the first tracking history event
        first_event = TrackingEvent(
            shipment_id=shipment.id,
            status=status,
            location=current_location,
            event_time=datetime.utcnow()
        )

        db.session.add(first_event)
        db.session.commit()

        # Open the shipment receipt immediately
        return redirect(
            url_for(
                "shipment_receipt",
                shipment_id=shipment.id
            )
        )

    return render_template(
        "create_shipment.html",
        message=message,
        tracking_number=tracking_number
    )


# =========================
# EDIT / UPDATE SHIPMENT
# =========================

@app.route(
    "/admin/edit-shipment/<int:shipment_id>",
    methods=["GET", "POST"]
)
def edit_shipment(shipment_id):
    if not session.get("admin_logged_in"):
        return redirect(
            url_for("admin_login")
        )

    shipment = Shipment.query.get_or_404(
        shipment_id
    )

    if request.method == "POST":

        current_location = request.form.get(
            "current_location",
            ""
        ).strip()

        status = request.form.get(
            "status",
            ""
        ).strip()

        old_location = shipment.current_location
        old_status = shipment.status

        if current_location:
            shipment.current_location = current_location

        if status:
            shipment.status = status

        # Save shipment changes
        db.session.commit()

        # Add a tracking event only when something changed
        if (
            shipment.current_location != old_location
            or shipment.status != old_status
        ):
            new_event = TrackingEvent(
                shipment_id=shipment.id,
                status=shipment.status,
                location=shipment.current_location,
                event_time=datetime.utcnow()
            )

            db.session.add(new_event)
            db.session.commit()

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "edit_shipment.html",
        shipment=shipment
    )


# =========================
# SHIPMENT RECEIPT
# =========================

@app.route(
    "/admin/receipt/<int:shipment_id>"
)
def shipment_receipt(shipment_id):
    if not session.get("admin_logged_in"):
        return redirect(
            url_for("admin_login")
        )

    shipment = Shipment.query.get_or_404(
        shipment_id
    )

    return render_template(
        "receipt.html",
        shipment=shipment
    )


# =========================
# ADMIN LOGOUT
# =========================

@app.route("/admin/logout")
def admin_logout():
    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# =========================
# CREATE DATABASE TABLES
# =========================

with app.app_context():
    db.create_all()


# =========================
# START APPLICATION
# =========================

if __name__ == "__main__":
    app.run(debug=True)
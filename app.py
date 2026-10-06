import os
import random
import uuid
import re
from io import BytesIO
from decimal import Decimal, InvalidOperation
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
except ImportError:
    colors = None


app = Flask(__name__)


# =========================================================
# CONFIGURATION
# =========================================================

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-worldlink-secret-key",
)

database_url = os.getenv(
    "DATABASE_URL",
    "sqlite:///courier.db",
)

database_url = database_url.replace(
    "postgres://",
    "postgresql+psycopg://",
    1,
)

database_url = database_url.replace(
    "postgresql://",
    "postgresql+psycopg://",
    1,
)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


invoice_link_serializer = URLSafeTimedSerializer(
    app.config["SECRET_KEY"]
)


# =========================================================
# ADMIN CONFIGURATION
# =========================================================

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME",
    "admin",
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
)

if not ADMIN_PASSWORD:
    raise RuntimeError(
        "ADMIN_PASSWORD environment variable is not set."
    )

ADMIN_PASSWORD_HASH = generate_password_hash(
    ADMIN_PASSWORD
)

# =========================================================
# SHIPMENT STATUSES

STATUSES = [
    "Shipment Received",
    "Shipment Confirmed",
    "Pickup Scheduled",
    "Picked Up",

    "Processing",
    "Departed Origin Facility",
    "In Transit",

    "Arrived at Transit Hub",
    "At Sorting Facility",
    "Departed Sorting Facility",

    "Arrived at Destination Country",
    "Customs Clearance",
    "Customs Cleared",
    "Held by Customs",
    "Awaiting Documentation",
    "Awaiting Payment",
    "Released from Customs",

    "Arrived at Local Facility",
    "Out for Delivery",

    "Delivery Attempted",
    "Delivery Rescheduled",
    "Recipient Unavailable",
    "Address Issue",

    "Delivered",

    "Delivery Exception",
    "On Hold",
    "Returned to Sender",
    "Cancelled",
]


# =========================================================
# SHIPMENT STATUS ORDER
# =========================================================

STATUS_ORDER = {
    status: position
    for position, status in enumerate(STATUSES, start=1)
}

# =========================================================
# DATABASE MODELS
# =========================================================

class Shipment(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tracking_number = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    sender = db.Column(
        db.String(100),
        nullable=False,
    )

    sender_address = db.Column(
        db.String(200),
        nullable=False,
        default="Not provided",
    )

    receiver = db.Column(
        db.String(100),
        nullable=False,
    )

    receiver_address = db.Column(
        db.String(200),
        nullable=False,
        default="Not provided",
    )

    receiver_phone = db.Column(
        db.String(50),
        nullable=False,
        default="Not provided",
    )

    origin = db.Column(
        db.String(100),
        nullable=False,
    )

    destination = db.Column(
        db.String(100),
        nullable=False,
    )

    current_location = db.Column(
        db.String(100),
        nullable=False,
        default="Not updated",
    )

    status = db.Column(
        db.String(100),
        nullable=False,
        default="Shipment Received",
    )

    service_type = db.Column(
        db.String(100),
        nullable=False,
        default="International Express",
    )

    package_description = db.Column(
        db.String(255),
        nullable=False,
        default="Parcel",
    )

    weight = db.Column(
        db.Float,
        nullable=False,
        default=0.0,
    )

    estimated_delivery = db.Column(
        db.Date,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    events = db.relationship(
        "TrackingEvent",
        backref="shipment",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="TrackingEvent.event_time.desc()",
    )


class TrackingEvent(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    shipment_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "shipment.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.String(100),
        nullable=False,
    )

    location = db.Column(
        db.String(150),
        nullable=False,
    )

    note = db.Column(
        db.String(255),
        nullable=True,
    )

    event_time = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class ChatMessage(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    conversation_id = db.Column(
        db.String(80),
        nullable=False,
        index=True,
    )

    sender_type = db.Column(
        db.String(20),
        nullable=False,
    )

    customer_name = db.Column(
        db.String(120),
        nullable=False,
        default="Website Visitor",
    )

    customer_email = db.Column(
        db.String(255),
        nullable=False,
        default="",
    )

    tracking_number = db.Column(
        db.String(50),
        nullable=True,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    is_read = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
    )

    # True when the customer has explicitly asked for a human support representative.
    human_requested = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )


class ChatTypingStatus(db.Model):

    __tablename__ = "chat_typing_status"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    conversation_id = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_typing_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    admin_typing_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class Invoice(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)

    shipment_id = db.Column(
        db.Integer,
        db.ForeignKey("shipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_type = db.Column(db.String(40), nullable=False, default="Courier Invoice")
    customs_country = db.Column(db.String(100), nullable=True)
    currency = db.Column(db.String(10), nullable=False, default="USD")

    shipping_amount = db.Column(db.Float, nullable=False, default=0.0)
    customs_amount = db.Column(db.Float, nullable=False, default=0.0)
    handling_amount = db.Column(db.Float, nullable=False, default=0.0)
    other_amount = db.Column(db.Float, nullable=False, default=0.0)
    tax_amount = db.Column(db.Float, nullable=False, default=0.0)
    discount_amount = db.Column(db.Float, nullable=False, default=0.0)

    payment_status = db.Column(db.String(30), nullable=False, default="Pending")
    notes = db.Column(db.Text, nullable=True)

    # Additional invoice/commercial details.
    goods_description = db.Column(db.String(255), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    country_of_origin = db.Column(db.String(100), nullable=True)
    hs_code = db.Column(db.String(30), nullable=True)
    declared_value = db.Column(db.Float, nullable=False, default=0.0)
    declared_currency = db.Column(db.String(10), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)
    amount_paid = db.Column(db.Float, nullable=False, default=0.0)
    due_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    shipment = db.relationship("Shipment", backref=db.backref("invoices", lazy=True))


# =========================================================
# HELPERS
# =========================================================

def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("admin_logged_in"):
            return redirect(
                url_for(
                    "admin_login",
                    next=request.path,
                )
            )

        return view(*args, **kwargs)

    return wrapped


def generate_tracking_number():

    while True:

        tracking_number = (
            f"WLC{random.randint(100000000, 999999999)}"
        )

        existing = Shipment.query.filter_by(
            tracking_number=tracking_number
        ).first()

        if not existing:
            return tracking_number


def add_tracking_event(
    shipment,
    status=None,
    location=None,
    note=None,
):

    event = TrackingEvent(
        shipment_id=shipment.id,
        status=status or shipment.status,
        location=location or shipment.current_location,
        note=note,
        event_time=datetime.utcnow(),
    )

    db.session.add(event)

    return event


def parse_float(
    value,
    default=0.0,
):

    try:
        return float(value)

    except (TypeError, ValueError):
        return default


COUNTRIES = [
    "Kenya", "Suriname", "United Kingdom", "United States", "Canada",
    "Netherlands", "France", "Germany", "Belgium", "Italy", "Spain",
    "Portugal", "Ireland", "Switzerland", "Sweden", "Norway", "Denmark",
    "Finland", "Poland", "Austria", "Australia", "New Zealand", "South Africa",
    "Nigeria", "Ghana", "Uganda", "Tanzania", "Rwanda", "United Arab Emirates",
    "Saudi Arabia", "Qatar", "India", "China", "Japan", "Singapore", "Malaysia",
    "Brazil", "Mexico", "Other",
]

CURRENCIES = ["USD", "EUR", "GBP", "KES", "SRD", "CAD", "AUD"]


def generate_invoice_number():
    while True:
        number = f"WLI-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        if not Invoice.query.filter_by(invoice_number=number).first():
            return number


def money(value):
    return f"{float(value or 0):,.2f}"


def clean_invoice_amounts(invoice):
    """Keep customer billing amounts non-negative and payment within the total."""
    for field in (
        "shipping_amount", "customs_amount", "handling_amount",
        "other_amount", "tax_amount", "discount_amount", "amount_paid",
        "declared_value"
    ):
        value = getattr(invoice, field, 0) or 0
        setattr(invoice, field, max(float(value), 0.0))

    subtotal = (
        invoice.shipping_amount + invoice.customs_amount +
        invoice.handling_amount + invoice.other_amount
    )
    total = max(subtotal + invoice.tax_amount - invoice.discount_amount, 0.0)
    invoice.amount_paid = min(invoice.amount_paid, total)
    return total


def build_invoice_pdf(invoice):
    if colors is None:
        raise RuntimeError("PDF support is not installed. Install reportlab.")

    shipment = invoice.shipment
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title=f"{invoice.document_type} {invoice.invoice_number}",
        author="Worldlink Courier Service",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="InvoiceTitle2", parent=styles["Heading1"], fontSize=20, leading=23,
        textColor=colors.HexColor("#0b1f3a"), spaceAfter=3))
    styles.add(ParagraphStyle(
        name="SmallMuted2", parent=styles["Normal"], fontSize=7.5, leading=10,
        textColor=colors.HexColor("#66788f")))
    styles.add(ParagraphStyle(
        name="BodySmall2", parent=styles["Normal"], fontSize=8.2, leading=10.5,
        textColor=colors.HexColor("#17263a")))

    story = []
    logo_path = os.path.join(app.root_path, "static", "images", "worldlink-logo.png")
    logo = Image(logo_path, width=47*mm, height=13*mm, kind="proportional") if os.path.exists(logo_path) else Paragraph("<b>WORLDLINK COURIER SERVICE</b>", styles["InvoiceTitle2"])
    meta = Paragraph(
        f"<b>{invoice.document_type.upper()}</b><br/><b>{invoice.invoice_number}</b><br/>"
        f"Issued {invoice.created_at.strftime('%d %b %Y')}"
        + (f"<br/>Due {invoice.due_date.strftime('%d %b %Y')}" if invoice.due_date else ""),
        styles["BodySmall2"])
    header = Table([[logo, meta]], colWidths=[105*mm,70*mm])
    header.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(1,0),(1,0),"RIGHT"),
                                ("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story += [header, Spacer(1,3*mm)]

    info = Table([
        [Paragraph("<b>BILL TO / RECEIVER</b>", styles["SmallMuted2"]), Paragraph("<b>SENDER</b>", styles["SmallMuted2"])],
        [Paragraph(f"<b>{shipment.receiver}</b><br/>{shipment.receiver_address}<br/>{shipment.receiver_phone}", styles["BodySmall2"]),
         Paragraph(f"<b>{shipment.sender}</b><br/>{shipment.sender_address}", styles["BodySmall2"])],
        [Paragraph("<b>SHIPMENT</b>", styles["SmallMuted2"]), Paragraph("<b>PACKAGE</b>", styles["SmallMuted2"])],
        [Paragraph(f"<b>{shipment.tracking_number}</b><br/>{shipment.origin} → {shipment.destination}<br/>{shipment.service_type}", styles["BodySmall2"]),
         Paragraph(f"{invoice.goods_description or shipment.package_description}<br/>Quantity: {invoice.quantity}<br/>Weight: {money(shipment.weight)} kg", styles["BodySmall2"])]
    ], colWidths=[87.5*mm,87.5*mm])
    info.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f7f9fc")),
        ("BACKGROUND",(0,2),(-1,2),colors.HexColor("#f7f9fc")),
        ("BOX",(0,0),(-1,-1),0.55,colors.HexColor("#dce5ef")),
        ("INNERGRID",(0,0),(-1,-1),0.4,colors.HexColor("#e5ebf2")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)
    ]))
    story += [info, Spacer(1,4*mm)]

    customs = Table([
        [Paragraph("<b>CUSTOMS / GOODS DETAILS</b>", styles["SmallMuted2"]), Paragraph("<b>PAYMENT</b>", styles["SmallMuted2"])],
        [Paragraph(
            f"Customs country: <b>{invoice.customs_country or 'Not applicable'}</b><br/>"
            f"Country of origin: {invoice.country_of_origin or 'Not specified'}<br/>"
            f"HS code: {invoice.hs_code or 'Not specified'}<br/>"
            f"Declared value: {invoice.declared_currency or invoice.currency} {money(invoice.declared_value)}",
            styles["BodySmall2"]),
         Paragraph(
            f"Status: <b>{invoice.payment_status}</b><br/>"
            f"Method: {invoice.payment_method or 'Not specified'}<br/>"
            f"Amount paid: {invoice.currency} {money(invoice.amount_paid)}",
            styles["BodySmall2"])]
    ], colWidths=[87.5*mm,87.5*mm])
    customs.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f7f9fc")),
        ("BOX",(0,0),(-1,-1),0.55,colors.HexColor("#dce5ef")),
        ("INNERGRID",(0,0),(-1,-1),0.4,colors.HexColor("#e5ebf2")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)
    ]))
    story += [customs, Spacer(1,4*mm)]

    rows = [["Description", "Amount"]]
    charges = [
        ("Courier / shipping service", invoice.shipping_amount),
        ("Customs billing", invoice.customs_amount),
        ("Handling / clearance", invoice.handling_amount),
        ("Other service charge", invoice.other_amount),
        ("Tax", invoice.tax_amount),
    ]
    for label, value in charges:
        if value:
            rows.append([label, f"{invoice.currency} {money(value)}"])
    if invoice.discount_amount:
        rows.append(["Discount", f"- {invoice.currency} {money(invoice.discount_amount)}"])
    if len(rows) == 1:
        rows.append(["Billing amount", f"{invoice.currency} 0.00"])

    subtotal = (invoice.shipping_amount or 0) + (invoice.customs_amount or 0) + (invoice.handling_amount or 0) + (invoice.other_amount or 0)
    total = max(subtotal + (invoice.tax_amount or 0) - (invoice.discount_amount or 0), 0)
    balance = max(total - (invoice.amount_paid or 0), 0)
    rows.append([Paragraph("<b>Total</b>", styles["BodySmall2"]), Paragraph(f"<b>{invoice.currency} {money(total)}</b>", styles["BodySmall2"])])
    rows.append(["Amount paid", f"{invoice.currency} {money(invoice.amount_paid)}"])
    rows.append([Paragraph("<b>Balance due</b>", styles["BodySmall2"]), Paragraph(f"<b>{invoice.currency} {money(balance)}</b>", styles["BodySmall2"])])

    table = Table(rows, colWidths=[125*mm,50*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0b1f3a")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,0),8.5),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#dce5ef")),
        ("ALIGN",(1,1),(1,-1),"RIGHT"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("BACKGROUND",(0,-3),(-1,-1),colors.HexColor("#f7f9fc"))
    ]))
    story += [table, Spacer(1,5*mm)]

    if invoice.notes:
        story += [Paragraph(f"<b>Notes:</b> {invoice.notes}", styles["SmallMuted2"]), Spacer(1,5*mm)]

    signature = Table([[
        Paragraph(
            "<font name='Helvetica-Oblique' size='20' color='#183f75'><i>Worldlink</i></font><br/>"
            "_____________________________<br/>"
            "<font size='7'><b>AUTHORIZED WORLDLINK BILLING OFFICER</b></font>",
            styles["SmallMuted2"]
        ),
        Paragraph("<b>WORLDLINK</b><br/><b>AUTHORIZED BILLING</b><br/><font size='6'>CUSTOMS &amp; CLEARANCE</font>", styles["BodySmall2"])
    ]], colWidths=[120*mm,55*mm])
    signature.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("BOX",(1,0),(1,0),1,colors.HexColor("#1769ff")),
        ("ALIGN",(1,0),(1,0),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)
    ]))
    story += [signature, Spacer(1,4*mm),
              Paragraph(f"Worldlink Courier Service · Billing & Customer Documentation · {invoice.invoice_number}", styles["SmallMuted2"])]

    doc.build(story)
    buffer.seek(0)
    return buffer


def get_unread_chat_count():

    return ChatMessage.query.filter_by(
        sender_type="customer",
        is_read=False,
    ).count()


@app.context_processor
def inject_globals():

    return {
        "current_year": datetime.utcnow().year,
        "statuses": STATUSES,
    }


# =========================================================
# PUBLIC PAGES
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )

@app.route(
    "/track",
    methods=["GET", "POST"],
)
def track():

    shipment = None
    tracking_events = []
    message = None
    tracking_number = ""

    if request.method == "POST":

        tracking_number = (
            request.form.get(
                "tracking_number",
                "",
            )
            .strip()
            .upper()
        )

        shipment = Shipment.query.filter_by(
            tracking_number=tracking_number
        ).first()

        if shipment:

            tracking_events = (
                TrackingEvent.query
                .filter_by(
                    shipment_id=shipment.id
                )
                .order_by(
                    TrackingEvent.event_time.desc()
                )
                .all()
            )

        else:

            message = (
                "We couldn't find that tracking number. "
                "Please check it and try again."
            )

    return render_template(
        "tracking.html",
        shipment=shipment,
        tracking_events=tracking_events,
        message=message,
        tracking_number=tracking_number,
    )


@app.route("/services")
def services():

    return render_template(
        "services.html"
    )


@app.route("/rates")
def rates():

    return render_template(
        "rates.html"
    )


@app.route("/support")
def support():

    return render_template(
        "support.html"
    )


# =========================================================
# TRACKING API
# =========================================================

@app.route(
    "/api/track/<tracking_number>"
)
def api_track(tracking_number):

    shipment = Shipment.query.filter_by(
        tracking_number=tracking_number.strip().upper()
    ).first()

    if not shipment:

        return jsonify({
            "found": False
        }), 404

    events = [

        {
            "status": event.status,
            "location": event.location,
            "note": event.note,
            "time": event.event_time.isoformat(),
        }

        for event in shipment.events

    ]

    return jsonify({

        "found": True,

        "shipment": {

            "tracking_number":
                shipment.tracking_number,

            "status":
                shipment.status,

            "current_location":
                shipment.current_location,

            "origin":
                shipment.origin,

            "destination":
                shipment.destination,

            "service_type":
                shipment.service_type,

            "estimated_delivery": (
                shipment.estimated_delivery.isoformat()
                if shipment.estimated_delivery
                else None
            ),

            "events":
                events,
        }

    })


# =========================================================
# ADMIN AUTHENTICATION
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"],
)
def admin_login():

    if session.get("admin_logged_in"):

        return redirect(
            url_for("admin_dashboard")
        )

    message = None

    if request.method == "POST":

        username = (
            request.form.get(
                "username",
                "",
            )
            .strip()
        )

        password = request.form.get(
            "password",
            "",
        )

        if (
            username == ADMIN_USERNAME
            and check_password_hash(
                ADMIN_PASSWORD_HASH,
                password,
            )
        ):

            session.clear()

            session["admin_logged_in"] = True
            session["admin_username"] = username

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        message = (
            "Invalid username or password."
        )

    return render_template(
        "admin_login.html",
        message=message,
    )


@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    search = (
        request.args.get(
            "q",
            "",
        )
        .strip()
    )

    status_filter = (
        request.args.get(
            "status",
            "",
        )
        .strip()
    )

    query = Shipment.query

    if search:

        pattern = f"%{search}%"

        query = query.filter(
            or_(
                Shipment.tracking_number.ilike(
                    pattern
                ),

                Shipment.sender.ilike(
                    pattern
                ),

                Shipment.receiver.ilike(
                    pattern
                ),

                Shipment.origin.ilike(
                    pattern
                ),

                Shipment.destination.ilike(
                    pattern
                ),

                Shipment.current_location.ilike(
                    pattern
                ),
            )
        )

    if status_filter:

        query = query.filter_by(
            status=status_filter
        )

    shipments = (
        query
        .order_by(
            Shipment.id.desc()
        )
        .all()
    )

    total = Shipment.query.count()

    delivered = Shipment.query.filter_by(
        status="Delivered"
    ).count()

    in_transit = Shipment.query.filter_by(
        status="In Transit"
    ).count()

    out_for_delivery = (
        Shipment.query
        .filter_by(
            status="Out for Delivery"
        )
        .count()
    )

    unread_chats = get_unread_chat_count()

    return render_template(
        "admin_dashboard.html",

        shipments=shipments,

        total=total,

        delivered=delivered,

        in_transit=in_transit,

        out_for_delivery=out_for_delivery,

        search=search,

        status_filter=status_filter,

        unread_chats=unread_chats,
    )


# =========================================================
# CREATE SHIPMENT
# =========================================================

@app.route(
    "/admin/create-shipment",
    methods=["GET", "POST"],
)
@admin_required
def create_shipment():

    if request.method == "POST":

        selected_status = (
            request.form.get(
                "status",
                "Shipment Received",
            )
            .strip()
        )

        if selected_status not in STATUSES:

            selected_status = (
                "Shipment Received"
            )

        shipment = Shipment(

            tracking_number=
                generate_tracking_number(),

            sender=
                request.form.get(
                    "sender",
                    "",
                ).strip()
                or "Not provided",

            sender_address=
                request.form.get(
                    "sender_address",
                    "",
                ).strip()
                or "Not provided",

            receiver=
                request.form.get(
                    "receiver",
                    "",
                ).strip()
                or "Not provided",

            receiver_address=
                request.form.get(
                    "receiver_address",
                    "",
                ).strip()
                or "Not provided",

            receiver_phone=
                request.form.get(
                    "receiver_phone",
                    "",
                ).strip()
                or "Not provided",

            origin=
                request.form.get(
                    "origin",
                    "",
                ).strip()
                or "Not provided",

            destination=
                request.form.get(
                    "destination",
                    "",
                ).strip()
                or "Not provided",

            current_location=(
                request.form.get(
                    "current_location",
                    "",
                ).strip()

                or request.form.get(
                    "origin",
                    "",
                ).strip()

                or "Not updated"
            ),

            status=selected_status,

            service_type=
                request.form.get(
                    "service_type",
                    "International Express",
                ).strip()
                or "International Express",

            package_description=
                request.form.get(
                    "package_description",
                    "",
                ).strip()
                or "Parcel",

            weight=
                parse_float(
                    request.form.get(
                        "weight"
                    ),
                    0.0,
                ),
        )

        estimated = (
            request.form.get(
                "estimated_delivery",
                "",
            )
            .strip()
        )

        if estimated:

            try:

                shipment.estimated_delivery = (
                    datetime.strptime(
                        estimated,
                        "%Y-%m-%d",
                    ).date()
                )

            except ValueError:

                shipment.estimated_delivery = None

        db.session.add(shipment)

        db.session.flush()

        add_tracking_event(
            shipment,
            note=(
                "Shipment created and registered "
                "in the Worldlink tracking system."
            ),
        )

        db.session.commit()

        flash(
            f"Shipment {shipment.tracking_number} "
            "created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "shipment_receipt",
                shipment_id=shipment.id,
            )
        )

    return render_template(
        "create_shipment.html"
    )


# =========================================================
# EDIT SHIPMENT
# =========================================================

@app.route(
    "/admin/edit-shipment/<int:shipment_id>",
    methods=["GET", "POST"],
)
@admin_required
def edit_shipment(shipment_id):

    shipment = Shipment.query.get_or_404(
        shipment_id
    )

    if request.method == "POST":

        old_status = shipment.status
        old_location = shipment.current_location

        new_status = (
            request.form.get(
                "status",
                shipment.status,
            )
            .strip()
        )

        if new_status not in STATUSES:

            new_status = shipment.status

        old_rank = STATUS_ORDER.get(
            old_status
        )

        new_rank = STATUS_ORDER.get(
            new_status
        )

        # Prevent normal shipment stages from
        # being moved backwards.
        if (
            old_rank is not None
            and new_rank is not None
            and new_rank < old_rank
        ):

            flash(
                "Shipment status cannot be moved "
                "backward.",
                "error",
            )

            return redirect(
                url_for(
                    "edit_shipment",
                    shipment_id=shipment.id,
                )
            )

        shipment.status = new_status

        shipment.current_location = (
            request.form.get(
                "current_location",
                shipment.current_location,
            )
            .strip()
        )

        estimated = (
            request.form.get(
                "estimated_delivery",
                "",
            )
            .strip()
        )

        if estimated:

            try:

                shipment.estimated_delivery = (
                    datetime.strptime(
                        estimated,
                        "%Y-%m-%d",
                    ).date()
                )

            except ValueError:

                pass

        else:

            shipment.estimated_delivery = None

        note = (
            request.form.get(
                "note",
                "",
            )
            .strip()
        )

        changed = (
            shipment.status != old_status
            or shipment.current_location != old_location
            or bool(note)
        )

        if changed:

            add_tracking_event(
                shipment,

                status=shipment.status,

                location=shipment.current_location,

                note=(
                    note
                    or "Shipment tracking information updated."
                ),
            )

        db.session.commit()

        flash(
            f"{shipment.tracking_number} updated.",
            "success",
        )

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "edit_shipment.html",
        shipment=shipment,
    )


# =========================================================
# DELETE SHIPMENT
# =========================================================

@app.route(
    "/admin/delete-shipment/<int:shipment_id>",
    methods=["POST"],
)
@admin_required
def delete_shipment(shipment_id):

    shipment = Shipment.query.get_or_404(
        shipment_id
    )

    tracking_number = shipment.tracking_number

    db.session.delete(shipment)

    db.session.commit()

    flash(
        f"Parcel {tracking_number} was deleted.",
        "success",
    )

    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# ADMIN INVOICES
# =========================================================

@app.route("/admin/invoices")
@admin_required
def admin_invoices():
    q = request.args.get("q", "").strip()
    query = Invoice.query
    if q:
        pattern = f"%{q}%"
        query = query.join(Shipment).filter(
            or_(
                Invoice.invoice_number.ilike(pattern),
                Invoice.document_type.ilike(pattern),
                Invoice.customs_country.ilike(pattern),
                Shipment.tracking_number.ilike(pattern),
                Shipment.receiver.ilike(pattern),
                Shipment.sender.ilike(pattern),
            )
        )
    invoices = query.order_by(Invoice.id.desc()).all()
    return render_template("admin_invoices.html", invoices=invoices, search=q)


@app.route("/admin/invoices/new", methods=["GET", "POST"])
@admin_required
def create_invoice():
    shipments = Shipment.query.order_by(Shipment.id.desc()).all()
    selected_id = request.args.get("shipment_id", type=int)
    selected_shipment = Shipment.query.get(selected_id) if selected_id else None

    if request.method == "POST":
        shipment_id = request.form.get("shipment_id", type=int)
        shipment = Shipment.query.get_or_404(shipment_id)

        document_type = request.form.get("document_type", "Courier Invoice").strip()
        if document_type not in {"Courier Invoice", "Customs Billing", "Commercial Invoice", "Proforma Invoice"}:
            document_type = "Courier Invoice"

        currency = request.form.get("currency", "USD").strip().upper()
        if currency not in CURRENCIES:
            currency = "USD"

        payment_status = request.form.get("payment_status", "Pending").strip() or "Pending"
        if payment_status not in {"Pending", "Partially Paid", "Paid", "Cancelled"}:
            payment_status = "Pending"

        due_date = None
        due_date_raw = request.form.get("due_date", "").strip()
        if due_date_raw:
            try:
                due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
            except ValueError:
                due_date = None

        invoice = Invoice(
            invoice_number=generate_invoice_number(),
            shipment_id=shipment.id,
            document_type=document_type,
            customs_country=request.form.get("customs_country", "").strip() or None,
            currency=currency,
            shipping_amount=parse_float(request.form.get("shipping_amount")),
            customs_amount=parse_float(request.form.get("customs_amount")),
            handling_amount=parse_float(request.form.get("handling_amount")),
            other_amount=parse_float(request.form.get("other_amount")),
            tax_amount=parse_float(request.form.get("tax_amount")),
            discount_amount=parse_float(request.form.get("discount_amount")),
            payment_status=payment_status,
            notes=request.form.get("notes", "").strip(),
            goods_description=request.form.get("goods_description", "").strip() or shipment.package_description,
            quantity=max(int(request.form.get("quantity", "1") or 1), 1),
            country_of_origin=request.form.get("country_of_origin", "").strip() or None,
            hs_code=request.form.get("hs_code", "").strip() or None,
            declared_value=parse_float(request.form.get("declared_value")),
            declared_currency=request.form.get("declared_currency", currency).strip().upper() or currency,
            payment_method=request.form.get("payment_method", "").strip() or None,
            amount_paid=parse_float(request.form.get("amount_paid")),
            due_date=due_date,
        )

        clean_invoice_amounts(invoice)
        db.session.add(invoice)
        db.session.commit()

        flash(f"{invoice.invoice_number} saved successfully.", "success")
        return redirect(url_for("invoice_detail", invoice_id=invoice.id))

    shipment_data = {
        str(s.id): {
            "sender": s.sender,
            "sender_address": s.sender_address,
            "receiver": s.receiver,
            "receiver_address": s.receiver_address,
            "receiver_phone": s.receiver_phone,
            "origin": s.origin,
            "destination": s.destination,
            "tracking_number": s.tracking_number,
            "service_type": s.service_type,
            "package_description": s.package_description,
            "weight": s.weight,
        }
        for s in shipments
    }

    return render_template(
        "create_invoice.html",
        shipments=shipments,
        selected_shipment=selected_shipment,
        shipment_data=shipment_data,
        countries=COUNTRIES,
        currencies=CURRENCIES,
    )


@app.route("/admin/invoices/<int:invoice_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    shipments = Shipment.query.order_by(Shipment.id.desc()).all()

    if request.method == "POST":
        shipment_id = request.form.get("shipment_id", type=int)
        shipment = Shipment.query.get_or_404(shipment_id)

        document_type = request.form.get("document_type", invoice.document_type).strip()
        if document_type not in {"Courier Invoice", "Customs Billing", "Commercial Invoice", "Proforma Invoice"}:
            document_type = invoice.document_type

        currency = request.form.get("currency", invoice.currency).strip().upper()
        if currency not in CURRENCIES:
            currency = invoice.currency

        payment_status = request.form.get("payment_status", invoice.payment_status).strip() or invoice.payment_status
        if payment_status not in {"Pending", "Partially Paid", "Paid", "Cancelled"}:
            payment_status = invoice.payment_status

        due_date = None
        due_date_raw = request.form.get("due_date", "").strip()
        if due_date_raw:
            try:
                due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
            except ValueError:
                due_date = invoice.due_date

        invoice.shipment_id = shipment.id
        invoice.document_type = document_type
        invoice.customs_country = request.form.get("customs_country", "").strip() or None
        invoice.currency = currency
        invoice.shipping_amount = parse_float(request.form.get("shipping_amount"))
        invoice.customs_amount = parse_float(request.form.get("customs_amount"))
        invoice.handling_amount = parse_float(request.form.get("handling_amount"))
        invoice.other_amount = parse_float(request.form.get("other_amount"))
        invoice.tax_amount = parse_float(request.form.get("tax_amount"))
        invoice.discount_amount = parse_float(request.form.get("discount_amount"))
        invoice.payment_status = payment_status
        invoice.notes = request.form.get("notes", "").strip()
        invoice.goods_description = request.form.get("goods_description", "").strip() or shipment.package_description
        try:
            invoice.quantity = max(int(request.form.get("quantity", "1") or 1), 1)
        except ValueError:
            invoice.quantity = 1
        invoice.country_of_origin = request.form.get("country_of_origin", "").strip() or None
        invoice.hs_code = request.form.get("hs_code", "").strip() or None
        invoice.declared_value = parse_float(request.form.get("declared_value"))
        invoice.declared_currency = request.form.get("declared_currency", currency).strip().upper() or currency
        invoice.payment_method = request.form.get("payment_method", "").strip() or None
        invoice.amount_paid = parse_float(request.form.get("amount_paid"))
        invoice.due_date = due_date

        clean_invoice_amounts(invoice)
        db.session.commit()
        flash(f"{invoice.invoice_number} updated successfully.", "success")
        return redirect(url_for("invoice_detail", invoice_id=invoice.id))

    shipment_data = {
        str(s.id): {
            "sender": s.sender,
            "sender_address": s.sender_address,
            "receiver": s.receiver,
            "receiver_address": s.receiver_address,
            "receiver_phone": s.receiver_phone,
            "origin": s.origin,
            "destination": s.destination,
            "tracking_number": s.tracking_number,
            "service_type": s.service_type,
            "package_description": s.package_description,
            "weight": s.weight,
        }
        for s in shipments
    }

    return render_template(
        "create_invoice.html",
        shipments=shipments,
        selected_shipment=invoice.shipment,
        shipment_data=shipment_data,
        countries=COUNTRIES,
        currencies=CURRENCIES,
        invoice=invoice,
        editing=True,
    )


@app.route("/admin/invoices/<int:invoice_id>")
@admin_required
def invoice_detail(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    subtotal = (
        invoice.shipping_amount
        + invoice.customs_amount
        + invoice.handling_amount
        + invoice.other_amount
        + invoice.tax_amount
    )
    total = max(subtotal - invoice.discount_amount, 0)
    return render_template("invoice_detail.html", invoice=invoice, total=total)


@app.route("/admin/invoices/<int:invoice_id>/pdf")
@admin_required
def invoice_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    try:
        pdf = build_invoice_pdf(invoice)
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("invoice_detail", invoice_id=invoice.id))

    safe_name = invoice.invoice_number.replace("/", "-")
    from flask import send_file
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{safe_name}.pdf",
    )


# =========================================================
# SHIPMENT RECEIPT
# =========================================================

@app.route(
    "/admin/receipt/<int:shipment_id>"
)
@admin_required
def shipment_receipt(shipment_id):

    shipment = Shipment.query.get_or_404(
        shipment_id
    )

    return render_template(
        "receipt.html",
        shipment=shipment,
    )


# =========================================================
# CUSTOMER LIVE CHAT
# =========================================================

def extract_chat_tracking_number(message="", tracking_number=""):
    """
    Return a valid Worldlink tracking number supplied by the customer.
    Tracking numbers generated by this system use WLC + 9 digits.
    """
    supplied = (tracking_number or "").strip().upper()

    if re.fullmatch(r"WLC\d{9}", supplied):
        return supplied

    match = re.search(r"\bWLC\d{9}\b", (message or "").upper())

    return match.group(0) if match else ""


def build_chat_tracking_reply(tracking_number):
    """
    Build a customer-safe automatic tracking response.
    Do not expose private receiver contact details through live chat.
    """
    shipment = Shipment.query.filter_by(
        tracking_number=tracking_number
    ).first()

    if not shipment:
        return None

    latest_event = shipment.events[0] if shipment.events else None

    lines = [
        "Shipment found",
        "",
        f"Tracking number: {shipment.tracking_number}",
        f"Status: {shipment.status}",
        f"Current location: {shipment.current_location}",
        f"Origin: {shipment.origin}",
        f"Destination: {shipment.destination}",
    ]

    if shipment.service_type:
        lines.append(f"Service: {shipment.service_type}")

    if shipment.estimated_delivery:
        lines.append(
            "Estimated delivery: "
            + shipment.estimated_delivery.strftime("%d %b %Y")
        )

    if latest_event:
        lines.append("")
        lines.append("Latest tracking update:")
        lines.append(
            f"{latest_event.status} — {latest_event.location}"
        )

        if latest_event.note:
            lines.append(f"Note: {latest_event.note}")

        lines.append(
            "Updated: "
            + latest_event.event_time.strftime("%d %b %Y, %H:%M")
        )

    lines.extend([
        "",
        "This information is from the Worldlink tracking system. "
        "If you need further assistance, our support team can help you here."
    ])

    return "\n".join(lines)


def is_human_support_request(message):
    """Return True when the customer explicitly asks for a human representative."""
    normalized = re.sub(r"[^a-z0-9\s]", " ", (message or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    human_phrases = {
        "human", "agent", "support", "talk to support", "speak to support",
        "talk to someone", "speak to someone", "human agent",
        "customer service", "real person", "representative", "customer support",
        "i need a human", "i want a human", "i need an agent",
        "i want an agent", "i want to talk with an agent",
        "i want to talk to an agent", "i need to talk with an agent",
        "i need to talk to an agent", "i want to speak with an agent",
        "i want to speak to an agent", "i need to speak with an agent",
        "i need to speak to an agent", "i want to talk with someone",
        "i want to talk to someone", "i need to talk with someone",
        "i need to talk to someone", "i want to speak with someone",
        "i want to speak to someone", "i need to speak with someone",
        "i need to speak to someone", "connect me to support",
        "connect me with support", "connect me to an agent",
        "connect me with an agent", "let me talk to support",
        "let me speak to support", "let me talk to an agent",
        "let me speak to an agent",
    }
    return normalized in human_phrases


def build_auto_support_reply(message, tracking_number=""):
    """Rule-based 24/7 Worldlink customer support assistant."""
    normalized = re.sub(r"[^a-z0-9\s]", " ", (message or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    tracking_phrases = {
        "track", "tracking", "track shipment", "track my shipment",
        "track my package", "track my parcel", "i would like to track",
        "i would like to track my shipment", "i would like to track my package",
        "i want to track", "i want to track my shipment", "i want to track my package",
        "i need to track", "can i track", "how can i track",
        "where is my package", "where is my parcel", "where is my shipment",
        "where is my delivery", "check my shipment", "check my parcel",
    }
    if normalized in tracking_phrases:
        return ("Worldlink Virtual Support Assistant\n\n"
                "Of course. Please send your Worldlink tracking number "
                "(for example, WLC123456789), and I will check the latest "
                "shipment information for you.")

    greeting_words = {
        "hi", "hello", "hey", "good morning", "good afternoon",
        "good evening", "good day", "hi there", "hello there"
    }
    if normalized in greeting_words:
        return ("Worldlink Virtual Support Assistant\n\n"
                "Hello and welcome to Worldlink Courier Service. I can help with "
                "shipment tracking, delivery questions, general customs questions, "
                "and contacting support. If you need a human support representative, "
                "just say \"speak to support\".")

    human_phrases = {
        "human", "agent", "support", "talk to support", "speak to support",
        "talk to someone", "speak to someone", "talk with someone",
        "speak with someone", "talk to an agent", "talk with an agent",
        "speak to an agent", "speak with an agent", "human agent",
        "customer service", "real person", "representative", "customer support",
        "i want to talk with an agent", "i want to talk to an agent",
        "i want to speak with an agent", "i want to speak to an agent",
        "i want to talk with someone", "i want to talk to someone",
        "i want to speak with someone", "i want to speak to someone",
        "i need to talk with an agent", "i need to talk to an agent",
        "i need to speak with an agent", "i need to speak to an agent",
        "i need to talk with someone", "i need to talk to someone",
        "i need to speak with someone", "i need to speak to someone",
        "connect me with an agent", "connect me to an agent",
        "connect me with support", "connect me to support",
        "can i talk to an agent", "can i speak to an agent",
        "can i talk with an agent", "can i speak with an agent"
    }
    if normalized in human_phrases:
        return ("Worldlink Virtual Support Assistant\n\n"
                "Certainly. I've flagged this conversation for Worldlink Support. "
                "A support representative can continue the conversation with you. "
                "Please leave your question and we will assist you.")

    contact_phrases = {
        "contact", "contact support", "how can i contact support",
        "how do i contact support", "support contact", "support email",
        "what is your email", "what is your phone number", "phone number",
        "email address", "how can i reach support"
    }
    if normalized in contact_phrases:
        return ("Worldlink Virtual Support Assistant\n\n"
                "You can contact Worldlink Courier Service at:\n"
                "+44 7700900010\n"
                "support@worldlinkexpresscourier.com\n"
                "worldlinkexpresscourier.com\n\n"
                "You can also leave your question here and a support representative can assist you.")

    services_phrases = {
        "services", "what services do you offer", "what services do you provide",
        "what do you offer", "which services do you offer", "shipping services",
        "courier services", "international shipping", "do you ship internationally"
    }
    if normalized in services_phrases:
        return ("Worldlink Virtual Support Assistant\n\n"
                "Worldlink Courier Service provides courier and shipment services, "
                "including international shipment support and online shipment tracking. "
                "For a service option or quote for a specific destination, please contact "
                "Worldlink Support with your origin and destination details.")

    timing_phrases = {
        "how long does delivery take", "how long will delivery take",
        "how long does shipping take", "how long will shipping take",
        "delivery time", "shipping time", "when will it arrive",
        "when will my package arrive", "when will my parcel arrive",
        "when will i receive my package", "when will i receive my parcel",
        "when will i receive my shipment", "when can i expect my package",
        "when can i expect my parcel", "when can i expect my shipment",
        "when should i receive my package", "when should i receive my parcel",
        "when should i receive my shipment", "when should my package arrive",
        "when should my parcel arrive", "when should my shipment arrive",
        "what is the estimated delivery", "what is my estimated delivery",
        "estimated delivery", "expected delivery", "delivery date",
        "when is my delivery", "when is my package coming",
        "when is my parcel coming", "when is my shipment coming"
    }
    if normalized in timing_phrases:
        return ("Worldlink Virtual Support Assistant\n\n"
                "Delivery time depends on the service and destination. For a shipment already "
                "in transit, send your WLC tracking number and I can check its current status "
                "and estimated delivery. For a new shipment, Worldlink Support can provide "
                "the appropriate delivery estimate.")

    customs_terms = ("customs", "custom clearance", "customs clearance", "customs fee", "customs fees", "clearance")
    if any(term in normalized for term in customs_terms):
        return ("Worldlink Virtual Support Assistant\n\n"
                "I can help with general customs-support questions. Customs requirements, "
                "documents, and charges can depend on the shipment and destination. Please "
                "provide your tracking number for shipment-specific information, or ask to "
                "speak with Worldlink Support.")

    change_terms = ("change address", "change delivery address", "wrong address", "change my address",
                    "change delivery date", "change the delivery date", "reschedule delivery",
                    "change receiver", "change recipient")
    if any(term in normalized for term in change_terms):
        return ("Worldlink Virtual Support Assistant\n\n"
                "I can help route this request, but delivery-address or delivery-date changes "
                "require support review. Please send your tracking number and say \"speak to support\" "
                "so a representative can assist you.")

    invoice_terms = ("invoice", "need an invoice", "i need invoice", "send me an invoice",
                     "get an invoice", "invoice copy", "invoice number", "billing invoice")
    if any(term in normalized for term in invoice_terms):
        return ("Worldlink Virtual Support Assistant\n\n"
                "Certainly. I can help with an invoice request. Please provide your tracking number "
                "and tell me whether you need a new invoice or a copy of an existing invoice. "
                "A Worldlink Support representative can then assist you.")

    payment_terms = ("payment", "pay", "paid", "refund", "money back", "receipt")
    if any(term in normalized for term in payment_terms):
        return ("Worldlink Virtual Support Assistant\n\n"
                "For payment, receipt, or refund questions, a Worldlink Support representative "
                "needs to review the request. Please provide your tracking or invoice number if "
                "you have one, and ask to speak with support.")

    complaint_terms = ("complaint", "complain", "problem", "issue", "damaged", "lost", "missing", "not received")
    if any(term in normalized for term in complaint_terms):
        return ("Worldlink Virtual Support Assistant\n\n"
                "I'm sorry you're having trouble. Please provide your tracking number and a short "
                "description of the issue. A Worldlink Support representative can review the case "
                "and assist you further.")

    delivery_terms = ("delivery", "deliver", "arrive", "arrival", "late", "delayed")
    if any(term in normalized for term in delivery_terms):
        return ("Worldlink Virtual Support Assistant\n\n"
                "I can check a shipment's current status and estimated delivery. Please send your "
                "Worldlink tracking number, such as WLC123456789.")

    package_terms = ("parcel", "package", "shipment", "shipping", "courier")
    if any(term in normalized for term in package_terms):
        return ("Worldlink Virtual Support Assistant\n\n"
                "I can help you check a Worldlink shipment. Please send your tracking number, "
                "or tell me what you need help with.")

    return None



def build_invoice_download_token(invoice, tracking_number, customer_email):
    """Create a short-lived signed token for a customer invoice download."""
    return invoice_link_serializer.dumps({
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "tracking_number": tracking_number,
        "customer_email": (customer_email or "").strip().lower(),
    }, salt="worldlink-customer-invoice")


def build_invoice_download_url(invoice, tracking_number, customer_email):
    token = build_invoice_download_token(
        invoice,
        tracking_number,
        customer_email,
    )
    return url_for(
        "customer_invoice_pdf",
        invoice_number=invoice.invoice_number,
        token=token,
        _external=True,
    )


def build_invoice_chat_reply(conversation_id, message, tracking_number, customer_email):
    """Handle invoice requests using invoices already linked to the shipment."""
    normalized = re.sub(r"[^a-z0-9\s]", " ", (message or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    invoice_words = (
        "invoice", "billing invoice", "invoice copy", "invoice number",
        "copy of my invoice", "copy invoice", "download invoice",
    )
    invoice_context = any(word in normalized for word in invoice_words)

    recent_invoice_request = False
    if conversation_id:
        recent_messages = (
            ChatMessage.query
            .filter_by(conversation_id=conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
            .all()
        )
        recent_invoice_request = any(
            any(word in (item.message or "").lower() for word in invoice_words)
            for item in recent_messages
            if item.sender_type == "customer"
        )

    is_invoice_followup = (
        normalized in {
            "copy", "existing invoice", "old invoice", "invoice copy",
            "send the invoice", "send me the invoice", "download it",
            "download the invoice", "yes", "yes please", "the existing invoice",
        }
        and recent_invoice_request
    )

    if not invoice_context and not is_invoice_followup:
        return None

    if not tracking_number:
        return (
            "Worldlink Virtual Support Assistant\n\n"
            "I can help with your invoice request. Please send your Worldlink tracking "
            "number, for example WLC123456789."
        )

    shipment = Shipment.query.filter_by(tracking_number=tracking_number).first()
    if not shipment:
        return (
            "Worldlink Virtual Support Assistant\n\n"
            "I could not find a shipment for that tracking number. Please check the "
            "number and send it again."
        )

    invoices = (
        Invoice.query
        .filter_by(shipment_id=shipment.id)
        .order_by(Invoice.id.desc())
        .all()
    )

    wants_new = any(term in normalized for term in (
        "new invoice", "create an invoice", "make an invoice", "another invoice"
    ))

    wants_existing = (
        is_invoice_followup
        or any(term in normalized for term in (
            "copy", "existing", "download", "send me", "invoice copy"
        ))
    )

    if wants_new:
        return (
            "Worldlink Virtual Support Assistant\n\n"
            "A new invoice requires Worldlink Support to review the shipment charges "
            "before it is issued. I have identified your shipment. Please say "
            "\"speak to support\" and a representative can assist with the new invoice."
        )

    if invoices and wants_existing:
        invoice = invoices[0]
        invoice_url = build_invoice_download_url(
            invoice,
            shipment.tracking_number,
            customer_email,
        )
        return (
            "Worldlink Virtual Support Assistant\n\n"
            f"I found your latest invoice: {invoice.invoice_number}.\n\n"
            "Download your invoice here:\n"
            f"{invoice_url}\n\n"
            "This secure link is valid for 1 hour."
        )

    if invoices:
        invoice = invoices[0]
        return (
            "Worldlink Virtual Support Assistant\n\n"
            f"I found an existing invoice for {shipment.tracking_number}: "
            f"{invoice.invoice_number}. Would you like a copy of the existing invoice, "
            "or do you need a new invoice? Reply \"copy\" or \"new invoice\"."
        )

    return (
        "Worldlink Virtual Support Assistant\n\n"
        "I found your shipment, but there is currently no invoice linked to it. "
        "If you need a new invoice, please say \"speak to support\" so a Worldlink "
        "Support representative can review and issue it."
    )


@app.route("/chat/invoice/<invoice_number>/pdf")
def customer_invoice_pdf(invoice_number):
    """Serve a signed, short-lived customer invoice PDF without exposing admin access."""
    token = request.args.get("token", "").strip()
    if not token:
        return "Invoice link is missing or invalid.", 400

    try:
        payload = invoice_link_serializer.loads(
            token,
            salt="worldlink-customer-invoice",
            max_age=3600,
        )
    except SignatureExpired:
        return "This invoice link has expired. Please request a new invoice link through Worldlink Support.", 410
    except BadSignature:
        return "Invoice link is invalid.", 403

    if payload.get("invoice_number") != invoice_number:
        return "Invoice link is invalid.", 403

    invoice = Invoice.query.filter_by(invoice_number=invoice_number).first()
    if not invoice or str(invoice.id) != str(payload.get("invoice_id")):
        return "Invoice not found.", 404

    shipment = Shipment.query.get(invoice.shipment_id)
    if not shipment or shipment.tracking_number != payload.get("tracking_number"):
        return "Invoice link is invalid.", 403

    try:
        pdf = build_invoice_pdf(invoice)
    except RuntimeError as exc:
        return str(exc), 503

    safe_name = invoice.invoice_number.replace("/", "-")
    from flask import send_file
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{safe_name}.pdf",
    )


def get_conversation_tracking_number(conversation_id):
    """Return the most recent valid WLC tracking number in a chat conversation."""
    if not conversation_id:
        return ""

    messages = (
        ChatMessage.query
        .filter_by(conversation_id=conversation_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
        .all()
    )

    for item in messages:
        found = extract_chat_tracking_number(
            message=item.message or "",
            tracking_number=item.tracking_number or "",
        )
        if found:
            return found

    return ""


@app.route(
    "/chat/send",
    methods=["POST"],
)
def chat_send():

    data = (
        request.get_json(
            silent=True
        )
        or request.form
        or {}
    )

    # Accept both the current JavaScript names
    # and the older names for compatibility.
    customer_name = (
        data.get("customer_name")
        or data.get("name")
        or ""
    ).strip()

    customer_email = (
        data.get("customer_email")
        or data.get("email")
        or ""
    ).strip()

    tracking_number = (
        data.get(
            "tracking_number"
        )
        or ""
    ).strip().upper()

    message = (
        data.get(
            "message"
        )
        or ""
    ).strip()

    conversation_id = (
        data.get(
            "conversation_id"
        )
        or ""
    ).strip()

    if not customer_name:

        return jsonify({
            "success": False,
            "error": "Please enter your name.",
        }), 400

    if not customer_email:

        return jsonify({
            "success": False,
            "error": "Please enter your email address.",
        }), 400

    if not message:

        return jsonify({
            "success": False,
            "error": "Please enter a message.",
        }), 400

    if len(message) > 5000:

        return jsonify({
            "success": False,
            "error": "Message is too long.",
        }), 400

    if not conversation_id:

        conversation_id = uuid.uuid4().hex

    human_requested = is_human_support_request(message)

    chat = ChatMessage(

        conversation_id=
            conversation_id,

        sender_type=
            "customer",

        customer_name=
            customer_name,

        customer_email=
            customer_email,

        tracking_number=
            tracking_number or None,

        message=
            message,

        is_read=False,

        human_requested=
            human_requested,
    )

    db.session.add(chat)

    db.session.commit()

    # Automatic Worldlink support assistant.
    # Keep the latest WLC number in the conversation so a customer can
    # ask follow-up questions such as "when will it arrive?" without
    # repeating the tracking number every time.
    chat_tracking_number = extract_chat_tracking_number(
        message=message,
        tracking_number=tracking_number,
    )

    if not chat_tracking_number:
        chat_tracking_number = get_conversation_tracking_number(
            conversation_id
        )

    automatic_reply_text = None

    # Handle invoice requests before the general tracking follow-up logic.
    automatic_reply_text = build_invoice_chat_reply(
        conversation_id=conversation_id,
        message=message,
        tracking_number=chat_tracking_number,
        customer_email=customer_email,
    )

    if automatic_reply_text is None and chat_tracking_number:
        # Only answer with shipment data when the new message is a
        # tracking/follow-up request. Do not flood normal conversation
        # with the same tracking response.
        normalized_message = re.sub(
            r"[^a-z0-9\s]", " ", (message or "").lower()
        )
        normalized_message = re.sub(
            r"\s+", " ", normalized_message
        ).strip()

        tracking_followup_terms = (
            "track", "tracking", "where is", "where's", "status",
            "update", "latest update", "where is it", "where is my",
            "when will it arrive", "when will i receive it",
            "when will i get it", "when can i expect it",
            "when should i receive it", "estimated delivery",
            "expected delivery", "delivery date", "delivery time",
            "how long will it take", "how long does it take",
            "is it delivered", "has it arrived", "has my package arrived",
            "has my parcel arrived", "my package", "my parcel",
            "my shipment", "my delivery",
        )
        is_tracking_followup = any(
            term in normalized_message
            for term in tracking_followup_terms
        )

        # If the customer just sent the WLC number, always return its status.
        message_contains_tracking = bool(
            extract_chat_tracking_number(message=message, tracking_number="")
        )

        if message_contains_tracking or is_tracking_followup:
            automatic_reply_text = build_chat_tracking_reply(
                chat_tracking_number
            )
        else:
            automatic_reply_text = build_auto_support_reply(
                message=message,
                tracking_number=chat_tracking_number,
            )
    else:
        if automatic_reply_text is None:
            automatic_reply_text = build_auto_support_reply(
                message=message,
                tracking_number="",
            )

    if automatic_reply_text:
        bot_reply = ChatMessage(
            conversation_id=conversation_id,
            sender_type="support",
            customer_name=customer_name,
            customer_email=customer_email,
            tracking_number=chat_tracking_number or tracking_number or None,
            message=automatic_reply_text,
            is_read=True,
        )

        db.session.add(bot_reply)
        db.session.commit()

    return jsonify({

        "success": True,

        "ok": True,

        "conversation_id":
            conversation_id,

        "message": {

            "id":
                chat.id,

            "sender_type":
                chat.sender_type,

            "message":
                chat.message,

            "created_at":
                chat.created_at.isoformat(),
        },
    }), 201


# =========================================================
# CHAT TYPING STATUS
# =========================================================

CHAT_TYPING_TIMEOUT_SECONDS = 5


def _typing_status(conversation_id):
    status = ChatTypingStatus.query.filter_by(
        conversation_id=conversation_id
    ).first()

    if not status:
        return {
            "customer_typing": False,
            "admin_typing": False,
        }

    now = datetime.utcnow()

    customer_typing = bool(
        status.customer_typing_at
        and (now - status.customer_typing_at).total_seconds()
        <= CHAT_TYPING_TIMEOUT_SECONDS
    )

    admin_typing = bool(
        status.admin_typing_at
        and (now - status.admin_typing_at).total_seconds()
        <= CHAT_TYPING_TIMEOUT_SECONDS
    )

    return {
        "customer_typing": customer_typing,
        "admin_typing": admin_typing,
    }


def _set_typing_status(conversation_id, role, is_typing):
    conversation_id = (conversation_id or "").strip()

    if not conversation_id:
        return

    status = ChatTypingStatus.query.filter_by(
        conversation_id=conversation_id
    ).first()

    if not status:
        status = ChatTypingStatus(
            conversation_id=conversation_id
        )
        db.session.add(status)

    now = datetime.utcnow()

    if role == "customer":
        status.customer_typing_at = now if is_typing else None
    else:
        status.admin_typing_at = now if is_typing else None

    status.updated_at = now
    db.session.commit()


@app.route(
    "/api/chat/<conversation_id>/typing",
    methods=["GET", "POST"],
)
def customer_chat_typing(conversation_id):

    conversation_id = conversation_id.strip()

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        is_typing = bool(data.get("typing", False))

        _set_typing_status(
            conversation_id,
            "customer",
            is_typing,
        )

    status = _typing_status(conversation_id)

    return jsonify({
        "success": True,
        "conversation_id": conversation_id,
        "customer_typing": status["customer_typing"],
        "admin_typing": status["admin_typing"],
    })


@app.route(
    "/admin/api/chat/<conversation_id>/typing",
    methods=["GET", "POST"],
)
@admin_required
def admin_chat_typing(conversation_id):

    conversation_id = conversation_id.strip()

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        is_typing = bool(data.get("typing", False))

        _set_typing_status(
            conversation_id,
            "admin",
            is_typing,
        )

    status = _typing_status(conversation_id)

    return jsonify({
        "success": True,
        "conversation_id": conversation_id,
        "customer_typing": status["customer_typing"],
        "admin_typing": status["admin_typing"],
    })


# =========================================================
# ADMIN CHAT MESSAGE API
# =========================================================

@app.route(
    "/admin/api/chat/<conversation_id>"
)
@admin_required
def admin_chat_messages_api(conversation_id):

    conversation_id = conversation_id.strip()

    messages = (
        ChatMessage.query
        .filter_by(
            conversation_id=conversation_id
        )
        .order_by(
            ChatMessage.created_at.asc()
        )
        .all()
    )

    return jsonify({
        "success": True,
        "ok": True,
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": message.id,
                "sender_type": message.sender_type,
                "customer_name": message.customer_name,
                "customer_email": message.customer_email,
                "tracking_number": message.tracking_number,
                "message": message.message,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ],
    })


# =========================================================
# CUSTOMER CHAT MESSAGE API
# =========================================================

@app.route(
    "/api/chat/<conversation_id>"
)
def chat_messages(conversation_id):

    conversation_id = (
        conversation_id.strip()
    )

    messages = (
        ChatMessage.query
        .filter_by(
            conversation_id=conversation_id
        )
        .order_by(
            ChatMessage.created_at.asc()
        )
        .all()
    )

    return jsonify({

        "success": True,

        "ok": True,

        "conversation_id":
            conversation_id,

        "messages": [

            {

                "id":
                    message.id,

                "sender_type":
                    message.sender_type,

                "customer_name":
                    message.customer_name,

                "customer_email":
                    message.customer_email,

                "tracking_number":
                    message.tracking_number,

                "message":
                    message.message,

                "created_at":
                    message.created_at.isoformat(),
            }

            for message in messages
        ],
    })


# =========================================================
# ADMIN LIVE CHATS
# =========================================================

@app.route("/admin/chats")
@admin_required
def admin_chats():

    rows = (
        ChatMessage.query
        .order_by(
            ChatMessage.created_at.desc()
        )
        .all()
    )

    conversations = {}

    for row in rows:

        if row.conversation_id not in conversations:

            conversations[
                row.conversation_id
            ] = {

                "conversation_id":
                    row.conversation_id,

                "customer_name":
                    row.customer_name,

                "customer_email":
                    row.customer_email,

                "tracking_number":
                    row.tracking_number,

                "last_message":
                    row.message,

                "last_message_at":
                    row.created_at,

                "unread":
                    0,

                "human_requested":
                    False,
            }

        if (
            row.sender_type == "customer"
            and not row.is_read
        ):

            conversations[
                row.conversation_id
            ]["unread"] += 1

        if row.sender_type == "customer" and getattr(row, "human_requested", False):
            conversations[row.conversation_id]["human_requested"] = True

    conversation_list = list(
        conversations.values()
    )

    conversation_list.sort(
        key=lambda item: item["last_message_at"],
        reverse=True,
    )

    unread = get_unread_chat_count()

    return render_template(
        "admin_chats.html",

        conversations=
            conversation_list,

        chats=
            conversation_list,

        unread=
            unread,
    )


# =========================================================
# ADMIN INDIVIDUAL CHAT
# =========================================================

@app.route(
    "/admin/chat/<conversation_id>"
)
@admin_required
def admin_chat(conversation_id):

    conversation_id = (
        conversation_id.strip()
    )

    messages = (
        ChatMessage.query
        .filter_by(
            conversation_id=conversation_id
        )
        .order_by(
            ChatMessage.created_at.asc()
        )
        .all()
    )

    if not messages:

        flash(
            "Chat conversation not found.",
            "error",
        )

        return redirect(
            url_for("admin_chats")
        )

    # Keep the human-support flag separate from the normal unread state.
    # Opening the chat marks messages as read, but the support request remains flagged.
    human_requested = ChatMessage.query.filter_by(
        conversation_id=conversation_id,
        sender_type="customer",
        human_requested=True,
    ).first() is not None

    # Mark customer messages as read when the administrator opens the conversation.
    (
        ChatMessage.query
        .filter_by(
            conversation_id=conversation_id,
            sender_type="customer",
        )
        .update(
            {
                "is_read": True
            },
            synchronize_session=False,
        )
    )

    db.session.commit()

    if human_requested:
        flash(
            "Human support requested for this conversation.",
            "warning",
        )

    first_message = messages[0]

    return render_template(

        "admin_chat.html",

        messages=
            messages,

        conversation=
            first_message,

        conversation_id=
            conversation_id,

        customer_name=
            first_message.customer_name,

        customer_email=
            first_message.customer_email,

        tracking_number=
            first_message.tracking_number,
    )


# =========================================================
# ADMIN CHAT REPLY
# =========================================================

@app.route(
    "/admin/chat/<conversation_id>/reply",
    methods=["POST"],
)
@admin_required
def admin_chat_reply(conversation_id):

    conversation_id = (
        conversation_id.strip()
    )

    message = (
        request.form.get(
            "message",
            "",
        )
        .strip()
    )

    if not message:

        flash(
            "Please enter a reply.",
            "error",
        )

        return redirect(
            url_for(
                "admin_chat",
                conversation_id=conversation_id,
            )
        )

    first = (
        ChatMessage.query
        .filter_by(
            conversation_id=conversation_id
        )
        .order_by(
            ChatMessage.created_at.asc()
        )
        .first()
    )

    if not first:

        flash(
            "Conversation not found.",
            "error",
        )

        return redirect(
            url_for("admin_chats")
        )

    reply = ChatMessage(

        conversation_id=
            conversation_id,

        sender_type=
            "admin",

        customer_name=
            first.customer_name,

        customer_email=
            first.customer_email,

        tracking_number=
            first.tracking_number,

        message=
            message,

        is_read=True,
    )

    db.session.add(reply)

    db.session.commit()

    _set_typing_status(
        conversation_id,
        "admin",
        False,
    )

    return redirect(
        url_for(
            "admin_chat",
            conversation_id=conversation_id,
        )
    )


# =========================================================
# DATABASE INITIALIZATION + SAFE SCHEMA MIGRATION
# =========================================================

def initialize_database():

    with app.app_context():

        # Create any completely new tables.
        db.create_all()

        inspector = inspect(db.engine)

        # -------------------------------------------------
        # SHIPMENT TABLE MIGRATION
        # -------------------------------------------------

        shipment_columns = {
            column["name"]
            for column in inspector.get_columns("shipment")
        }

        # Add service_type if missing
        if "service_type" not in shipment_columns:

            db.session.execute(
                text(
                    """
                    ALTER TABLE shipment
                    ADD COLUMN service_type
                    VARCHAR(100)
                    NOT NULL
                    DEFAULT 'International Express'
                    """
                )
            )

            db.session.commit()

        # Add package_description if missing
        if "package_description" not in shipment_columns:

            db.session.execute(
                text(
                    """
                    ALTER TABLE shipment
                    ADD COLUMN package_description
                    VARCHAR(255)
                    NOT NULL
                    DEFAULT 'Parcel'
                    """
                )
            )

            db.session.commit()

        # Add weight if missing
        if "weight" not in shipment_columns:

            db.session.execute(
                text(
                    """
                    ALTER TABLE shipment
                    ADD COLUMN weight
                    DOUBLE PRECISION
                    NOT NULL
                    DEFAULT 0
                    """
                )
            )

            db.session.commit()

        # Add estimated_delivery if missing
        if "estimated_delivery" not in shipment_columns:

            db.session.execute(
                text(
                    """
                    ALTER TABLE shipment
                    ADD COLUMN estimated_delivery
                    DATE
                    """
                )
            )

            db.session.commit()

        # Add created_at if missing
        if "created_at" not in shipment_columns:

            db.session.execute(
                text(
                    """
                    ALTER TABLE shipment
                    ADD COLUMN created_at
                    TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
                    """
                )
            )

            db.session.commit()

        # -------------------------------------------------
        # TRACKING EVENT MIGRATION
        # -------------------------------------------------

        inspector = inspect(db.engine)

        if inspector.has_table("tracking_event"):

            tracking_columns = {
                column["name"]
                for column in inspector.get_columns(
                    "tracking_event"
                )
            }

            if "note" not in tracking_columns:

                db.session.execute(
                    text(
                        """
                        ALTER TABLE tracking_event
                        ADD COLUMN note
                        VARCHAR(255)
                        """
                    )
                )

                db.session.commit()

        # -------------------------------------------------
        # INVOICE TABLE MIGRATION
        # -------------------------------------------------

        inspector = inspect(db.engine)

        if inspector.has_table("invoice"):
            invoice_columns = {
                column["name"]
                for column in inspector.get_columns("invoice")
            }

            invoice_migrations = [
                ("goods_description", "VARCHAR(255)"),
                ("quantity", "INTEGER NOT NULL DEFAULT 1"),
                ("country_of_origin", "VARCHAR(100)"),
                ("hs_code", "VARCHAR(30)"),
                ("declared_value", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
                ("declared_currency", "VARCHAR(10)"),
                ("payment_method", "VARCHAR(50)"),
                ("amount_paid", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
                ("due_date", "DATE"),
            ]

            for column_name, column_sql in invoice_migrations:
                if column_name not in invoice_columns:
                    db.session.execute(
                        text(
                            f"ALTER TABLE invoice ADD COLUMN {column_name} {column_sql}"
                        )
                    )
                    db.session.commit()

        # -------------------------------------------------
        # CHAT TABLE MIGRATION
        # -------------------------------------------------
        chat_columns = {
            column["name"]
            for column in inspector.get_columns("chat_message")
        } if inspect(db.engine).has_table("chat_message") else set()

        if "human_requested" not in chat_columns and chat_columns:
            db.session.execute(
                text(
                    "ALTER TABLE chat_message "
                    "ADD COLUMN human_requested BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            db.session.commit()

        # CREATE ANY OTHER MISSING TABLES
        # -------------------------------------------------

        db.create_all()


initialize_database()


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
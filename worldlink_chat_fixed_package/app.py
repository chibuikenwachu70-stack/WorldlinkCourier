import os
import random
import uuid
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
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash


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


# =========================================================
# ADMIN CONFIGURATION
# =========================================================

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME",
    "admin",
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "change-this-password",
)

ADMIN_PASSWORD_HASH = os.getenv(
    "ADMIN_PASSWORD_HASH",
    generate_password_hash(ADMIN_PASSWORD),
)


# =========================================================
# SHIPMENT STATUSES
# =========================================================

STATUSES = [
    "Shipment Received",
    "Processing",
    "In Transit",
    "At Sorting Facility",
    "Customs Clearance",
    "Out for Delivery",
    "Delivered",
    "Delivery Exception",
    "On Hold",
]


STATUS_ORDER = {
    "Shipment Received": 1,
    "Processing": 2,
    "In Transit": 3,
    "At Sorting Facility": 4,
    "Customs Clearance": 5,
    "Out for Delivery": 6,
    "Delivered": 7,
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

    # If this is an existing conversation, recover the customer
    # details from the first saved message. This means a returning
    # customer does not have to enter their name and email again.
    if conversation_id:
        first_message = (
            ChatMessage.query
            .filter_by(conversation_id=conversation_id)
            .order_by(ChatMessage.created_at.asc())
            .first()
        )

        if first_message:
            if not customer_name:
                customer_name = first_message.customer_name
            if not customer_email:
                customer_email = first_message.customer_email
            if not tracking_number:
                tracking_number = first_message.tracking_number or ""

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
    )

    db.session.add(chat)

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
            }

        if (
            row.sender_type == "customer"
            and not row.is_read
        ):

            conversations[
                row.conversation_id
            ]["unread"] += 1

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
# ADMIN CHAT JSON API
# =========================================================

@app.route("/api/admin/chat/<conversation_id>")
@admin_required
def admin_chat_api(conversation_id):

    conversation_id = conversation_id.strip()

    messages = (
        ChatMessage.query
        .filter_by(conversation_id=conversation_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    if not messages:
        return jsonify({"success": False, "error": "Conversation not found."}), 404

    # The administrator is actively viewing this conversation, so
    # customer messages retrieved here are considered read.
    ChatMessage.query.filter_by(
        conversation_id=conversation_id,
        sender_type="customer",
    ).update(
        {"is_read": True},
        synchronize_session=False,
    )
    db.session.commit()

    return jsonify({
        "success": True,
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "customer_name": m.customer_name,
                "message": m.message,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    })


# =========================================================
# ADMIN CHAT LIST JSON API
# =========================================================

@app.route("/api/admin/chats")
@admin_required
def admin_chats_api():

    rows = (
        ChatMessage.query
        .order_by(ChatMessage.created_at.desc())
        .all()
    )

    conversations = {}

    for row in rows:
        if row.conversation_id not in conversations:
            conversations[row.conversation_id] = {
                "conversation_id": row.conversation_id,
                "customer_name": row.customer_name,
                "customer_email": row.customer_email,
                "tracking_number": row.tracking_number,
                "last_message": row.message,
                "last_message_at": row.created_at.isoformat(),
                "unread": 0,
            }

        if row.sender_type == "customer" and not row.is_read:
            conversations[row.conversation_id]["unread"] += 1

    conversation_list = list(conversations.values())
    conversation_list.sort(
        key=lambda item: item["last_message_at"],
        reverse=True,
    )

    return jsonify({
        "success": True,
        "unread": get_unread_chat_count(),
        "conversations": conversation_list,
    })


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

    # Mark customer messages as read
    # when the administrator opens the conversation.
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

    return redirect(
        url_for(
            "admin_chat",
            conversation_id=conversation_id,
        )
    )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

with app.app_context():

    db.create_all()


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
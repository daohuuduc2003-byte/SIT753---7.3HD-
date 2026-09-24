"""
server.py  —  River Trail Adventures
Task 10.2D: SQLite database integration

Run:  python3 server.py
Open: http://localhost:3000
"""

import os, re, sqlite3, html
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="public")
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "rivertrail.db")

# ── Database helpers ─────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS contacts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            email      TEXT    NOT NULL,
            phone      TEXT    NOT NULL,
            subject    TEXT    DEFAULT 'other',
            message    TEXT    NOT NULL,
            status     TEXT    DEFAULT 'new',
            created_at TEXT    DEFAULT (datetime('now','localtime')),
            updated_at TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS members (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            email        TEXT    NOT NULL UNIQUE,
            first_name   TEXT    NOT NULL,
            surname      TEXT    NOT NULL,
            mobile       TEXT    NOT NULL,
            dob          TEXT    NOT NULL,
            address      TEXT    NOT NULL,
            city         TEXT    NOT NULL,
            state        TEXT    NOT NULL,
            postcode     TEXT    NOT NULL,
            trail_types  TEXT    DEFAULT '',
            difficulty   TEXT    DEFAULT 'Easy',
            newsletter   INTEGER DEFAULT 0,
            created_at   TEXT    DEFAULT (datetime('now','localtime')),
            updated_at   TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS trail_reviews (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            trail_name TEXT    NOT NULL,
            reviewer   TEXT    NOT NULL,
            rating     INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment    TEXT    NOT NULL,
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        );
        """)
    print("✅  Database initialised →", DB_PATH)

# ── Sanitisation ─────────────────────────────────────────

def clean(s, maxlen=1000):
    if not isinstance(s, str): s = str(s) if s is not None else ""
    return html.escape(s.strip())[:maxlen]

def err(msg, code=400):
    return jsonify({"success": False, "error": msg}), code

# ── Serve static HTML / CSS / JS files ───────────────────

@app.route("/")
def index():
    return send_from_directory("public", "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("public", filename)

# ══════════════════════════════════════════════════════════
# CONTACTS  API
# ══════════════════════════════════════════════════════════

@app.route("/api/contacts", methods=["POST"])
def create_contact():
    data = request.get_json(force=True, silent=True) or {}

    name    = clean(data.get("name", ""))
    email   = clean(data.get("email", ""))
    phone   = clean(data.get("phone", "")).replace(" ", "")
    subject = clean(data.get("subject", "other"))
    message = clean(data.get("message", ""), 2000)

    # ── Validation ──
    errors = []
    if not name:
        errors.append("Name is required.")
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        errors.append("A valid email address is required.")
    if not re.match(r"^\d{7,15}$", phone):
        errors.append("Phone must be 7–15 digits.")
    if len(message) < 10:
        errors.append("Message must be at least 10 characters.")
    if subject not in ("trail", "gear", "membership", "story", "other", ""):
        subject = "other"
    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    try:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO contacts (name, email, phone, subject, message) VALUES (?,?,?,?,?)",
                (name, email, phone, subject or "other", message)
            )
        return jsonify({
            "success": True,
            "message": "Your enquiry has been saved. We will be in touch within 48 hours.",
            "id": cur.lastrowid
        }), 201
    except Exception as ex:
        print("DB error (contacts):", ex)
        return err("Database error. Please try again.", 500)


@app.route("/api/contacts", methods=["GET"])
def list_contacts():
    page    = max(1, int(request.args.get("page",  1)))
    limit   = min(20, int(request.args.get("limit", 5)))
    offset  = (page - 1) * limit
    search  = request.args.get("search", "").strip()
    subject = request.args.get("subject", "").strip()

    like = f"%{search}%" if search else "%"
    where = "WHERE (name LIKE ? OR email LIKE ? OR message LIKE ?)"
    params = [like, like, like]

    if subject:
        where += " AND subject = ?"
        params.append(subject)

    try:
        with get_db() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM contacts {where}", params
            ).fetchone()[0]

            rows = conn.execute(
                f"SELECT id,name,email,phone,subject,message,status,created_at "
                f"FROM contacts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [limit, offset]
            ).fetchall()

        return jsonify({
            "success": True,
            "data": [dict(r) for r in rows],
            "meta": {
                "total": total, "page": page,
                "limit": limit, "pages": max(1, -(-total // limit))
            }
        })
    except Exception as ex:
        print("DB error (contacts list):", ex)
        return err("Database error.", 500)


@app.route("/api/contacts/<int:contact_id>", methods=["DELETE"])
def delete_contact(contact_id):
    try:
        with get_db() as conn:
            info = conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        if info.rowcount == 0:
            return err("Record not found.", 404)
        return jsonify({"success": True, "message": "Enquiry deleted."})
    except Exception as ex:
        return err("Database error.", 500)


@app.route("/api/contacts/<int:contact_id>/status", methods=["PATCH"])
def update_contact_status(contact_id):
    data   = request.get_json(force=True, silent=True) or {}
    status = data.get("status", "")
    if status not in ("new", "read", "resolved"):
        return err("Status must be new, read, or resolved.")
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            info = conn.execute(
                "UPDATE contacts SET status=?, updated_at=? WHERE id=?",
                (status, now, contact_id)
            )
        if info.rowcount == 0:
            return err("Record not found.", 404)
        return jsonify({"success": True})
    except Exception as ex:
        return err("Database error.", 500)

# ══════════════════════════════════════════════════════════
# MEMBERS  API
# ══════════════════════════════════════════════════════════

@app.route("/api/members", methods=["POST"])
def create_member():
    data = request.get_json(force=True, silent=True) or {}

    email      = clean(data.get("email", ""))
    first_name = clean(data.get("first_name", ""))
    surname    = clean(data.get("surname", ""))
    mobile     = clean(data.get("mobile", "")).replace(" ", "")
    dob        = clean(data.get("dob", ""))
    address    = clean(data.get("address", ""))
    city       = clean(data.get("city", ""))
    state      = clean(data.get("state", ""))
    postcode   = clean(data.get("postcode", ""))
    password   = data.get("password", "")
    trail_list = data.get("trail_types", [])
    difficulty = clean(data.get("difficulty", "Easy"))
    newsletter = 1 if data.get("newsletter") else 0

    # ── Validation ──
    errors = []
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        errors.append("A valid email is required.")
    if len(str(password)) < 8:
        errors.append("Password must be at least 8 characters.")
    if not first_name: errors.append("First name is required.")
    if not surname:    errors.append("Surname is required.")
    if not re.match(r"^\d{10}$", mobile):
        errors.append("Mobile must be exactly 10 digits.")
    if not dob:        errors.append("Date of birth is required.")
    if not address:    errors.append("Address is required.")
    if not city:       errors.append("City is required.")
    if not state:      errors.append("State is required.")
    if not re.match(r"^\d{4}$", postcode):
        errors.append("Postcode must be 4 digits.")
    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    trail_csv = ",".join([clean(t) for t in (trail_list if isinstance(trail_list, list) else [])])

    try:
        with get_db() as conn:
            cur = conn.execute(
                """INSERT INTO members
                   (email, first_name, surname, mobile, dob, address,
                    city, state, postcode, trail_types, difficulty, newsletter)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (email, first_name, surname, mobile, dob, address,
                 city, state, postcode, trail_csv, difficulty, newsletter)
            )
        return jsonify({
            "success": True,
            "message": f"Welcome, {first_name}! Your membership is confirmed.",
            "id": cur.lastrowid
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "success": False,
            "error": "An account with this email already exists. Please use a different email."
        }), 409
    except Exception as ex:
        print("DB error (members):", ex)
        return err("Database error. Please try again.", 500)


@app.route("/api/members/count", methods=["GET"])
def member_count():
    try:
        with get_db() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        return jsonify({"success": True, "count": cnt})
    except Exception as ex:
        return err("Database error.", 500)

# ══════════════════════════════════════════════════════════
# TRAIL REVIEWS  API
# ══════════════════════════════════════════════════════════

@app.route("/api/reviews", methods=["POST"])
def create_review():
    data = request.get_json(force=True, silent=True) or {}

    trail_name = clean(data.get("trail_name", ""))
    reviewer   = clean(data.get("reviewer", ""), 80)
    comment    = clean(data.get("comment", ""), 1000)
    try:
        rating = int(data.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0

    errors = []
    if not trail_name:           errors.append("Trail name is required.")
    if not reviewer:             errors.append("Reviewer name is required.")
    if not (1 <= rating <= 5):   errors.append("Rating must be between 1 and 5.")
    if len(comment) < 5:         errors.append("Comment must be at least 5 characters.")
    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    try:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO trail_reviews (trail_name, reviewer, rating, comment) VALUES (?,?,?,?)",
                (trail_name, reviewer, rating, comment)
            )
        return jsonify({
            "success": True,
            "message": "Thank you for your review!",
            "id": cur.lastrowid
        }), 201
    except Exception as ex:
        print("DB error (reviews):", ex)
        return err("Database error. Please try again.", 500)


@app.route("/api/reviews", methods=["GET"])
def list_reviews():
    trail  = request.args.get("trail", "").strip()
    page   = max(1, int(request.args.get("page",  1)))
    limit  = min(10, int(request.args.get("limit", 3)))
    offset = (page - 1) * limit

    where  = "WHERE trail_name = ?" if trail else ""
    params = [trail] if trail else []

    try:
        with get_db() as conn:
            total   = conn.execute(
                f"SELECT COUNT(*) FROM trail_reviews {where}", params
            ).fetchone()[0]
            avg_row = conn.execute(
                f"SELECT AVG(CAST(rating AS REAL)) FROM trail_reviews {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT id, trail_name, reviewer, rating, comment, created_at "
                f"FROM trail_reviews {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [limit, offset]
            ).fetchall()

        avg_val = round(float(avg_row), 1) if avg_row else None
        return jsonify({
            "success": True,
            "data":    [dict(r) for r in rows],
            "avg":     avg_val,
            "meta":    {
                "total": total, "page": page,
                "limit": limit, "pages": max(1, -(-total // limit))
            }
        })
    except Exception as ex:
        print("DB error (reviews list):", ex)
        return err("Database error.", 500)


@app.route("/api/reviews/<int:review_id>", methods=["DELETE"])
def delete_review(review_id):
    try:
        with get_db() as conn:
            info = conn.execute("DELETE FROM trail_reviews WHERE id = ?", (review_id,))
        if info.rowcount == 0:
            return err("Review not found.", 404)
        return jsonify({"success": True})
    except Exception as ex:
        return err("Database error.", 500)

# ── Start ─────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("\n🥾  River Trail Adventures — Task 10.2D")
    print(f"   Server  → http://localhost:3000")
    print(f"   DB      → {DB_PATH}")
    print("   Press Ctrl+C to stop\n")
    app.run(host="127.0.0.1", port=3000, debug=False)
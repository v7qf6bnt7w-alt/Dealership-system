import os
import sqlite3
from functools import wraps
from uuid import uuid4

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "dealer-secret-key-2026"
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DB_PATH = os.path.join(app.root_path, "dealership.db")

ALLOWED_MEDIA_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "mp4", "webm", "ogg", "mov", "m4v"
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            version TEXT NOT NULL,
            year INTEGER,
            mileage INTEGER,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            image_url TEXT,
            description TEXT,
            details TEXT,
            featured INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    vehicle_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(vehicles)").fetchall()
    }
    if "year" not in vehicle_columns:
        db.execute("ALTER TABLE vehicles ADD COLUMN year INTEGER")
    if "mileage" not in vehicle_columns:
        db.execute("ALTER TABLE vehicles ADD COLUMN mileage INTEGER")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            request_type TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            message TEXT,
            wants_test_drive INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'New',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicle_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('image', 'video')),
            media_url TEXT NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            UNIQUE(vehicle_id, kind, media_url)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER NOT NULL,
            name TEXT NOT NULL COLLATE NOCASE,
            UNIQUE(brand_id, name),
            FOREIGN KEY(brand_id) REFERENCES catalog_brands(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            name TEXT NOT NULL COLLATE NOCASE,
            UNIQUE(model_id, name),
            FOREIGN KEY(model_id) REFERENCES catalog_models(id) ON DELETE CASCADE
        )
        """
    )

    # Keep the supplied car catalogue intact and make its values searchable.
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'car_catalogue_2000_present'"
    ).fetchone():
        catalog_rows = db.execute(
            """
            SELECT DISTINCT TRIM(Brand), TRIM(Model), TRIM(Version_Trim)
            FROM car_catalogue_2000_present
            WHERE TRIM(COALESCE(Brand, '')) != ''
            """
        ).fetchall()
        for brand_name, model_name, version_name in catalog_rows:
            _ensure_catalog_entry(db, brand_name, model_name, version_name)

    # Migrate the original single-image field without losing existing images.
    for old_vehicle in db.execute(
        "SELECT id, image_url FROM vehicles WHERE COALESCE(image_url, '') != ''"
    ).fetchall():
        db.execute(
            "INSERT OR IGNORE INTO vehicle_media (vehicle_id, kind, media_url, is_primary) VALUES (?, 'image', ?, 1)",
            (old_vehicle["id"], old_vehicle["image_url"]),
        )

    admin_exists = db.execute("SELECT 1 FROM users WHERE username = 'admin' LIMIT 1").fetchone()
    if not admin_exists:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("admin", "admin123"),
        )

    vehicle_count = db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    if vehicle_count == 0:
        sample_vehicles = [
            (
                "Toyota",
                "Corolla",
                "Hybrid",
                "Toyota Corolla Hybrid",
                26500,
                7,
                "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?auto=format&fit=crop&w=1200&q=80",
                "Efficient, modern and ideal for daily driving.",
                "Hybrid, automatic, LED, backup camera, adaptive cruise",
                1,
            ),
            (
                "Ford",
                "Mustang",
                "GT",
                "Ford Mustang GT",
                42000,
                3,
                "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=1200&q=80",
                "High-performance coupe built for excitement and style.",
                "V8, sport package, leather interior, digital display",
                1,
            ),
            (
                "BMW",
                "Series 5",
                "Luxury",
                "BMW 530i",
                50500,
                2,
                "https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&w=1200&q=80",
                "Executive comfort with premium technology and design.",
                "Navigation, panoramic roof, premium sound, assisted driving",
                1,
            ),
            (
                "Mercedes",
                "GLE",
                "Premium",
                "Mercedes-Benz GLE 350",
                61000,
                4,
                "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?auto=format&fit=crop&w=1200&q=80",
                "Luxury SUV with spacious comfort and power.",
                "4MATIC, leather seats, driver assistance, ambient lighting",
                0,
            ),
        ]

        db.executemany(
            """
            INSERT INTO vehicles (brand, model, version, name, price, stock, image_url, description, details, featured)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sample_vehicles,
        )

    db.commit()


def _ensure_catalog_entry(db, brand, model="", version=""):
    brand = (brand or "").strip()
    model = (model or "").strip()
    version = (version or "").strip()
    if not brand:
        return

    db.execute("INSERT OR IGNORE INTO catalog_brands (name) VALUES (?)", (brand,))
    brand_id = db.execute(
        "SELECT id FROM catalog_brands WHERE name = ? COLLATE NOCASE", (brand,)
    ).fetchone()["id"]
    if not model:
        return

    db.execute(
        "INSERT OR IGNORE INTO catalog_models (brand_id, name) VALUES (?, ?)",
        (brand_id, model),
    )
    model_id = db.execute(
        "SELECT id FROM catalog_models WHERE brand_id = ? AND name = ? COLLATE NOCASE",
        (brand_id, model),
    ).fetchone()["id"]
    if version:
        db.execute(
            "INSERT OR IGNORE INTO catalog_versions (model_id, name) VALUES (?, ?)",
            (model_id, version),
        )


def get_catalog_options(option_type, brand="", model=""):
    db = get_db()
    if option_type == "brand":
        rows = db.execute("SELECT name AS value FROM catalog_brands ORDER BY name COLLATE NOCASE").fetchall()
    elif option_type == "model":
        rows = db.execute(
            """
            SELECT m.name AS value FROM catalog_models m
            JOIN catalog_brands b ON b.id = m.brand_id
            WHERE b.name = ? COLLATE NOCASE ORDER BY m.name COLLATE NOCASE
            """,
            (brand,),
        ).fetchall()
    elif option_type == "version":
        rows = db.execute(
            """
            SELECT v.name AS value FROM catalog_versions v
            JOIN catalog_models m ON m.id = v.model_id
            JOIN catalog_brands b ON b.id = m.brand_id
            WHERE b.name = ? COLLATE NOCASE AND m.name = ? COLLATE NOCASE
            ORDER BY v.name COLLATE NOCASE
            """,
            (brand, model),
        ).fetchall()
    else:
        return []
    return [row["value"] for row in rows]


def save_uploaded_media(file):
    if not file or not file.filename:
        return None
    safe_name = secure_filename(file.filename)
    if not safe_name or "." not in safe_name:
        return None
    extension = safe_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_MEDIA_EXTENSIONS:
        flash(f"Skipped unsupported media file: {safe_name}.", "warning")
        return None
    filename = f"{uuid4().hex}.{extension}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return filename, "image" if extension in {"jpg", "jpeg", "png", "gif", "webp"} else "video"


def get_vehicle_media(vehicle_id):
    media = get_db().execute(
        "SELECT * FROM vehicle_media WHERE vehicle_id = ? ORDER BY is_primary DESC, id ASC",
        (vehicle_id,),
    ).fetchall()
    result = [
        {
            **dict(item),
            "url": item["media_url"] if item["media_url"].startswith("http") else url_for("uploaded_file", filename=item["media_url"]),
        }
        for item in media
    ]
    if not result:
        legacy = get_db().execute("SELECT image_url FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
        if legacy and legacy["image_url"]:
            image_url = legacy["image_url"]
            result.append({
                "id": None,
                "vehicle_id": vehicle_id,
                "kind": "image",
                "media_url": image_url,
                "is_primary": 1,
                "url": image_url if image_url.startswith("http") else url_for("uploaded_file", filename=image_url),
            })
    return result


def vehicle_with_primary_media(vehicle):
    item = dict(vehicle)
    media = get_vehicle_media(item["id"])
    primary_image = next((entry for entry in media if entry["kind"] == "image"), None)
    if primary_image:
        item["image_url"] = primary_image["media_url"]
    return item


def store_vehicle_media(db, vehicle_id, image_url, previous_image_url="", uploaded_files=(), remove_ids=()):
    removed_files = []
    if remove_ids:
        placeholders = ",".join("?" for _ in remove_ids)
        rows = db.execute(
            f"SELECT media_url FROM vehicle_media WHERE vehicle_id = ? AND id IN ({placeholders})",
            [vehicle_id, *remove_ids],
        ).fetchall()
        removed_files = [row["media_url"] for row in rows]
        db.execute(
            f"DELETE FROM vehicle_media WHERE vehicle_id = ? AND id IN ({placeholders})",
            [vehicle_id, *remove_ids],
        )

    if image_url and image_url != previous_image_url:
        db.execute("UPDATE vehicle_media SET is_primary = 0 WHERE vehicle_id = ?", (vehicle_id,))
        db.execute(
            "INSERT OR IGNORE INTO vehicle_media (vehicle_id, kind, media_url, is_primary) VALUES (?, 'image', ?, 1)",
            (vehicle_id, image_url),
        )
        db.execute(
            "UPDATE vehicle_media SET is_primary = 1 WHERE vehicle_id = ? AND kind = 'image' AND media_url = ?",
            (vehicle_id, image_url),
        )

    has_primary_image = db.execute(
        "SELECT 1 FROM vehicle_media WHERE vehicle_id = ? AND kind = 'image' AND is_primary = 1 LIMIT 1",
        (vehicle_id,),
    ).fetchone() is not None
    for media_file in uploaded_files:
        saved = save_uploaded_media(media_file)
        if not saved:
            continue
        filename, kind = saved
        is_primary = int(kind == "image" and not has_primary_image)
        db.execute(
            "INSERT OR IGNORE INTO vehicle_media (vehicle_id, kind, media_url, is_primary) VALUES (?, ?, ?, ?)",
            (vehicle_id, kind, filename, is_primary),
        )
        if is_primary:
            has_primary_image = True
            if not image_url:
                image_url = filename

    if not has_primary_image:
        db.execute(
            "UPDATE vehicle_media SET is_primary = 1 WHERE id = (SELECT id FROM vehicle_media WHERE vehicle_id = ? AND kind = 'image' ORDER BY id LIMIT 1)",
            (vehicle_id,),
        )
    if previous_image_url and previous_image_url in removed_files and image_url == previous_image_url:
        remaining_image = db.execute(
            "SELECT media_url FROM vehicle_media WHERE vehicle_id = ? AND kind = 'image' ORDER BY is_primary DESC, id LIMIT 1",
            (vehicle_id,),
        ).fetchone()
        image_url = remaining_image["media_url"] if remaining_image else ""

    for media_url in removed_files:
        if not media_url.startswith("http") and os.path.basename(media_url) == media_url:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], media_url)
            if os.path.isfile(file_path):
                os.remove(file_path)
    return image_url


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please login to access the administrator panel.", "warning")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def parse_vehicle_filters():
    brand = request.args.get("brand", "").strip()
    model = request.args.get("model", "").strip()
    version = request.args.get("version", "").strip()
    search = request.args.get("search", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    sort = request.args.get("sort", "newest")

    return {
        "brand": brand,
        "model": model,
        "version": version,
        "search": search,
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort,
    }


def build_vehicle_query(filters):
    query = "SELECT * FROM vehicles WHERE 1 = 1"
    params = []

    if filters["brand"]:
        query += " AND brand = ?"
        params.append(filters["brand"])
    if filters["model"]:
        query += " AND model = ?"
        params.append(filters["model"])
    if filters["version"]:
        query += " AND version = ?"
        params.append(filters["version"])
    if filters["search"]:
        query += " AND (name LIKE ? OR brand LIKE ? OR model LIKE ? OR description LIKE ? OR details LIKE ?)"
        search_term = f"%{filters['search']}%"
        params.extend([search_term, search_term, search_term, search_term, search_term])
    if filters["min_price"]:
        query += " AND price >= ?"
        params.append(float(filters["min_price"]))
    if filters["max_price"]:
        query += " AND price <= ?"
        params.append(float(filters["max_price"]))

    if filters["sort"] == "price_asc":
        query += " ORDER BY price ASC"
    elif filters["sort"] == "price_desc":
        query += " ORDER BY price DESC"
    elif filters["sort"] == "brand":
        query += " ORDER BY brand ASC, model ASC"
    else:
        query += " ORDER BY created_at DESC"

    return query, params


def get_vehicle_image(vehicle):
    images = [item for item in get_vehicle_media(vehicle["id"]) if item["kind"] == "image"]
    image_url = images[0]["media_url"] if images else vehicle["image_url"]
    image_url = image_url or "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=1200&q=80"
    if isinstance(image_url, str) and image_url.startswith("http"):
        return image_url
    return url_for("uploaded_file", filename=image_url)


@app.route("/")
def index():
    filters = parse_vehicle_filters()
    db = get_db()
    vehicles = db.execute(*build_vehicle_query(filters)).fetchall()

    featured = db.execute("SELECT * FROM vehicles WHERE featured = 1 ORDER BY created_at DESC LIMIT 5").fetchall()
    if not featured:
        featured = db.execute("SELECT * FROM vehicles ORDER BY created_at DESC LIMIT 5").fetchall()

    brand_options = get_catalog_options("brand")
    model_options = {
        brand: get_catalog_options("model", brand=brand)
        for brand in brand_options
    }
    version_options = [
        row["name"] for row in db.execute(
            "SELECT DISTINCT name FROM catalog_versions ORDER BY name COLLATE NOCASE"
        ).fetchall()
    ]

    return render_template(
        "index.html",
        vehicles=[vehicle_with_primary_media(vehicle) for vehicle in vehicles],
        featured=[vehicle_with_primary_media(vehicle) for vehicle in featured],
        filters=filters,
        brands=brand_options,
        brand_options=brand_options,
        model_options=model_options,
        version_options=version_options,
    )


@app.route("/vehicle/<int:vehicle_id>")
def vehicle_detail(vehicle_id):
    db = get_db()
    vehicle = db.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not vehicle:
        flash("Vehicle not found.", "danger")
        return redirect(url_for("index"))

    return render_template(
        "vehicle_detail.html",
        vehicle=vehicle,
        image_url=get_vehicle_image(vehicle),
        media=get_vehicle_media(vehicle_id),
    )


@app.route("/request-info/<int:vehicle_id>", methods=["POST"])
def request_info(vehicle_id):
    db = get_db()
    vehicle = db.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not vehicle:
        return jsonify({"success": False, "message": "Vehicle was not found."}), 404

    form = request.form
    first_name = form.get("first_name", "").strip()
    last_name = form.get("last_name", "").strip()
    email = form.get("email", "").strip()
    phone = form.get("phone", "").strip()
    message = form.get("message", "").strip()
    request_type = form.get("request_type", "information")
    wants_test_drive = 1 if form.get("wants_test_drive") == "yes" else 0

    if not first_name or not last_name or not email or not phone:
        return jsonify({"success": False, "message": "Please complete the required fields."}), 400

    db.execute(
        """
        INSERT INTO requests (vehicle_id, request_type, first_name, last_name, email, phone, message, wants_test_drive)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vehicle_id,
            request_type,
            first_name,
            last_name,
            email,
            phone,
            message,
            wants_test_drive,
        ),
    )
    db.commit()

    return jsonify({"success": True, "message": f"Your {request_type} request has been submitted successfully."})


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND password_hash = ?",
            (username, password),
        ).fetchone()

        if user:
            session["admin_logged_in"] = True
            session["admin_username"] = username
            flash("Login successful.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password.", "danger")
        return render_template("admin_login.html")

    return render_template("admin_login.html")


@app.route("/admin-logout")
def admin_logout():
    session.clear()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    vehicles = db.execute("SELECT * FROM vehicles ORDER BY created_at DESC").fetchall()
    requests = db.execute("SELECT * FROM requests ORDER BY created_at DESC LIMIT 10").fetchall()
    return render_template("admin_dashboard.html", vehicles=vehicles, requests=requests)


@app.route("/admin/vehicles")
@login_required
def admin_vehicles():
    db = get_db()
    vehicles = db.execute("SELECT * FROM vehicles ORDER BY created_at DESC").fetchall()
    return render_template(
        "admin_vehicles.html",
        vehicles=[vehicle_with_primary_media(vehicle) for vehicle in vehicles],
    )


@app.route("/admin/catalog/options")
@login_required
def admin_catalog_options():
    option_type = request.args.get("type", "")
    brand = request.args.get("brand", "").strip()
    model = request.args.get("model", "").strip()
    if option_type not in {"brand", "model", "version"}:
        return jsonify({"options": []}), 400
    if option_type in {"model", "version"} and not brand:
        return jsonify({"options": []})
    if option_type == "version" and not model:
        return jsonify({"options": []})
    return jsonify({"options": get_catalog_options(option_type, brand, model)})


@app.route("/admin/catalog/add", methods=["POST"])
@login_required
def admin_add_catalog_value():
    data = request.get_json(silent=True) or {}
    option_type = data.get("type", "")
    value = str(data.get("value", "")).strip()
    brand = str(data.get("brand", "")).strip()
    model = str(data.get("model", "")).strip()
    if option_type not in {"brand", "model", "version"} or not value:
        return jsonify({"success": False, "message": "Enter a valid catalog value."}), 400
    if option_type in {"model", "version"} and not brand:
        return jsonify({"success": False, "message": "Add or select a brand first."}), 400
    if option_type == "version" and not model:
        return jsonify({"success": False, "message": "Add or select a model first."}), 400

    db = get_db()
    _ensure_catalog_entry(
        db,
        value if option_type == "brand" else brand,
        value if option_type == "model" else model,
        value if option_type == "version" else "",
    )
    db.commit()
    return jsonify({"success": True, "message": f"{value} is saved for future vehicles."})


@app.route("/admin/vehicle/new", methods=["GET", "POST"])
@login_required
def admin_new_vehicle():
    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        version = request.form.get("version", "").strip()
        year_value = request.form.get("year", "").strip()
        mileage_value = request.form.get("mileage", "").strip()
        year = int(year_value) if year_value else None
        mileage = int(mileage_value) if mileage_value else None
        name = request.form.get("name", "").strip() or f"{brand} {model} {version}"
        price = float(request.form.get("price", 0) or 0)
        stock = int(request.form.get("stock", 0) or 0)
        description = request.form.get("description", "").strip()
        details = request.form.get("details", "").strip()
        featured = 1 if request.form.get("featured") == "on" else 0

        image_url = request.form.get("image_url", "").strip()

        db = get_db()
        _ensure_catalog_entry(db, brand, model, version)
        db.execute(
            """
            INSERT INTO vehicles (brand, model, version, year, mileage, name, price, stock, image_url, description, details, featured)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                brand,
                model,
                version,
                year,
                mileage,
                name,
                price,
                stock,
                image_url,
                description,
                details,
                featured,
            ),
        )
        vehicle_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        image_url = store_vehicle_media(
            db,
            vehicle_id,
            image_url,
            uploaded_files=request.files.getlist("media_files"),
        )
        db.execute("UPDATE vehicles SET image_url = ? WHERE id = ?", (image_url, vehicle_id))
        db.commit()
        flash("Vehicle created successfully.", "success")
        return redirect(url_for("admin_vehicles"))

    return render_template("admin_vehicle_form.html", vehicle=None, action="new", media=[])


@app.route("/admin/vehicle/<int:vehicle_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_vehicle(vehicle_id):
    db = get_db()
    vehicle = db.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not vehicle:
        flash("Vehicle not found.", "danger")
        return redirect(url_for("admin_vehicles"))

    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        version = request.form.get("version", "").strip()
        year_value = request.form.get("year", "").strip()
        mileage_value = request.form.get("mileage", "").strip()
        year = int(year_value) if year_value else None
        mileage = int(mileage_value) if mileage_value else None
        name = request.form.get("name", "").strip() or f"{brand} {model} {version}"
        price = float(request.form.get("price", 0) or 0)
        stock = int(request.form.get("stock", 0) or 0)
        description = request.form.get("description", "").strip()
        details = request.form.get("details", "").strip()
        featured = 1 if request.form.get("featured") == "on" else 0

        image_url = request.form.get("image_url", vehicle["image_url"] or "").strip()

        _ensure_catalog_entry(db, brand, model, version)
        db.execute(
            """
            UPDATE vehicles
            SET brand = ?, model = ?, version = ?, year = ?, mileage = ?, name = ?, price = ?, stock = ?, image_url = ?, description = ?, details = ?, featured = ?
            WHERE id = ?
            """,
            (
                brand,
                model,
                version,
                year,
                mileage,
                name,
                price,
                stock,
                image_url,
                description,
                details,
                featured,
                vehicle_id,
            ),
        )
        image_url = store_vehicle_media(
            db,
            vehicle_id,
            image_url,
            previous_image_url=vehicle["image_url"] or "",
            uploaded_files=request.files.getlist("media_files"),
            remove_ids=request.form.getlist("remove_media"),
        )
        db.execute("UPDATE vehicles SET image_url = ? WHERE id = ?", (image_url, vehicle_id))
        db.commit()
        flash("Vehicle updated successfully.", "success")
        return redirect(url_for("admin_vehicles"))

    return render_template(
        "admin_vehicle_form.html",
        vehicle=vehicle,
        action="edit",
        media=get_vehicle_media(vehicle_id),
    )


@app.route("/admin/vehicle/<int:vehicle_id>/delete", methods=["POST"])
@login_required
def admin_delete_vehicle(vehicle_id):
    db = get_db()
    media_rows = db.execute(
        "SELECT media_url FROM vehicle_media WHERE vehicle_id = ?", (vehicle_id,)
    ).fetchall()
    db.execute("DELETE FROM requests WHERE vehicle_id = ?", (vehicle_id,))
    db.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
    db.commit()
    for row in media_rows:
        media_url = row["media_url"]
        if not media_url.startswith("http") and os.path.basename(media_url) == media_url:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], media_url)
            if os.path.isfile(file_path):
                os.remove(file_path)
    flash("Vehicle deleted successfully.", "success")
    return redirect(url_for("admin_vehicles"))


@app.route("/admin/vehicle/<int:vehicle_id>/stock", methods=["POST"])
@login_required
def admin_update_stock(vehicle_id):
    db = get_db()
    vehicle = db.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not vehicle:
        flash("Vehicle not found.", "danger")
        return redirect(url_for("admin_vehicles"))

    delta = int(request.form.get("delta", 0) or 0)
    new_stock = max(0, int(vehicle["stock"]) + delta)
    db.execute("UPDATE vehicles SET stock = ? WHERE id = ?", (new_stock, vehicle_id))
    db.commit()

    if new_stock == 0:
        flash(f"{vehicle['name']} stock reached zero and is now marked as unavailable.", "warning")
    else:
        flash(f"Stock updated for {vehicle['name']}.", "success")
    return redirect(url_for("admin_vehicles"))


@app.route("/admin/requests")
@login_required
def admin_requests():
    db = get_db()
    requests = db.execute("SELECT * FROM requests ORDER BY created_at DESC").fetchall()
    return render_template("admin_requests.html", requests=requests)


@app.route("/admin/request/<int:request_id>/update", methods=["POST"])
@login_required
def admin_update_request(request_id):
    db = get_db()
    status = request.form.get("status", "New").strip()
    notes = request.form.get("notes", "").strip()

    db.execute(
        "UPDATE requests SET status = ?, notes = ? WHERE id = ?",
        (status, notes, request_id),
    )
    db.commit()
    flash("Request status updated successfully.", "success")
    return redirect(url_for("admin_requests"))


@app.route("/admin/request/<int:request_id>/delete", methods=["POST"])
@login_required
def admin_delete_request(request_id):
    db = get_db()
    db.execute("DELETE FROM requests WHERE id = ?", (request_id,))
    db.commit()
    flash("Request deleted successfully.", "success")
    return redirect(url_for("admin_requests"))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

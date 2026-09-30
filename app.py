import os
import secrets
import shutil
import uuid
from datetime import date, datetime
from functools import wraps
from decimal import Decimal, InvalidOperation

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, abort, send_from_directory)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()  # reads .env locally; on Railway the real env vars are used

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SEED_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")  # images shipped with the code
# On Railway, point UPLOAD_DIR at a mounted volume so uploads survive redeploys
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", SEED_UPLOAD_DIR)
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
# SQLite locally; set DATABASE_URL (e.g. mysql+pymysql://...) in production
db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'gallery.db')}")
if db_url.startswith("mysql://"):
    db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Avoid "MySQL server has gone away" after idle periods
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 280}
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB uploads

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

db = SQLAlchemy(app)


# ---------------------------------------------------------------- models
class Drawing(db.Model):
    __tablename__ = "drawings"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    picture = db.Column(db.String(255), nullable=False)  # filename in static/uploads
    published_date = db.Column(db.Date, nullable=False, default=date.today)
    description = db.Column(db.Text, nullable=False, default="")


class Order(db.Model):
    __tablename__ = "orders"
    STATUSES = ["new", "in discussion", "accepted", "in progress", "completed", "declined"]

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    initial_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="new")
    admin_notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


# ---------------------------------------------------------------- helpers
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def save_upload(file_storage):
    ext = secure_filename(file_storage.filename).rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, filename))
    return filename


def delete_upload(filename):
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(path):
        os.remove(path)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get("_csrf")
        if not token or token != request.form.get("_csrf"):
            abort(400, "Invalid form token. Please refresh and try again.")


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.context_processor
def inject_year():
    return {"current_year": date.today().year}


# ---------------------------------------------------------------- public
@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    # Serves drawings from UPLOAD_DIR (the Railway volume in production)
    return send_from_directory(UPLOAD_DIR, filename, max_age=86400)


@app.route("/")
def home():
    featured = Drawing.query.order_by(Drawing.published_date.desc()).limit(3).all()
    return render_template("home.html", featured=featured)


@app.route("/gallery")
def gallery():
    drawings = Drawing.query.order_by(Drawing.published_date.desc()).all()
    return render_template("gallery.html", drawings=drawings)


@app.route("/gallery/<int:drawing_id>")
def drawing_detail(drawing_id):
    drawing = db.get_or_404(Drawing, drawing_id)
    others = (Drawing.query.filter(Drawing.id != drawing_id)
              .order_by(Drawing.published_date.desc()).limit(3).all())
    return render_template("drawing_detail.html", drawing=drawing, others=others)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/commission", methods=["GET", "POST"])
def commission():
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ("first_name", "last_name", "phone", "email", "description", "initial_price")}
        errors = []
        for key, label in [("first_name", "First name"), ("last_name", "Last name"),
                           ("phone", "Phone number"), ("email", "Email"),
                           ("description", "Description"), ("initial_price", "Initial price")]:
            if not form[key]:
                errors.append(f"{label} is required.")
        if form["email"] and "@" not in form["email"]:
            errors.append("Please enter a valid email address.")
        price = None
        if form["initial_price"]:
            try:
                price = Decimal(form["initial_price"])
                if price <= 0:
                    errors.append("Initial price must be greater than 0.")
            except InvalidOperation:
                errors.append("Initial price must be a number.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db.session.add(Order(first_name=form["first_name"], last_name=form["last_name"],
                                 phone=form["phone"], email=form["email"],
                                 description=form["description"], initial_price=price))
            db.session.commit()
            flash("Thank you! Your request has been sent. Hara will reach out to you soon.", "success")
            return redirect(url_for("commission"))
    return render_template("commission.html", form=form)


# ---------------------------------------------------------------- admin
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if (secrets.compare_digest(request.form.get("username", ""), ADMIN_USERNAME) and
                secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD)):
            session["is_admin"] = True
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/admin") else url_for("admin_dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = {
        "drawings": Drawing.query.count(),
        "orders": Order.query.count(),
        "new_orders": Order.query.filter_by(status="new").count(),
    }
    recent = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats, recent=recent)


@app.route("/admin/drawings")
@admin_required
def admin_drawings():
    drawings = Drawing.query.order_by(Drawing.published_date.desc()).all()
    return render_template("admin/drawings.html", drawings=drawings)


@app.route("/admin/drawings/new", methods=["GET", "POST"])
@app.route("/admin/drawings/<int:drawing_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_drawing_form(drawing_id=None):
    drawing = db.get_or_404(Drawing, drawing_id) if drawing_id else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        pub = request.form.get("published_date", "")
        picture = request.files.get("picture")

        errors = []
        if not name:
            errors.append("Name is required.")
        try:
            pub_date = datetime.strptime(pub, "%Y-%m-%d").date() if pub else date.today()
        except ValueError:
            errors.append("Invalid date.")
            pub_date = date.today()
        has_new_pic = picture and picture.filename
        if has_new_pic and not allowed_file(picture.filename):
            errors.append("Picture must be PNG, JPG, WEBP or GIF.")
        if not drawing and not has_new_pic:
            errors.append("A picture is required.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/drawing_form.html", drawing=drawing, form=request.form)

        if drawing is None:
            drawing = Drawing(picture=save_upload(picture))
            db.session.add(drawing)
        elif has_new_pic:
            old = drawing.picture
            drawing.picture = save_upload(picture)
            delete_upload(old)
        drawing.name = name
        drawing.description = description
        drawing.published_date = pub_date
        db.session.commit()
        flash(f"“{drawing.name}” saved.", "success")
        return redirect(url_for("admin_drawings"))
    return render_template("admin/drawing_form.html", drawing=drawing, form=None)


@app.route("/admin/drawings/<int:drawing_id>/delete", methods=["POST"])
@admin_required
def admin_drawing_delete(drawing_id):
    drawing = db.get_or_404(Drawing, drawing_id)
    delete_upload(drawing.picture)
    db.session.delete(drawing)
    db.session.commit()
    flash("Drawing deleted.", "success")
    return redirect(url_for("admin_drawings"))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    status = request.args.get("status", "")
    q = Order.query
    if status in Order.STATUSES:
        q = q.filter_by(status=status)
    orders = q.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders,
                           statuses=Order.STATUSES, current=status)


@app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
@admin_required
def admin_order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    if request.method == "POST":
        status = request.form.get("status")
        if status in Order.STATUSES:
            order.status = status
        order.admin_notes = request.form.get("admin_notes", "").strip()
        db.session.commit()
        flash("Order updated.", "success")
        return redirect(url_for("admin_order_detail", order_id=order.id))
    return render_template("admin/order_detail.html", order=order, statuses=Order.STATUSES)


@app.route("/admin/orders/<int:order_id>/delete", methods=["POST"])
@admin_required
def admin_order_delete(order_id):
    order = db.get_or_404(Order, order_id)
    db.session.delete(order)
    db.session.commit()
    flash("Order deleted.", "success")
    return redirect(url_for("admin_orders"))


# ---------------------------------------------------------------- setup
def seed():
    if Drawing.query.count():
        return
    db.session.add_all([
        Drawing(name="Lemons & Fig", picture="lemons-and-fig.jpg",
                published_date=date(2026, 9, 20),
                description="An oil pastel still life: two sunlit lemons and a halved fig "
                            "resting on a warm table, set against a deep brown backdrop. "
                            "Layered strokes build the glow of the fruit and the soft shadows around it."),
        Drawing(name="Lemon Study", picture="lemon-study.jpg",
                published_date=date(2026, 9, 12),
                description="A lighter oil pastel study of two lemons and their leaves on white paper, "
                            "focusing on texture, highlight and cast shadow."),
        Drawing(name="Coming Soon", picture="placeholder.svg",
                published_date=date(2026, 9, 1),
                description="A new piece is on the way. Check back soon."),
    ])
    db.session.commit()


with app.app_context():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # Copy the bundled starter images into the volume (only the missing ones)
    if os.path.abspath(UPLOAD_DIR) != os.path.abspath(SEED_UPLOAD_DIR):
        for fname in os.listdir(SEED_UPLOAD_DIR):
            dest = os.path.join(UPLOAD_DIR, fname)
            if not os.path.exists(dest):
                shutil.copy2(os.path.join(SEED_UPLOAD_DIR, fname), dest)
    db.create_all()
    seed()


if __name__ == "__main__":
    app.run(debug=True)
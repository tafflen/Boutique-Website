from flask import Flask, render_template, request, redirect, flash, session, url_for
from flask_wtf.csrf import CSRFProtect
from functools import wraps
import mysql.connector
import bcrypt
import os
from werkzeug.utils import secure_filename  # sanitizes filenames
import google.generativeai as genai
app = Flask(__name__)
csrf = CSRFProtect(app)

# ─────────────────────────────────────────
# GEMINI API CONFIG
# ─────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "I'LL PUT MY KEY AFTER CREATING THE .ENV FILE")
genai.configure(api_key=GEMINI_API_KEY) 

# Create the model instance once at startup
# gemini-1.5-flash is fast and free-tier friendly
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

# ─────────────────────────────────────────
# SECRET KEY — move to environment variable
# os.environ.get() reads from your system environment
# If not found, falls back to the hardcoded string (for local dev)
# On production (Render/Railway), set this as an env variable
# ─────────────────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "boutique@#xK92!mPqL77zRt")

# ─────────────────────────────────────────
# FILE UPLOAD CONFIG
# ─────────────────────────────────────────
csrf = CSRFProtect(app)

# Folder where uploaded images will be saved
UPLOAD_FOLDER = os.path.join('static', 'uploads')

# Only these file types are allowed — security measure
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# Max file size — 5MB (5 * 1024 * 1024 bytes)
MAX_CONTENT_LENGTH = 5 * 1024 * 1024

app.config['UPLOAD_FOLDER']      = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  

def sanitize(text, max_length=200):
    """
    Cleans user input before saving to DB or displaying.
    
    strip()     → removes leading/trailing spaces
    max_length  → prevents storing huge strings (DoS protection)
    
    We do NOT use escape() here because Jinja2 auto-escapes
    output in templates — double-escaping would show &amp; etc.
    Just strip and truncate is enough for input sanitization.
    """
    if not text:
        return ""
    return text.strip()[:max_length]

# ─────────────────────────────────────────
# DB HELPER — fresh connection every time
# Prevents "MySQL server has gone away" crash
# ─────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",    
        password="12345",
        database="boutique"
    )

# ─────────────────────────────────────────
# HELPER — check if file extension is allowed
# ─────────────────────────────────────────
def allowed_file(filename):
    # filename = "product.jpg"
    # filename.rsplit('.', 1) = ["product", "jpg"]
    # [1] = "jpg"
    # .lower() = "jpg"
    # check if "jpg" is in ALLOWED_EXTENSIONS
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    SELECT id, name, category, price, stock, image
    FROM products
    ORDER BY id DESC
    LIMIT 4
""")

    featured_products = cursor.fetchall()

    cursor.close()
    db.close()
    return render_template("index1.html",featured_products=featured_products)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contactBoutique")
def contact():
    return render_template("contactBoutique.html")

# ─────────────────────────────────────────────────────────────────────────────
# DECORATORS — reusable route protection
# ─────────────────────────────────────────────────────────────────────────────

def login_required(f):
    """
    Use this decorator on any route that needs a logged-in user.
    Replaces the manual: if not session.get("user"): redirect("/login")

    @login_required          ← add this line above any route function
    def my_route():
        ...

    How it works:
    1. Browser requests the route
    2. login_required runs FIRST
    3. If session has "user" → calls your route function normally
    4. If not → redirects to login page immediately
    """
    @wraps(f)
    # @wraps preserves the original function's name and docstring
    # Without it, all decorated routes would appear as "wrapper" in Flask
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            flash("Please login to continue.", "error")
            return redirect(url_for("handle_login"))
        return f(*args, **kwargs)   # call the actual route function
    return wrapper


def admin_required(f):
    """
    Use this decorator on any admin-only route.
    ALWAYS stack it BELOW @login_required — login is checked first.

    @login_required     ← checked first
    @admin_required     ← checked second
    def admin_route():
        ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("is_admin") != 1:
            flash("Access denied. Admins only.", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapper

# ─────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def handle_login():
    if session.get("user"):          # already logged in → home
        return redirect("/")

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"].encode('utf-8')

        db = get_db()
        cursor = db.cursor(buffered=True)
        cursor.execute("SELECT password , is_admin FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        db.close()

        # Generic message — never reveal which field failed (security best practice)
        if result and bcrypt.checkpw(password, result[0].encode('utf-8')):
            session["user"] = username
            session["is_admin"] = result[1]  # Store admin status in session
            flash("Login successful", "success")
            # return redirect("/")
            if result[1] == 1:
                return redirect("/admin")
            else:
                return redirect("/")
        else:
            flash("Invalid username or password.", "error")
            return redirect("/login")

    return render_template("login.html")


# ─────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "success")
    return redirect("/")


# ─────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].encode('utf-8')

        db = get_db()
        cursor = db.cursor(buffered=True)

        # Check for duplicate username
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash("Username already taken. Please choose another.", "error")
            cursor.close()
            db.close()
            return redirect("/register")

        # Hash password — bcrypt adds salt automatically
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hashed_password)
        )
        db.commit()
        cursor.close()
        db.close()

        flash("Account created successfully! Please login.", "success")
        return redirect("/login")

    return render_template("register.html")


# ─────────────────────────────────────────
# ADMIN DASHBOARD — protected route
# Only accessible if logged in AND is admin
# ─────────────────────────────────────────
@app.route("/admin")
@login_required
@admin_required  
def admin_dashboard():

    # # Check 1 — is the user logged in at all?
    # if not session.get("user"):
    #     flash("Please login to continue.", "error")
    #     return redirect("/login")

    #   # Use session instead of querying DB again
    # if session.get("is_admin") != 1:
    #     # flash("Access denied. Admins only.", "error")
    #     return redirect("/")

    # return render_template("admin/dashboard.html")

    db = get_db()
    cursor = db.cursor(buffered=True)

    # Count total products
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]  # fetchone() returns tuple → [0] gets the number

    # Count total users (excluding admins)
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 0")
    total_users = cursor.fetchone()[0]

    cursor.close()
    db.close()

    return render_template("admin/dashboard.html",
                           total_products=total_products,
                           total_users=total_users)

@app.route("/admin/products")
@login_required
@admin_required
def admin_products():

    # # Protection — not logged in
    # if not session.get("user"):
    #     flash("Please login to continue.", "error")
    #     return redirect("/login")

    # # Protection — not admin
    # if session.get("is_admin") != 1:
    #     flash("Access denied. Admins only.", "error")
    #     return redirect("/")

    db = get_db()
    cursor = db.cursor(buffered=True)

    # Fetch all products from database
    cursor.execute("SELECT id, name, category, price, stock,image FROM products")
    products = cursor.fetchall()   # fetchall() returns list of tuples
    # Example: [(1, 'Silk Saree', 'Sarees', 1299.00, 10), (2, ...)]

    cursor.close()
    db.close()

    return render_template("admin/products.html", products=products)

# ─────────────────────────────────────────
# ADD PRODUCT — GET shows form, POST saves it
# ─────────────────────────────────────────
@app.route("/admin/products/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_product():

    # # Protection
    # if not session.get("user"):
    #     flash("Please login to continue.", "error")
    #     return redirect("/login")

    # if session.get("is_admin") != 1:
    #     flash("Access denied. Admins only.", "error")
    #     return redirect("/")

    if request.method == "POST":

        # ── Step 1: Get text fields
        name        = sanitize(request.form.get("name",        ""), 200)
        description = sanitize(request.form.get("description", ""), 1000)
        category    = sanitize(request.form.get("category",    ""), 100)
        price       = request.form.get("price", "").strip()
        stock       = request.form.get("stock", "").strip()

        # ── Step 2: Get uploaded file
        # request.files is separate from request.form
        # request.form  → text fields
        # request.files → file fields
        image_file = request.files.get("image")

        # ── Step 3: Validate text fields
        errors = []

        if not name:
            errors.append("Product name is required.")
        if not price:
            errors.append("Price is required.")
        if not stock:
            errors.append("Stock quantity is required.")
        if not category:
            errors.append("Please select a category.")

        try:
            price = float(price)
            if price < 0:
                errors.append("Price cannot be negative.")
        except ValueError:
            errors.append("Price must be a valid number.")

        try:
            stock = int(stock)
            if stock < 0:
                errors.append("Stock cannot be negative.")
        except ValueError:
            errors.append("Stock must be a whole number.")

        # ── Step 4: Handle image upload
        image_filename = None  # default — no image

        if image_file and image_file.filename != '':
            # image_file.filename != '' means user actually selected a file

            if allowed_file(image_file.filename):
                # secure_filename removes dangerous characters from filename
                # "My Product!!.jpg" → "My_Product__.jpg"
                filename = secure_filename(image_file.filename)

                # Build full path: static/uploads/filename.jpg
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                # Actually save the file to disk
                image_file.save(save_path)

                # Store just the filename in DB — not the full path
                image_filename = filename

            else:
                errors.append("Image must be JPG, PNG, or WEBP format.")

        # ── Step 5: If errors → stop and show them
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("admin/add_product.html")

        # ── Step 6: Insert into database
        db = get_db()
        cursor = db.cursor(buffered=True)

        cursor.execute(
            "INSERT INTO products (name, description, category, price, stock, image) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, description, category, price, stock, image_filename)
        )
        db.commit()
        cursor.close()
        db.close()

        flash(f"'{name}' added successfully!", "success")
        return redirect("/admin/products")

    return render_template("admin/add_product.html")


# ─────────────────────────────────────────────
# EDIT PRODUCT  — GET: show form  |  POST: save changes
# ─────────────────────────────────────────────
@app.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_product(product_id):
    # Block non-admins immediately
    if session.get("is_admin") != 1:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)  # dictionary=True → rows come back as dicts

    if request.method == "POST":
        # ── Collect form values ──────────────────────────────────────────
        name        = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category    = request.form.get("category", "").strip()
        price       = request.form.get("price", "0").strip()
        stock       = request.form.get("stock", "0").strip()

        # ── Basic validation ─────────────────────────────────────────────
        if not name or not price or not stock:
            flash("Name, price, and stock are required.", "danger")
            return redirect(f"/admin/products/edit/{product_id}")

        # ── Check if a NEW image was uploaded ────────────────────────────
        file = request.files.get("image")          # None if no file chosen
        new_filename = None                        # We'll fill this if needed

        if file and file.filename != "":           # User selected a new image
            if allowed_file(file.filename):
                new_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], new_filename))
            else:
                flash("Invalid image type. Use PNG, JPG, GIF, or WEBP.", "danger")
                return redirect(f"/admin/products/edit/{product_id}")

        # ── Build the SQL query based on whether image was changed ────────
        if new_filename:
            # Image WAS changed → update everything including image column
            sql = """
                UPDATE products
                SET name=%s, description=%s, category=%s,
                    price=%s, stock=%s, image=%s
                WHERE id=%s
            """
            values = (name, description, category, price, stock,
                      new_filename, product_id)
        else:
            # Image was NOT changed → update everything EXCEPT image column
            sql = """
                UPDATE products
                SET name=%s, description=%s, category=%s,
                    price=%s, stock=%s
                WHERE id=%s
            """
            values = (name, description, category, price, stock, product_id)

        cursor.execute(sql, values)
        db.commit()                                # Save changes to database

        flash("Product updated successfully!", "success")
        return redirect("/admin/products")         # Back to product list

    # ── GET request: load existing product data into the form ────────────
    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()                    # One row as a dictionary

    if not product:                                # Safety: ID doesn't exist
        flash("Product not found.", "danger")
        return redirect("/admin/products")

    return render_template("admin/edit_product.html", product=product)


# ─────────────────────────────────────────────
# DELETE PRODUCT  — POST only (never allow GET deletes)
# ─────────────────────────────────────────────
@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    # Block non-admins immediately
    if session.get("is_admin") != 1:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
    db.commit()

    flash("Product deleted.", "warning")
    return redirect("/admin/products")


# ─────────────────────────────────────────
# SHOP PAGE — customer facing
# Shows all products from database
# ─────────────────────────────────────────
@app.route("/shop")
def shop():
    db = get_db()
    cursor = db.cursor(buffered=True)

    # Check if a category filter was passed in the URL
    # /shop?category=Sarees → category = "Sarees"
    # /shop → category = None
    category = request.args.get("category")

    if category:
        # Filter by specific category
        cursor.execute("""
            SELECT id, name, category, price, stock, image, description
            FROM products
            WHERE category = %s
            ORDER BY created_at DESC
        """, (category,))
    else:
        # No filter → show all products
        cursor.execute("""
            SELECT id, name, category, price, stock, image, description
            FROM products
            ORDER BY created_at DESC
        """)
    # ORDER BY created_at DESC → newest products appear first
    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("shop.html", products=products, selected_category=category)


# ─────────────────────────────────────────
# PRODUCT DETAIL PAGE
# Shows full info of one specific product
# ─────────────────────────────────────────
@app.route("/product/<int:product_id>")
def product_detail(product_id):
    # <int:product_id> → Flask converts the URL number to an integer
    # /product/3 → product_id = 3

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, price, stock, image, description
        FROM products
        WHERE id = %s
    """, (product_id,))
    # (product_id,) → tuple with one value — comma is required!

    product = cursor.fetchone()
    # cursor.close()
    # db.close()

    # If product doesn't exist → show 404 page
    if not product:
        flash("Product not found.", "error")
        return redirect("/shop")

    cursor.execute("""SELECT id, name, price, image FROM products 
      WHERE category = %s
      AND id != %s
      ORDER BY created_at DESC
      LIMIT 4""", (product["category"], product_id))
    related = cursor.fetchall()

    cursor.close()
    db.close()
    category = request.args.get("category", "")

    return render_template("product_detail.html", product=product, related=related, category=category)

# ─────────────────────────────────────────
# CART — session based
# cart structure stored in session:
# session["cart"] = {
#   "3": {"name": "Glow Serum", "price": 499.0, "qty": 2, "image": "glow.jpg"},
#   "7": {"name": "Rose Toner", "price": 299.0, "qty": 1, "image": "toner.jpg"}
# }
# Key is product_id as STRING (session keys must be strings)
# ─────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# CART ROUTES  
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    """
    Handles adding a product to the session cart.
    Accepts POST data: product_id, quantity (optional, defaults to 1)
    Works from BOTH shop.html and product_detail.html
    """

    # ----- 1. Read form data -----
    # request.form is a dict-like object containing all POST fields
    product_id = request.form.get("product_id")      # comes as a string from HTML
    # int() converts "2" → 2; we default to 1 if qty field is missing
    quantity   = int(request.form.get("quantity", 1))

    # ----- 2. Validate product_id -----
    if not product_id:
        # Someone called this URL without a product_id — ignore
        flash("Invalid product.", "danger")
        return redirect(url_for("shop"))

    # ----- 3. Fetch product from DB -----
    # We need name, price, image to store in the cart dict
    db = get_db()
    cursor = db.cursor(dictionary=True)   # returns rows as dicts
    cursor.execute(
        "SELECT id, name, price, stock, image FROM products WHERE id = %s",
        (product_id,)                     # always use parameterized queries!
    )
    product = cursor.fetchone()           # returns None if not found
    cursor.close()
    db.close()

    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("shop"))

    # ----- 4. Check stock -----
    if product["stock"] < 1:
        flash(f"Sorry, {product['name']} is out of stock.", "warning")
        return redirect(request.referrer or url_for("shop"))
        # request.referrer = the URL the user came FROM (shop page or detail page)
        # fallback to shop if referrer is None

    # ----- 5. Initialize cart if it doesn't exist yet -----
    if "cart" not in session:
        session["cart"] = {}
        # session is a dict managed by Flask; it persists across requests
        # for the same browser session via a signed cookie

    # ----- 6. str(product_id) — critical! -----
    # JSON (used internally by Flask sessions) only allows string keys
    pid = str(product["id"])

    # ----- 7. Add or update quantity -----
    if pid in session["cart"]:
        # Product already in cart → just increase quantity
        new_qty = session["cart"][pid]["qty"] + quantity

        # Don't let quantity exceed stock
        if new_qty > product["stock"]:
            new_qty = product["stock"]
            flash(f"Only {product['stock']} units available. Quantity capped.", "warning")
        
        session["cart"][pid]["qty"] = new_qty
    else:
        # New product → add it with all required fields
        session["cart"][pid] = {
            "name"  : product["name"],
            "price" : float(product["price"]),  # store as float for math later
            "qty"   : quantity,
            "image" : product["image"] or "default.jpg"  # fallback image
        }

    # ----- 8. IMPORTANT: tell Flask the session was modified -----
    # Flask only saves the session to cookie if it detects a change.
    # Modifying a nested dict (session["cart"][pid]["qty"]) does NOT
    # automatically trigger save — you must set this flag manually.
    session.modified = True

    flash(f"'{product['name']}' added to cart!", "success")

    # ----- 9. POST-Redirect-GET: redirect back to where user came from -----
    return redirect(request.referrer or url_for("shop"))


# ─────────────────────────────────────────────────────────────────────────────

@app.route("/update-cart", methods=["POST"])
def update_cart():
    """
    Updates the quantity of an existing cart item.
    Called from the cart page via a small form next to each item.
    """
    product_id = str(request.form.get("product_id", ""))
    # int() with a try/except handles bad input like "abc"
    try:
        new_qty = int(request.form.get("quantity", 1))
    except ValueError:
        flash("Invalid quantity.", "danger")
        return redirect(url_for("cart"))

    # Ignore if cart doesn't exist or product not in cart
    if "cart" not in session or product_id not in session["cart"]:
        flash("Item not found in cart.", "warning")
        return redirect(url_for("cart"))

    if new_qty < 1:
        # If qty goes to 0 or below, treat it as a remove
        session["cart"].pop(product_id)
        flash("Item removed from cart.", "info")
    else:
        # Optional: validate against stock
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT stock FROM products WHERE id = %s", (product_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if row and new_qty > row["stock"]:
            new_qty = row["stock"]
            flash(f"Quantity capped at available stock ({row['stock']}).", "warning")

        session["cart"][product_id]["qty"] = new_qty
        flash("Cart updated.", "success")

    session.modified = True  # never forget this!
    return redirect(url_for("cart"))


# ─────────────────────────────────────────────────────────────────────────────

@app.route("/remove-from-cart", methods=["POST"])
def remove_from_cart():
    """
    Removes a single item from the cart completely.
    """
    product_id = str(request.form.get("product_id", ""))

    if "cart" in session and product_id in session["cart"]:
        item_name = session["cart"][product_id]["name"]   # save name before deleting
        session["cart"].pop(product_id)                   # dict.pop() removes the key
        session.modified = True
        flash(f"'{item_name}' removed from cart.", "info")
    else:
        flash("Item not found in cart.", "warning")

    return redirect(url_for("cart"))


# ─────────────────────────────────────────────────────────────────────────────

@app.route("/cart")
def cart():
    """
    Displays the cart page.
    Calculates subtotal, tax, and total server-side for accuracy.
    """
    cart_items = session.get("cart", {})
    # cart_items is a dict: { "3": {"name": ..., "price": ..., "qty": ..., "image": ...} }

    # Calculate totals here in Python (not JavaScript) so they're trustworthy
    subtotal = sum(
        item["price"] * item["qty"]
        for item in cart_items.values()   # .values() gives us each item dict
    )

    # Simple tax calculation (18% GST — adjust for your region)
    tax_rate = 0.18
    tax      = round(subtotal * tax_rate, 2)
    total    = round(subtotal + tax, 2)

    # item_count used for the navbar badge
    item_count = sum(item["qty"] for item in cart_items.values())

    return render_template(
        "cart.html",
        cart_items = cart_items,
        subtotal   = round(subtotal, 2),
        tax        = tax,
        total      = total,
        item_count = item_count
    )

# TEMPORARY DEBUG ROUTE — paste this in app.py, remove after fixing
@app.route("/debug-cart")
def debug_cart():
    # This shows you EXACTLY what's in the session right now
    # If cart is empty here, session is not saving at all
    # If cart has items here, the problem is in cart.html display
    import json
    return f"""
    <h2>Session Debug</h2>
    <p><b>Session cart:</b> {session.get('cart', 'EMPTY — nothing saved')}</p>
    <p><b>Session keys:</b> {list(session.keys())}</p>
    <p><b>Secret key set:</b> {bool(app.secret_key)}</p>
    <pre>{json.dumps(session.get('cart', {}), indent=2)}</pre>
    """

@app.route("/clear-cart", methods=["POST"])
def clear_cart():
    """
    Wipes the entire cart in one click.
    Used by 'Empty Cart' button on cart page.
    """
    session.pop("cart", None)   # safely removes cart key; no error if missing
    session.modified = True
    flash("Your cart has been cleared.", "info")
    return redirect(url_for("cart"))

# ─────────────────────────────────────────────────────────────────────────────
# CHECKOUT — GET: show form | POST: validate + save order
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/checkout", methods=["GET", "POST"])
@login_required 
def checkout():
    """
    GET  → Show address form to the customer
    POST → Validate inputs, save order to DB, clear cart, redirect to confirmation
    """

    # # ── Must be logged in ─────────────────────────────────────────────
    # if not session.get("user"):
    #     flash("Please login to place an order.", "error")
    #     return redirect("/login")

    # ── Cart must have items ──────────────────────────────────────────
    cart_items = session.get("cart", {})
    if not cart_items:
        flash("Your cart is empty.", "warning")
        return redirect("/shop")

    # ── Calculate totals (same logic as cart route) ───────────────────
    subtotal = sum(item["price"] * item["qty"] for item in cart_items.values())
    tax      = round(subtotal * 0.18, 2)
    total    = round(subtotal + tax, 2)

    if request.method == "POST":

        # ── Step 1: Read form fields ──────────────────────────────────
        name    = sanitize(request.form.get("name",    ""), 100)
        phone   = sanitize(request.form.get("phone",   ""), 15)
        address = sanitize(request.form.get("address", ""), 300)
        city    = sanitize(request.form.get("city",    ""), 100)
        pincode = sanitize(request.form.get("pincode", ""), 10)
        # ── Step 2: Validate every field ──────────────────────────────
        errors = []

        if not name:
            errors.append("Full name is required.")

        if not phone or not phone.isdigit() or len(phone) != 10:
            errors.append("Enter a valid 10-digit phone number.")

        if not address:
            errors.append("Delivery address is required.")

        if not city:
            errors.append("City is required.")

        if not pincode or not pincode.isdigit() or len(pincode) != 6:
            errors.append("Enter a valid 6-digit pincode.")

        # ── Step 3: If errors → show them, don't save anything ────────
        if errors:
            for e in errors:
                flash(e, "error")
            # Re-render form WITH totals so summary still shows
            return render_template("checkout.html",
                                   subtotal=subtotal, tax=tax, total=total)

        # ── Step 4: Save order to DB ──────────────────────────────────
        db     = get_db()
        cursor = db.cursor()

        # Insert one row into orders table
        cursor.execute("""
            INSERT INTO orders
                (user, name, phone, address, city, pincode,
                 subtotal, tax, total, payment_id, order_status)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'paid')
        """, (
            session["user"],   # logged-in username
            name,
            phone,
            address,
            city,
            pincode,
            subtotal,
            tax,
            total,
            "SIMULATED_PAYMENT"   # placeholder — real payment ID goes here later
        ))

        # cursor.lastrowid = the auto-generated id of the row just inserted
        # We need this to link order_items to this specific order
        order_db_id = cursor.lastrowid

        # ── Step 5: Save each cart item into order_items ──────────────
        # One row per product — this is how we remember what was ordered
        for pid, item in cart_items.items():
            cursor.execute("""
                INSERT INTO order_items
                    (order_id, product_id, product_name, quantity, price)
                VALUES
                    (%s, %s, %s, %s, %s)
            """, (
                order_db_id,    # links back to the orders row
                int(pid),       # product id (convert from string key)
                item["name"],   # snapshot of name at purchase time
                item["qty"],
                item["price"]   # snapshot of price at purchase time
            ))

        # db.commit() saves ALL the inserts above in one transaction
        # If anything fails, nothing gets saved (atomicity)
        db.commit()
        cursor.close()
        db.close()

        # ── Step 6: Clear the cart from session ───────────────────────
        session.pop("cart", None)
        session.modified = True

        flash("🎉 Order placed successfully!", "success")
        return redirect(f"/order-confirmation/{order_db_id}")

    # GET request → just show the empty form
    return render_template("checkout.html",
                           subtotal=subtotal, tax=tax, total=total)


# ─────────────────────────────────────────────────────────────────────────────
# ORDER CONFIRMATION
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/order-confirmation/<int:order_id>")
@login_required 
def order_confirmation(order_id):
    """
    Shows thank-you page after successful order.
    Fetches order + items from DB to display summary.
    """

    if not session.get("user"):
        return redirect("/login")

    db     = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch the order — also check it belongs to this user (security)
    cursor.execute("""
        SELECT * FROM orders
        WHERE id = %s AND user = %s
    """, (order_id, session["user"]))
    order = cursor.fetchone()

    if not order:
        flash("Order not found.", "error")
        return redirect("/shop")

    # Fetch all items belonging to this order
    cursor.execute("""
        SELECT product_name, quantity, price,
               (quantity * price) AS line_total
        FROM order_items
        WHERE order_id = %s
    """, (order_id,))
    items = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("order_confirmation.html", order=order, items=items)

# ─────────────────────────────────────────────────────────────────────────────
# AI CHATBOT ROUTE
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
@csrf.exempt 
def chat():
    """
    Receives a message from the chat widget via AJAX (fetch API).
    Sends it to Gemini with conversation history and system context.
    Returns a JSON response — NOT a full HTML page.

    Why JSON? The chat widget updates the page dynamically using
    JavaScript without a full page reload. This is called AJAX.
    """

    # ── Read the user's message from the POST body ────────────────────
    # request.get_json() parses the JSON body sent by fetch() in JS
    data    = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return {"reply": "Please type a message."}, 400

    # ── Initialize chat history in session if first message ──────────
    # History format Gemini expects:
    # [{"role": "user", "parts": ["hello"]},
    #  {"role": "model", "parts": ["hi there!"]}]
    if "chat_history" not in session:
        session["chat_history"] = []

    # ── Build system context — fetch products from DB ─────────────────
    # This gives Gemini real knowledge of YOUR products
    try:
        db     = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT name, category, price, stock FROM products LIMIT 20")
        products = cursor.fetchall()
        cursor.close()
        db.close()

        # Format products as a readable list for the prompt
        product_list = "\n".join([
            f"- {p['name']} ({p['category']}) — ₹{p['price']} — "
            f"{'In stock' if p['stock'] > 0 else 'Out of stock'}"
            for p in products
        ])
    except Exception:
        product_list = "Product information temporarily unavailable."

    # ── System prompt — defines Gemini's personality ──────────────────
    # This is prepended to every conversation so Gemini stays in context
    system_prompt = f"""
    You are Elshaddai Boutique's AI Shopping Assistant.

    Your role:
    - Help customers shop for women's fashion.
    - Answer questions about products, sizes, colors, styling, matching accessories, fabrics, and availability.
    - Recommend products only from the boutique's inventory.

    Current products:
    {product_list}

    STRICT RESPONSE RULES:
    - NEVER write long paragraphs.
    - Keep every reply between 30 and 80 words.
    - Use at most 3 short sentences.
    - If listing options, give only the top 3 recommendations.
    - Avoid detailed explanations unless the customer explicitly asks for more.
    - Be friendly, warm, and conversational.
    - Mention prices only when recommending a product.
    - If a product is unavailable, suggest similar available products.
    - Never invent products not listed above.
    - If the question is unrelated to fashion or shopping, politely redirect the conversation back to the boutique.

    Examples:

    Customer: What accessories suit a red saree?

    Assistant:
    Gold jewelry, pearl accessories, or a black clutch pair beautifully with a red saree. For weddings, gold is the most elegant choice. Would you like suggestions for matching footwear too?

    Customer: Do you have cotton kurtis?

    Assistant:
    Yes! We currently have these cotton kurtis:
    • Floral Cotton Kurti – ₹899
    • Printed Cotton Kurti – ₹1099
    Which style are you looking for?

    Customer: Tell me everything about sarees.

    Assistant:
    We have several sarees in different fabrics and colors. Let me know if you prefer cotton, silk, party wear, or bridal sarees, and I'll recommend the best options.
    """

    # ── Build full conversation for Gemini ────────────────────────────
    # We send: system prompt + history + new message
    # Gemini sees the full context every time
    history = session["chat_history"]

    try:
        # Start a chat with existing history
        chat_session = gemini_model.start_chat(history=history)

        # Send system prompt + user message together on first message,
        # or just user message on subsequent messages
        if len(history) == 0:
            full_message = f"{system_prompt}\n\nCustomer: {message}"
        else:
            full_message = message

        response = chat_session.send_message(full_message)
        reply    = response.text

    except Exception as e:
        # Graceful fallback — never show raw errors to users
        reply = "Sorry, I'm having trouble connecting right now. Please try again in a moment."
        print(f"Gemini error: {e}")   # log to terminal for debugging

    # ── Save updated history to session ──────────────────────────────
    session["chat_history"].append({
        "role" : "user",
        "parts": [message]    # save original message, not the system-prefixed one
    })
    session["chat_history"].append({
        "role" : "model",
        "parts": [reply]
    })

    # Keep history to last 10 exchanges (20 messages) to avoid huge cookies
    # Slice from the end to keep most recent messages
    if len(session["chat_history"]) > 20:
        session["chat_history"] = session["chat_history"][-20:]

    session.modified = True

    # ── Return JSON to the JavaScript fetch() call ────────────────────
    # jsonify() converts a Python dict to a proper JSON HTTP response
    from flask import jsonify
    return jsonify({"reply": reply})


# ─────────────────────────────────────────
# CLEAR CHAT HISTORY
# ─────────────────────────────────────────
@app.route("/clear-chat", methods=["POST"])
@csrf.exempt
def clear_chat():
    """Wipes chat history from session. Called by the 'Clear' button."""
    session.pop("chat_history", None)
    session.modified = True
    return {"status": "cleared"}, 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
    
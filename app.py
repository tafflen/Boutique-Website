from flask import Flask, render_template, request, redirect, flash, session
import mysql.connector
import bcrypt
import os

app = Flask(__name__)
app.secret_key = 'boutique@#xK92!mPqL77zRt'  # Strong secret key

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


@app.route("/")
def home():
    return render_template("index1.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contactBoutique")
def contact():
    return render_template("contactBoutique.html")


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
def admin_dashboard():

    # Check 1 — is the user logged in at all?
    if not session.get("user"):
        flash("Please login to continue.", "error")
        return redirect("/login")

      # Use session instead of querying DB again
    if session.get("is_admin") != 1:
        # flash("Access denied. Admins only.", "error")
        return redirect("/")

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
def admin_products():

    # Protection — not logged in
    if not session.get("user"):
        flash("Please login to continue.", "error")
        return redirect("/login")

    # Protection — not admin
    if session.get("is_admin") != 1:
        flash("Access denied. Admins only.", "error")
        return redirect("/")

    db = get_db()
    cursor = db.cursor(buffered=True)

    # Fetch all products from database
    cursor.execute("SELECT id, name, category, price, stock FROM products")
    products = cursor.fetchall()   # fetchall() returns list of tuples
    # Example: [(1, 'Silk Saree', 'Sarees', 1299.00, 10), (2, ...)]

    cursor.close()
    db.close()

    return render_template("admin/products.html", products=products)

# ─────────────────────────────────────────
# ADD PRODUCT — GET shows form, POST saves it
# ─────────────────────────────────────────
@app.route("/admin/products/add", methods=["GET", "POST"])
def add_product():

    # Protection — not logged in
    if not session.get("user"):
        flash("Please login to continue.", "error")
        return redirect("/login")

    # Protection — not admin
    if session.get("is_admin") != 1:
        flash("Access denied. Admins only.", "error")
        return redirect("/")

    if request.method == "POST":

        # ── Step 1: Get form data
        name        = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category    = request.form.get("category", "").strip()
        price       = request.form.get("price", "").strip()
        stock       = request.form.get("stock", "").strip()

        # ── Step 2: Validate — check nothing important is empty
        errors = []

        if not name:
            errors.append("Product name is required.")

        if not price:
            errors.append("Price is required.")

        if not stock:
            errors.append("Stock quantity is required.")

        if not category:
            errors.append("Please select a category.")

        # ── Step 3: Validate price and stock are valid numbers
        try:
            price = float(price)   # converts "1299" → 1299.0
            if price < 0:
                errors.append("Price cannot be negative.")
        except ValueError:
            # ValueError fires if price contains letters like "abc"
            errors.append("Price must be a valid number.")

        try:
            stock = int(stock)     # converts "10" → 10
            if stock < 0:
                errors.append("Stock cannot be negative.")
        except ValueError:
            errors.append("Stock must be a whole number.")

        # ── Step 4: If any errors → show them, keep form filled
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("admin/add_product.html")

        # ── Step 5: All valid → INSERT into database
        db = get_db()
        cursor = db.cursor(buffered=True)

        cursor.execute(
            "INSERT INTO products (name, description, category, price, stock) VALUES (%s, %s, %s, %s, %s)",
            (name, description, category, price, stock)
        )
        db.commit()   # ← save changes permanently
        cursor.close()
        db.close()

        flash(f"'{name}' added successfully!", "success")
        return redirect("/admin/products")  # ← go back to product list

    # GET request → just show the empty form
    return render_template("admin/add_product.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
    
from flask import Flask, render_template, request
import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="12345",  
    database="boutique"
)

cursor = db.cursor()
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index1.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contactBoutique")
def contact():
    return render_template("contactBoutique.html")

# @app.route("/login")
# def login():
#     return render_template("login.html")

@app.route("/login",methods=["GET","POST"])
def handle_login():
    if request.method == "POST":
        username=request.form["username"]
        password=request.form["password"]
        return f"Username:{username}, Password:{password}"
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        query = "INSERT INTO users (username, password) VALUES (%s, %s)"
        values = (username, password)

        cursor.execute(query, values)
        db.commit()

        return "User Registered Successfully"

    return render_template("register.html")

if __name__ == "__main__":  
    app.run(debug=True)


import random
import sqlite3
from pathlib import Path
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, g, abort
)

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret-key"

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "bank.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")

    db.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_number TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            gender TEXT NOT NULL,
            age INTEGER NOT NULL,
            dob TEXT NOT NULL,
            mobile TEXT NOT NULL,
            account_type TEXT NOT NULL
                CHECK(account_type IN ('Current', 'Saving')),
            balance REAL NOT NULL CHECK(balance >= 0),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT NOT NULL,
            loan_type TEXT NOT NULL,
            amount REAL NOT NULL,
            annual_income REAL NOT NULL,
            years INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(account_number)
                REFERENCES accounts(account_number)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_account TEXT,
            to_account TEXT,
            amount REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    db.commit()
    db.close()


def generate_account_number():
    db = get_db()
    while True:
        number = str(random.randint(100000000000, 999999999999))
        exists = db.execute(
            "SELECT 1 FROM accounts WHERE account_number = ?",
            (number,)
        ).fetchone()
        if not exists:
            return number


@app.template_filter("money")
def money(value):
    return f"₹{float(value):,.2f}"


@app.template_filter("datetime_format")
def datetime_format(value):
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y, %I:%M %p")
    except (ValueError, TypeError):
        return value


@app.route("/")
def index():
    db = get_db()

    stats = {
        "accounts": db.execute(
            "SELECT COUNT(*) FROM accounts"
        ).fetchone()[0],
        "customers": db.execute(
            "SELECT COUNT(*) FROM accounts"
        ).fetchone()[0],
        "balance": db.execute(
            "SELECT COALESCE(SUM(balance), 0) FROM accounts"
        ).fetchone()[0],
        "loans": db.execute(
            "SELECT COUNT(*) FROM loans"
        ).fetchone()[0],
    }

    recent = db.execute("""
        SELECT * FROM transactions
        ORDER BY id DESC LIMIT 5
    """).fetchall()

    return render_template("index.html", stats=stats, recent=recent)


@app.route("/create-account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        try:
            name = request.form["name"].strip()
            gender = request.form["gender"]
            age = int(request.form["age"])
            dob = request.form["dob"]
            mobile = request.form["mobile"].strip()
            account_type = request.form["account_type"]
            balance = float(request.form["balance"])

            if not name or len(name) > 100:
                raise ValueError("Enter a valid customer name.")

            if gender not in ("Male", "Female", "Other"):
                raise ValueError("Select a valid gender.")

            if age < 18 or age > 120:
                raise ValueError("The customer must be at least 18 years old.")

            datetime.strptime(dob, "%Y-%m-%d")

            if len(mobile) != 10 or not mobile.isdigit():
                raise ValueError("Enter a valid 10-digit mobile number.")

            if account_type not in ("Current", "Saving"):
                raise ValueError("Select a valid account type.")

            minimum = 5000 if account_type == "Current" else 1000

            if balance < minimum:
                raise ValueError(
                    f"Minimum initial balance for {account_type} "
                    f"Account is ₹{minimum:,.0f}."
                )

            if balance > 100000000:
                raise ValueError("Initial deposit exceeds the demo limit.")

            account_number = generate_account_number()
            db = get_db()

            db.execute("""
                INSERT INTO accounts (
                    account_number, name, gender, age, dob,
                    mobile, account_type, balance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_number, name, gender, age, dob,
                mobile, account_type, balance,
                datetime.now().isoformat(timespec="seconds")
            ))
            db.commit()

            flash(
                f"Account created successfully! Account number: "
                f"{account_number}", "success"
            )
            return redirect(url_for(
                "customer_details", account_number=account_number
            ))

        except (ValueError, KeyError) as error:
            flash(str(error) or "Please check the entered information.", "error")
        except sqlite3.Error:
            flash("Could not save the account. Please try again.", "error")

    return render_template("create_account.html")


@app.route("/customers")
def customers():
    db = get_db()
    search = request.args.get("q", "").strip()

    if search:
        rows = db.execute("""
            SELECT * FROM accounts
            WHERE name LIKE ? OR account_number LIKE ? OR mobile LIKE ?
            ORDER BY created_at DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        rows = db.execute("""
            SELECT * FROM accounts ORDER BY created_at DESC
        """).fetchall()

    return render_template("customers.html", customers=rows, search=search)


@app.route("/customer/<account_number>")
def customer_details(account_number):
    db = get_db()
    customer = db.execute(
        "SELECT * FROM accounts WHERE account_number = ?",
        (account_number,)
    ).fetchone()

    if customer is None:
        abort(404)

    loans = db.execute("""
        SELECT * FROM loans WHERE account_number = ? ORDER BY id DESC
    """, (account_number,)).fetchall()

    transactions = db.execute("""
        SELECT * FROM transactions
        WHERE from_account = ? OR to_account = ?
        ORDER BY id DESC LIMIT 20
    """, (account_number, account_number)).fetchall()

    return render_template(
        "customer_details.html",
        customer=customer,
        loans=loans,
        transactions=transactions
    )


@app.route("/apply-loan", methods=["GET", "POST"])
def apply_loan():
    loan_types = ["Home Loan", "Car Loan", "Education Loan",
                  "Agricultural Loan"]

    if request.method == "POST":
        try:
            account_number = request.form["account_number"].strip()
            loan_type = request.form["loan_type"]
            amount = float(request.form["amount"])
            income = float(request.form["annual_income"])
            years = int(request.form["years"])

            if loan_type not in loan_types:
                raise ValueError("Select a valid loan type.")

            if amount <= 0 or amount > 100000000:
                raise ValueError("Enter a valid loan amount.")

            if income <= 0 or income > 100000000:
                raise ValueError("Enter a valid annual income.")

            if not 1 <= years <= 30:
                raise ValueError("Loan duration must be 1–30 years.")

            db = get_db()
            account = db.execute(
                "SELECT * FROM accounts WHERE account_number = ?",
                (account_number,)
            ).fetchone()

            if account is None:
                raise ValueError("Account number not found.")

            # Simplified educational eligibility estimate, not bank policy.
            monthly_payment_estimate = amount / (years * 12)
            monthly_income = income / 12
            eligible = monthly_payment_estimate <= monthly_income * 0.5
            status = "Eligible - Review Required" if eligible else "Not Eligible"

            db.execute("""
                INSERT INTO loans (
                    account_number, loan_type, amount, annual_income,
                    years, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                account_number, loan_type, amount, income,
                years, status, datetime.now().isoformat(timespec="seconds")
            ))
            db.commit()

            flash(
                f"Loan assessment: {status}. This is only a demo estimate.",
                "success" if eligible else "error"
            )
            return redirect(url_for(
                "customer_details", account_number=account_number
            ))

        except (ValueError, KeyError) as error:
            flash(str(error) or "Please check the loan form.", "error")
        except sqlite3.Error:
            flash("Could not save the loan application.", "error")

    return render_template("apply_loan.html", loan_types=loan_types)


@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if request.method == "POST":
        try:
            sender = request.form["from_account"].strip()
            receiver = request.form["to_account"].strip()
            amount = round(float(request.form["amount"]), 2)

            if sender == receiver:
                raise ValueError("Sender and receiver must be different.")

            if amount <= 0 or amount > 10000000:
                raise ValueError("Enter a valid transfer amount.")

            db = get_db()
            db.execute("BEGIN IMMEDIATE")

            source = db.execute(
                "SELECT * FROM accounts WHERE account_number = ?",
                (sender,)
            ).fetchone()

            destination = db.execute(
                "SELECT * FROM accounts WHERE account_number = ?",
                (receiver,)
            ).fetchone()

            if source is None or destination is None:
                raise ValueError("Sender or receiver account was not found.")

            if source["balance"] < amount:
                raise ValueError("Insufficient account balance.")

            db.execute(
                "UPDATE accounts SET balance = balance - ? "
                "WHERE account_number = ?", (amount, sender)
            )
            db.execute(
                "UPDATE accounts SET balance = balance + ? "
                "WHERE account_number = ?", (amount, receiver)
            )

            now = datetime.now().isoformat(timespec="seconds")
            db.execute("""
                INSERT INTO transactions (
                    from_account, to_account, amount,
                    transaction_type, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (sender, receiver, amount, "Transfer", now))

            db.commit()
            flash("Demo transfer completed successfully.", "success")
            return redirect(url_for(
                "customer_details", account_number=sender
            ))

        except (ValueError, KeyError) as error:
            if "db" in g:
                g.db.rollback()
            flash(str(error) or "Please check transfer details.", "error")
        except sqlite3.Error:
            if "db" in g:
                g.db.rollback()
            flash("Transfer failed. Please try again.", "error")

    return render_template("transfer.html")


@app.errorhandler(404)
def not_found(error):
    return render_template("base.html", page_error="Page or account not found."), 404


init_db()

if __name__ == "__main__":
    app.run(debug=True)

import math
import os
import socket
from datetime import datetime, timezone

import pymongo
from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient, ReadPreference
from pymongo.errors import PyMongoError

app = Flask(__name__)

# Connection string comes only from the environment (no hosts or passwords in code).
# serverSelectionTimeoutMS=5000: during a PRIMARY election a write waits up to 5 s for the new
# PRIMARY instead of failing at once (retryable writes then resend it once).
client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000, tz_aware=True)
calculations = client.get_default_database()["calculations"]

APP_VERSION = os.environ.get("APP_VERSION", "1.0")          # set at build time (Dockerfile ARG)
POD_NAME = os.environ.get("HOSTNAME", socket.gethostname())
try:
    POD_IP = os.environ.get("POD_IP") or socket.gethostbyname(socket.gethostname())
except OSError:
    POD_IP = "unknown"

LIMITS = {"principal": 1e12, "rate": 100, "months": 1200}   # upper bounds keep (1+r)^n finite


def positive(value, upper):
    """Return value as a float in (0, upper], or None if it is not valid."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 < number <= upper else None


@app.get("/")
def index():
    return render_template("index.html", version=APP_VERSION)


@app.post("/api/emi")
def emi():
    data = request.get_json(force=True, silent=True) or request.form
    p = positive(data.get("principal"), LIMITS["principal"])
    rate = positive(data.get("rate"), LIMITS["rate"])
    n = positive(data.get("months"), LIMITS["months"])
    if p is None or rate is None or n is None or n != int(n):
        return jsonify(error="Loan amount, interest rate and months must be positive numbers "
                             "(rate up to 100%, months a whole number up to 1200)."), 400

    n = int(n)
    r = rate / 12 / 100                                      # monthly interest rate
    monthly = p * r * (1 + r) ** n / ((1 + r) ** n - 1)
    total = monthly * n

    try:
        calculations.insert_one({
            "principal": p, "rate": rate, "months": n, "emi": round(monthly, 2),
            "servedBy": POD_NAME, "createdAt": datetime.now(timezone.utc),
        })
    except PyMongoError as e:
        app.logger.error("insert failed: %s", e)
        return jsonify(error="Database unavailable, please try again.", servedBy=POD_NAME), 503

    return jsonify(emi=round(monthly, 2), totalPayment=round(total, 2),
                   totalInterest=round(total - p, 2), servedBy=POD_NAME, podIP=POD_IP,
                   version=APP_VERSION)


@app.get("/api/history")
def history():
    try:
        rows = list(calculations.find({}, {"_id": 0}).sort("createdAt", -1).limit(10))
    except PyMongoError as e:
        app.logger.error("history failed: %s", e)
        return jsonify(error="Database unavailable, please try again."), 503
    return jsonify([{**row, "createdAt": row["createdAt"].isoformat()} for row in rows])


@app.get("/health")
def health():
    # 200 only if MongoDB answers. Any replica-set member counts (PRIMARY_PREFERRED), so a
    # PRIMARY election does not take every web pod out of the Service at the same time.
    try:
        with pymongo.timeout(2):
            client.admin.command("ping", read_preference=ReadPreference.PRIMARY_PREFERRED)
        return "ok", 200
    except PyMongoError:
        return "cannot reach MongoDB", 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

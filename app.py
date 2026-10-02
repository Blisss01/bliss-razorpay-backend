import os
import re
import razorpay
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": [
    "https://blisschocolate.in",
    "https://www.blisschocolate.in"
]}})

KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

if not KEY_ID or not KEY_SECRET:
    raise RuntimeError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required")

client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

# Server-side price list. Never trust prices sent by the browser.
PRODUCT_PRICES = {
    "Dark Chocolate Bar": 1,
    "Pure Milk Chocolate": 59,
    "Twin Bliss Bar": 69,
    "Cherry Dark Indulgence": 69,
    "Oreo Crunch Bar": 79,
    "Rainbow Drizzle Bar": 59,
    "Nutty Cocoa Bar": 99,
    "Love You Chocolate Bar": 99,
    "Raksha Bandhan Chocolate Duo": 99,
    "Rakhi Celebration Chocolate Box": 109,
    "Raksha Bond Treats": 59,
    "Birthday Chocolate Gift Wrapping": 59,
    "Raksha Bandhan Duo Bar": 79,
    "Couple Birthday Chocolate Bar": 59,

    "Bliss Assorted Chocolate Tub": 99,
    "Golden Heart Chocolate Box": 69,
    "Love You Chocolate Gift Box": 129,
    "Happy Rakhi Chocolate Box": 149,
    "1 KG Pure Dark Chocolate": 650,
    "1 KG Pure Milk Chocolate": 800,
    "1 KG Mix(Dark & Milk) Chocolate": 700,
    "1 KG Dark Tutti Futti Chocolate": 700,
    "1 KG Dark With Dry Fruit Chocolate": 800,
    "1 KG Dark With Oreo Chocolate": 750,

    "Royal Snack Celebration Hamper": 399,
    "Premium Snack Crate": 399,
    "Red Ribbon Celebration Hamper": 459,
    "Chocolate Lover’s Gift Tray": 599,
    "Festive Crunch Hamper": 399,
    "Deluxe Dry Fruit & Chocolate Hamper": 650,
}

def calculate_total(items):
    if not isinstance(items, list) or not items:
        raise ValueError("Cart is empty")

    total = 0
    clean_items = []

    for row in items:
        name = str(row.get("name", "")).strip()
        quantity = row.get("quantity")

        if name not in PRODUCT_PRICES:
            raise ValueError(f"Invalid product: {name}")

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise ValueError("Invalid quantity")

        if quantity < 1 or quantity > 50:
            raise ValueError("Invalid quantity")

        unit_price = PRODUCT_PRICES[name]
        total += unit_price * quantity
        clean_items.append({
            "name": name,
            "quantity": quantity,
            "unit_price": unit_price
        })

    return total, clean_items


@app.get("/")
def health():
    return jsonify({"ok": True, "service": "Bliss Razorpay backend"})


@app.post("/api/create-order")
def create_order():
    try:
        body = request.get_json(silent=True) or {}
        total, items = calculate_total(body.get("items"))

        receipt = "bliss_" + re.sub(r"[^a-zA-Z0-9]", "", os.urandom(8).hex())[:20]

        order = client.order.create(data={
            "amount": total * 100,  # INR -> paise
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "store": "Bliss & Co.",
                "items_count": str(sum(x["quantity"] for x in items))
            }
        })

        return jsonify({
            "key_id": KEY_ID,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "items": items
        })

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("create-order failed")
        return jsonify({"error": "Could not create Razorpay order"}), 500


@app.post("/api/verify-payment")
def verify_payment():
    try:
        body = request.get_json(silent=True) or {}

        order_id = str(body.get("razorpay_order_id", "")).strip()
        payment_id = str(body.get("razorpay_payment_id", "")).strip()
        signature = str(body.get("razorpay_signature", "")).strip()

        if not order_id or not payment_id or not signature:
            return jsonify({"success": False, "error": "Missing payment details"}), 400

        # Verify Checkout signature using Razorpay's server-side SDK.
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })

        # Also check the payment amount/status against the Razorpay order.
        payment = client.payment.fetch(payment_id)
        order = client.order.fetch(order_id)

        if payment.get("order_id") != order_id:
            return jsonify({"success": False, "error": "Payment/order mismatch"}), 400

        if int(payment.get("amount", 0)) != int(order.get("amount", 0)):
            return jsonify({"success": False, "error": "Payment amount mismatch"}), 400

        if payment.get("status") != "captured":
            return jsonify({"success": False, "error": "Payment is not captured"}), 400

        return jsonify({
            "success": True,
            "payment_id": payment_id,
            "order_id": order_id,
            "status": payment.get("status")
        })

    except Exception:
        app.logger.exception("verify-payment failed")
        return jsonify({"success": False, "error": "Payment verification failed"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

import os
import re
import razorpay

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://blisschocolate.in",
            "https://www.blisschocolate.in"
        ]
    }
})

# =========================
# RAZORPAY
# =========================

KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

if not KEY_ID or not KEY_SECRET:
    raise RuntimeError(
        "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required"
    )

client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))


# =========================
# SUPABASE DATABASE
# =========================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SECRET_KEY are required"
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)


# =========================
# PRODUCT PRICES
# =========================

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


# =========================
# CALCULATE TOTAL
# =========================

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

        subtotal = unit_price * quantity
        total += subtotal

        clean_items.append({
            "name": name,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal
        })

    return total, clean_items


# =========================
# HEALTH CHECK
# =========================

@app.get("/")
def health():

    return jsonify({
        "ok": True,
        "service": "Bliss Razorpay backend",
        "database": "connected"
    })


# =========================
# CREATE RAZORPAY ORDER
# + SAVE ORDER IN DATABASE
# =========================

@app.post("/api/create-order")
def create_order():

    try:

        body = request.get_json(silent=True) or {}

        total, items = calculate_total(
            body.get("items")
        )

        # Customer details from checkout form
        customer = body.get("customer") or {}
        customer_name = str(customer.get("name", "")).strip()
        customer_address = str(customer.get("address", "")).strip()
        customer_state = str(customer.get("state", "")).strip()
        customer_city = str(customer.get("city", "")).strip()
        customer_pincode = str(customer.get("pincode", "")).strip()
        customer_phone = str(customer.get("phone", "")).strip()
        customer_email = str(customer.get("email", "")).strip()

        if not all([
            customer_name, customer_address, customer_state,
            customer_city, customer_pincode, customer_phone, customer_email
        ]):
            raise ValueError("Customer details are incomplete")

        if not customer_pincode.isdigit() or len(customer_pincode) != 6:
            raise ValueError("Invalid pincode")

        if not customer_phone.isdigit() or len(customer_phone) != 10:
            raise ValueError("Invalid contact number")

        receipt = "bliss_" + re.sub(
            r"[^a-zA-Z0-9]",
            "",
            os.urandom(8).hex()
        )[:20]

        # Create Razorpay order
        order = client.order.create(data={
            "amount": total * 100,
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "store": "Bliss & Co.",
                "items_count": str(
                    sum(x["quantity"] for x in items)
                )
            }
        })

        # Generate our own order number
        order_number = "BLISS-" + re.sub(
            r"[^a-zA-Z0-9]",
            "",
            os.urandom(5).hex()
        ).upper()

        # Save / update customer first
        existing_customer = supabase.table("customers") \
            .select("id") \
            .eq("phone", customer_phone) \
            .limit(1) \
            .execute()

        if existing_customer.data:
            customer_id = existing_customer.data[0]["id"]

            supabase.table("customers") \
                .update({
                    "name": customer_name,
                    "email": customer_email,
                    "phone": customer_phone,
                    "address": customer_address,
                    "city": customer_city,
                    "state": customer_state,
                    "pincode": customer_pincode
                }) \
                .eq("id", customer_id) \
                .execute()
        else:
            customer_result = supabase.table("customers").insert({
                "name": customer_name,
                "email": customer_email,
                "phone": customer_phone,
                "address": customer_address,
                "city": customer_city,
                "state": customer_state,
                "pincode": customer_pincode
            }).execute()

            customer_id = customer_result.data[0]["id"]

        # Save main order
        db_order = supabase.table("orders").insert({
            "customer_id": customer_id,
            "razorpay_order_id": order["id"],
            "order_number": order_number,
            "total_amount": total,
            "payment_status": "PENDING",
            "order_status": "NEW"
        }).execute()

        saved_order = db_order.data[0]

        # Save order items
        order_items = []

        for item in items:

            product_result = supabase.table("products") \
                .select("id") \
                .eq("name", item["name"]) \
                .limit(1) \
                .execute()

            product_id = None

            if product_result.data:
                product_id = product_result.data[0]["id"]

            order_items.append({
                "order_id": saved_order["id"],
                "product_id": product_id,
                "product_name": item["name"],
                "quantity": item["quantity"],
                "price": item["unit_price"],
                "subtotal": item["subtotal"]
            })

        supabase.table("order_items").insert(
            order_items
        ).execute()

        return jsonify({
            "key_id": KEY_ID,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "items": items,
            "order_number": order_number
        })

    except ValueError as exc:

        return jsonify({
            "error": str(exc)
        }), 400

    except Exception as exc:

        app.logger.exception(
            "create-order failed"
        )

        return jsonify({
            "error": "Could not create Razorpay order"
        }), 500


# =========================
# VERIFY PAYMENT
# + SAVE PAYMENT IN DATABASE
# =========================

@app.post("/api/verify-payment")
def verify_payment():

    try:

        body = request.get_json(silent=True) or {}

        order_id = str(
            body.get("razorpay_order_id", "")
        ).strip()

        payment_id = str(
            body.get("razorpay_payment_id", "")
        ).strip()

        signature = str(
            body.get("razorpay_signature", "")
        ).strip()

        if not order_id or not payment_id or not signature:

            return jsonify({
                "success": False,
                "error": "Missing payment details"
            }), 400

        # Verify Razorpay signature
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })

        # Fetch Razorpay payment/order
        payment = client.payment.fetch(
            payment_id
        )

        order = client.order.fetch(
            order_id
        )

        # Security checks
        if payment.get("order_id") != order_id:

            return jsonify({
                "success": False,
                "error": "Payment/order mismatch"
            }), 400

        if int(payment.get("amount", 0)) != int(
            order.get("amount", 0)
        ):

            return jsonify({
                "success": False,
                "error": "Payment amount mismatch"
            }), 400

        if payment.get("status") != "captured":

            return jsonify({
                "success": False,
                "error": "Payment is not captured"
            }), 400

        # Find our database order
        db_order_result = supabase.table("orders") \
            .select("id") \
            .eq("razorpay_order_id", order_id) \
            .limit(1) \
            .execute()

        if not db_order_result.data:

            return jsonify({
                "success": False,
                "error": "Database order not found"
            }), 404

        db_order_id = db_order_result.data[0]["id"]

        # Check if payment already saved
        existing_payment = supabase.table("payments") \
            .select("id") \
            .eq(
                "razorpay_payment_id",
                payment_id
            ) \
            .limit(1) \
            .execute()

        if not existing_payment.data:

            supabase.table("payments").insert({

                "order_id": db_order_id,
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "amount": int(
                    payment.get("amount", 0)
                ) / 100,
                "payment_method": payment.get(
                    "method"
                ),
                "status": "CAPTURED"

            }).execute()

        # Update order status
        supabase.table("orders") \
            .update({
                "payment_status": "PAID",
                "order_status": "CONFIRMED"
            }) \
            .eq("id", db_order_id) \
            .execute()

        return jsonify({

            "success": True,

            "payment_id": payment_id,

            "order_id": order_id,

            "status": payment.get(
                "status"
            )

        })

    except Exception:

        app.logger.exception(
            "verify-payment failed"
        )

        return jsonify({
            "success": False,
            "error": "Payment verification failed"
        }), 400


# =========================
# LOCAL DEVELOPMENT
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get("PORT", 5000)
        ),
        debug=True
    )

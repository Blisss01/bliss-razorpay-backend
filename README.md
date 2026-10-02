# Bliss Chocolate - Razorpay Backend

This backend creates Razorpay Orders and verifies successful Checkout payments.
The Razorpay Secret is stored only as a server environment variable.

## Local setup

1. Install Python.
2. Open this folder in VS Code.
3. Run:

   pip install -r requirements.txt

4. Create a `.env` file from `.env.example`.
5. Put your Razorpay TEST Key ID and TEST Key Secret in `.env`.
6. Start:

   python app.py

The API will run at http://127.0.0.1:5000

## Render

Create a Web Service from this folder/repository.

Build command:
pip install -r requirements.txt

Start command:
gunicorn app:app

Environment variables:
RAZORPAY_KEY_ID = your TEST Key ID
RAZORPAY_KEY_SECRET = your TEST Key Secret

Do not commit `.env` to GitHub.

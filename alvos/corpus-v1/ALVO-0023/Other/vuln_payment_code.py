import hashlib
from flask import Flask, redirect
from secrets import token_hex

secret = "[....]"
app = Flask(__name__)


def sign_for_payment(payment_information):
    # compute signature to ensure the payment details
    # cannot be tampered with
    data = secret + payment_information
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


@app.route('/redirect_for_payment')
def redirect_for_payment():
    tx_id = token_hex(16)
    payment_info = "transaction_id=" + tx_id + "&amount=20.00"
    params = payment_info + "&sign=" + sign_for_payment(payment_info)
    return redirect("https://onlineshop/payment?" + params,
                    code=302)

#!/usr/bin/env python3

import hashlib
from flask import Flask, redirect
from secrets import token_hex

secret = "[....]"
app = Flask(__name__)

# Vulnerable to length extension attack

def sign_for_payment(payment_information):
	"""
	calculate the signature to ensure the payment details
    needs to not be tampered with
    """
	data = secret + payment_information
	return hashlib.sha256(data.encode('utf-8')).hexdigest()


@app.route('/redirect_for_payment')
def redirect_for_payment():
	tx_id = token_hex(16)
	payment_info = "transaction_id=" + tx_id + "&ammount=20.00"
	# payment information catted to secret & not using hmac
	params = payment_info + "&sign=" + sign_for_payment(payment_info)
	return redirect("https://badwebapp.com?" + params, code=302)

	# how to rewrite securely ?

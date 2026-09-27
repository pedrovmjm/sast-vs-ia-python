#!/usr/bin/env/python 3

"""
app.py

SYNOPSIS
========
::
 
   Follow the set up instructions on the README.md
   After executing export FLASK_ENV=development
   A server will be running on localhost port 5000
   Open your browser and navigate to: http://127.0.0.1:5000
   The Web App should open and you can begin testing
   This process is the same for running each Flask App in this repository.

DESCRIPTION
===========

This is an XSS vulnerable web app. 
See the commented lines of source code in index.html for specific examples.
The code in index.html is intended to be modified to demonstrate reflected and stored XSS

"""
from flask import Flask, render_template, request
import db

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        db.add_comment(request.form['comment'])

    search_query = request.args.get('q')

    comments = db.get_comments(search_query)

    return render_template('index.html',
                           comments=comments,
                           search_query=search_query)

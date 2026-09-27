#!/usr/bin/env python3

"""
main.py
Building a flask SQLite database web app using Jinja template engine

SYNOPSIS
========
::
   The code in main.py serves as a POC for safe and uncoding to protect against SQL Injection attacks.
   And, is commented in such a way that this web application can be run either secured, or vulnerable.
   There exist two versions of the function, def get_db_connection(): 
   Each one is labled with a # comment above it. 
   # Correct/safe,  and the others labled # Bad: Vulnerable to SQL Injection.
   Additional commented code is left at the bottom for customization and augmenting main.py if the user desires.
   If you want to run the correct version of main.py, then use main_safe.py in this repo

DESCRIPTION
===========

This web app was created to be intentionally vulnerable to SQL injection and used as a Proof Of Concept
See running_flask.txt, for instructions on running this app in your IDE.
The user has full use of this app as an interactive blog/message board. You can read, write, edit and delete posts. 
Each of the HTML files in this folder: post, index, base, create, and edit, correspond to the functions below.


"""

import re
import sqlite3
from flask import Flask, render_template, request, url_for, flash, redirect
from werkzeug.exceptions import abort


# Safe connection to the DB
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Safe retrieval of a selected post
def get_post(post_id):
    conn = get_db_connection()  # SQL configured to schema.sql
    post = conn.execute('SELECT * FROM posts WHERE id = ?',
                        (post_id,)).fetchone()
    conn.close()
    if post is None:
        abort(404)
    return post

app = Flask(__name__)
app.config['SECRET_KEY'] = 'qwerty12345'


# Bad: Vulnerable to SQL Injection
# Attempted Connection to the DB 
# And attempted retrieval of a post in the same function
# This can work
# But the example above proves simpler and doesn't need regex use
def get_db_connection():
    conn = get_db_connection()
 """
  The problem: The regex filters values that begin and end with numbers only as indicated by \d
  also, re.M indicates a multi-line regex evaluation
  the post id is catted to the remaining query
"""
    num_format = re.compile(r'^\d+$', re.M) # weak regex
        if re.match(num_format,post_id):
        # SQLI vuln, passes user input to string
            post = conn.execute('SELECT * FROM posts WHERE id = '+post_id).fetchone()
            conn.close()
            if post is None:
                abort(404)
            return post
        else:
            abort(404)


@app.route('/')
def index():
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM posts').fetchall()
    conn.close()
    return render_template('index.html', posts=posts)


@app.route('/<int:post_id>')
def post(post_id):
    post = get_post(post_id)
    return render_template('post.html', post=post)


@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            conn = get_db_connection()
            conn.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
                         (title, content))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))

    return render_template('create.html')


@app.route('/<int:id>/edit', methods=('GET', 'POST'))
def edit(id):
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            conn = get_db_connection()
            conn.execute('UPDATE posts SET title = ?, content = ?'
                         ' WHERE id = ?',
                         (title, content, id))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))

    return render_template('edit.html', post=post)


@app.route('/<int:id>/delete', methods=('POST',))
def delete(id):
    post = get_post(id)
    conn = get_db_connection()
    conn.execute('DELETE FROM posts WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('"{}" was successfully deleted!'.format(post['title']))
    return redirect(url_for('index'))


# To use a diffent port, uncomment the lines below
# Below is port 8080
# if __name__ == "__main__":
#     app.run(host="127.0.0.1", port=8080, debug=True)


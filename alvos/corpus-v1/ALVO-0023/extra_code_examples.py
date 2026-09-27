#!/usr/bin/env python3

"""
Extra

SYNOPSIS
========
Scrap code snippits

DESCRIPTION
===========

This is scrap code from creating the apps in this repository.
I left here here to serve as a template and resource for quick editing of existing code, and writing other apps in the future


"""

# import re
# import sqlite3
# from flask import Flask, render_template, request, url_for, flash, redirect
# from werkzeug.exceptions import abort
#
# def get_db_connection():
#     conn = sqlite3.connect('database.db')
#     conn.row_factory = sqlite3.Row
#     return conn
#
# app = Flask(__name__)
# app.config['SECRET_KEY'] = 'qwerty12345'
#
# @app.route('/create', methods=('GET', 'POST'))
# def create():
#     if request.method == 'POST':
#         title = request.form['title']
#         content = request.form
#
#         if not title:
#             flash('Title is required')
#         else:
#             conn = get_db_connection()
#             conn.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
#                          (title, content))
#             conn.commit()
#             conn.close()
#             return redirect(url_for('index'))
#
#     return render_template('create.html')
#
# @app.route('/')
# def index():
#     conn = get_db_connection()
#     posts = conn.execute('SELECT * FROM posts').fetchall()
#     conn.close()
#     return render_template('index.html', posts=posts)
#
# #def get_post(post_id):
# # Vulnerable to SQLi
# def get_post(post_id):
#     conn = get_db_connection()
#     num_format = re.compile(r'^\d+$', re.M) # regex begins and ends with only numbers & multiline
#     if re.match(num_format, post_id): # and the lack of filtering passes input to post_id
#         post = conn.execute('SELECT * FROM posts WHERE id = ' + post_id).fetchone()
#         conn.close()
#         if post is None:
#             abort(404)
#         return post
#     else:
#         abort(404)
#
#     # CORRECT SAFE CODE
#     # conn = get_db_connection()
#     # post = conn.execute('SELECT * FROM posts WHERE id = ?',
#     #                     (post_id,)).fetchone()
#     # conn.close()
#     # if post is None:
#     #     abort(404)
#     # return post
#
# # could injecting ' comas and or <> escape the param and lead to exploit?
# @app.route('/<int:post_id>')
# def post(post_id):
#     post = get_post(post_id)
#     return render_template('post.html', post=post)
#
#
# # if __name__ == "__main__":
# #     app.run(host="127.0.0.1", port=8080, debug=True)
#
#
#

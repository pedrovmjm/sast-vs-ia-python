#!/usr/bin/env python3

"""
SQL Injection: vulnerable code example

SYNOPSIS
========
::

   python3 sqli_example.py

DESCRIPTION
===========
THis is just an example, it is not integrated/part of this active code in this repo
Attackers will hunt for SQL injection in a variety of ways.
Submitting the single quote character ' and  comments --
looking for errors or other anomalies

High Risk Security Vulnerabilities
SQL Injection – Passing Safe Query Parameters

"""

# #BAD Vulnerable Example.  DON'T Do This.
cursor.execute("SELECT securitycoaches FROM users WHERE username = '" + username + '");
cursor.execute("SELECT securitycoaches min FROM users WHERE username = '{}'".format(username));

cursor.execute("SELECT securitycoaches FROM users WHERE username = '%s' % username);
cursor.execute(f"SELECT securitycoaches FROM users WHERE username = '{username}'");

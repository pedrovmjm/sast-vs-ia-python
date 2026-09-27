#!/usr/bin/env python3 

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from Encrypt import Encrypt
from Username import Username


class MyServer(BaseHTTPRequestHandler):

    def get(self):
        cookies = SimpleCookie(self.headers.get('Cookie'))
        if cookies.get('username'):
            Username.pickle()
            # username = pickle.loads(base64.b64decode(cookies.get('username').value))
            # Issue:B301:blacklist Pickle and modules that wrap it can be unsafe when used to deserialize untrusted data
            # Vulnerable code below: Calls pickle.loads on user supplied info
            # No signature present or anything preventing the sending of a malicious pickle object
            # This would enable code execution

        else:
            username='stranger'
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>Hello</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))

            # Below, the username is not escaped, this leads to XSS attack
            self.wfile.write(bytes("<h1>Hello %s</h1>" % username, "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))


if __name__ == '__main__':
    webServer = HTTPServer(('0.0.0.0', 1337), MyServer)
    # Issue:B104:hardcoded_bind_all_interfaces Possible binding to all interfaces.

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")

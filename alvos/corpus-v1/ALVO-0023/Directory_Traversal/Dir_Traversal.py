from http.server import BaseHTTPRequestHandler, HTTPServer
import re
from os.path import exists
import os


class MyServer(BaseHTTPRequestHandler):
    def do_GET(self): # no data type receive defined
        path = os.getcwd() # dir traversal and possible LFI
        pattern = r'/\.\.\/\.\.\/' # weak regex pattern
        if re.match(pattern, self.path): # escape characters needed
            self.send_response(404)
            return
        path += self.path
        if path.endswith('/'):
            path += 'index.html'
        print(path)
        if exists(path):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(open(path).read().encode('utf-8')) # path is open no string mod
        else:
            self.send_response(404)


if __name__ == "__main__":
    webServer = HTTPServer(('0.0.0.0', 1337), MyServer)

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")

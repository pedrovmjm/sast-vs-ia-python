from http.server import BaseHTTPRequestHandler, HTTPServer
from http.cookies import SimpleCookie
import base64

from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

KEY = Random.new().read(AES.block_size)

# Should use frameworks that are secure MVC Modele View Controller .NET MVC, REST services

class MyServer(BaseHTTPRequestHandler):

    def decrypt(self, cookie):
        enc = base64.urlsafe_b64decode(cookie)
        iv = enc[0:AES.block_size]
        encd = enc[AES.block_size:]
        aes = AES.new(KEY, AES.MODE_CBC, iv)
        return unpad(aes.decrypt(encd), AES.block_size).decode('utf-8')

    def do_GET(self):
        cookies = SimpleCookie(self.headers.get('Cookie'))
        if cookies.get('session_id'):
            try:
                username = self.decrypt(cookies.get('session_id').value) # regex and escaped all inputs
            except:
                self.send_response(500)
                return
        else:
            username = 'Anonymous'
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("Hello", "utf-8"))
        self.wfile.write(bytes("", "utf-8"))
        self.wfile.write(bytes("Hello %s" % username, "utf-8")) # needs encoding
        self.wfile.write(bytes("", "utf-8"))


print(encrypt('admin'))

if __name__ == "__main__":
    webServer = HTTPServer(('0.0.0.0', 1337), MyServer)
    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    print("Server stopped.")

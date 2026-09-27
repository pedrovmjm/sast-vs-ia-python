import socket
import ssl

hostname = 'website.com'
context = ssl.create_default_context()
context.check_hostname = False # make true to prevent host header injection

with socket.create_connection((hostname, 443)) as sock:
    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
        ssock.write("GET / HTTP/1.1\r\nHost: #{hostname}\r\n\r\n".encode('utf-8')) # context vencode and escape characters
        print(ssock.read())  # regex and encode on outbound  & HTML encode

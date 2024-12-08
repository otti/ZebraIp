import socket

HOST = "zebra.lan"
PORT = 9100

label = """
N
A0,0,0,4,1,1,N, "Test"
P1
"""

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(label.encode("latin_1"))
    s.close();

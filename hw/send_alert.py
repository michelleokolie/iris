"""Send one Alert line to io, for bench testing. Usage: python hw/send_alert.py 2 left [--socket PATH]"""
import argparse
import socket

ap = argparse.ArgumentParser()
ap.add_argument("level")
ap.add_argument("direction")
ap.add_argument("--socket", default="/tmp/iris.sock")
args = ap.parse_args()
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
    s.connect(args.socket)
    s.sendall(f"{args.level} {args.direction}\n".encode())

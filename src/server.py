import sys
import struct
import socket
import threading
from base64 import b64encode
from hashlib import sha1, md5

FIN	= 0x80
OPCODE = 0x0f
MASKED = 0x80
PAYLOAD_LEN = 0x7f
PAYLOAD_LEN_EXT16 = 0x7e
PAYLOAD_LEN_EXT64 = 0x7f

OPCODE_CONTINUATION = 0x0
OPCODE_TEXT		 = 0x1
OPCODE_BINARY	   = 0x2
OPCODE_CLOSE_CONN   = 0x8
OPCODE_PING		 = 0x9
OPCODE_PONG		 = 0xA

MD5 = md5(open('NWY.zip','rb').read()).hexdigest()

def encode_to_UTF8(data):
	try:
		return data.encode('UTF-8')
	except UnicodeEncodeError as e:
		print("Could not encode data to UTF-8 -- %s" % e)
		return False
	except Exception as e:
		raise(e)
		return False

def try_decode_UTF8(data):
	try:
		return data.decode('utf-8')
	except UnicodeDecodeError:
		return False
	except Exception as e:
		raise(e)

def send_binary(conn, opcode=OPCODE_BINARY):
	header  = bytearray()
	file = open("NWY.zip", 'rb')
	payload = file.read()
	payload_length = len(payload)
	header.append(FIN | opcode)
	header.append(PAYLOAD_LEN_EXT16)
	header.extend(struct.pack(">H", payload_length))
	conn.sendall(header + payload)

def send_text(conn, message, opcode=OPCODE_TEXT):
	if isinstance(message, bytes):
		message = try_decode_UTF8(message)  # this is slower but ensures we have UTF-8

	header  = bytearray()
	payload = encode_to_UTF8(message)
	payload_length = len(payload)
	header.append(FIN | opcode)
	header.append(payload_length)
	conn.sendall(header + payload)

def send_close(conn):
	send_text(conn, "close", OPCODE_CLOSE_CONN)

def send_pong(conn, message):
	send_text(conn, message, OPCODE_PONG)

def read_http_headers(data):
	headers = {}
	temps = data.decode().strip().split('\n')
	temps.pop(0)
	for temp in temps:
		head, value = temp.split(':', 1)
		headers[head.lower().strip()] = value.strip()
	return headers

def handshake(conn, data):
	headers = read_http_headers(data)
	try:
		if headers['upgrade'].lower() != 'websocket':
			send_close(conn)
			return
	except KeyError:
		send_close(conn)
		return
	try:
		key = headers['sec-websocket-key']
	except KeyError:
		print("no key")
		send_close(conn)
		return

	response = make_handshake_response(key)
	conn.sendall(response.encode())

def make_handshake_response(key):
	return \
	  'HTTP/1.1 101 Switching Protocols\r\n'\
	  'Upgrade: websocket\r\n'			  \
	  'Connection: Upgrade\r\n'			 \
	  'Sec-WebSocket-Accept: %s\r\n'		\
	  '\r\n' % calculate_response_key(key)

def calculate_response_key(key):
	GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
	hash = sha1(key.encode() + GUID.encode())
	response_key = b64encode(hash.digest()).strip()
	return response_key.decode('ASCII')

def handleMessage(conn, buff):
	try:
		b1, b2 = buff[0], buff[1]
	except Exception as e:
		send_close(conn)
		return
	fin	= b1 & FIN
	opcode = b1 & OPCODE
	masked = b2 & MASKED
	payload_length = b2 & PAYLOAD_LEN
	if opcode == OPCODE_CLOSE_CONN:
		print("close")
		send_close(conn)
		return
	if not masked:
		print("not masked, die")
		send_close(conn)
		return
	if opcode not in [OPCODE_TEXT, OPCODE_BINARY, OPCODE_CLOSE_CONN, OPCODE_PING]:
		print("Unknown opcode", end = " ")
		print(opcode)
		send_close(conn)
		return
	shift = 0
	if payload_length == 126:
		print("126")
		shift = 2
		payload_length = struct.unpack(">H", buff[3:5])[0]
	elif payload_length == 127:
		print("127")
		print("THIS IS THE MUST DIE THING")
		send_text(conn, "0")
		return
	masks = buff[2+shift:6+shift]
	message_bytes = bytearray()
	for message_byte in buff[6+shift:]:
		message_byte ^= masks[len(message_bytes) % 4]
		message_bytes.append(message_byte)
	if opcode==OPCODE_PING:
		send_pong(conn, message_bytes.decode())
	elif opcode==OPCODE_TEXT:
		txt = message_bytes.decode()
		print(txt)
		if "!echo" in txt:
			send_text(conn, txt[6:])
		elif "!submission" in txt:
			send_binary(conn)
	else:
		if md5(message_bytes).hexdigest() == MD5:
			print("THIS IS THE SAME THING" + str(self.server.handler_to_client(self)['id']))
			send_text(conn, "1")
		else:
			print("THIS IS THE WRONG THING" + str(self.server.handler_to_client(self)['id']))
			send_text(conn, "0")

def handleThread(conn, data):
	handshake(conn, data)
	while True:
		buff = conn.recv(2<<15)
		handleMessage(conn, buff)


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
HOST = 'localhost' 
PORT = 80
s.bind((HOST, PORT))
s.listen()
print("Loop start")
while True:
	conn, addr = s.accept()
	print("New thread")
	print('Connected', addr)
	data = conn.recv(1024)
	connectionThread = threading.Thread(target=handleThread, args=(conn, data))
	connectionThread.start()




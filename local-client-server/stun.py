import enum
import ipaddress
import socket
import struct
import os

MAGIC = 0x2112A442
MAGIC_BYTES = struct.pack("!I", MAGIC)

HEADER_STRUCT = struct.Struct("!HHI12s")

ATTR_HEADER_STRUCT = struct.Struct("!HH")
XOR_MAPPED_ADDRESS = 0x20


class Protocol(enum.IntEnum):
    IPv4 = 1
    IPv6 = 2


class Class(enum.IntEnum):
    REQUEST = 0x000
    INDICATION = 0x010
    RESPONSE = 0x100
    ERROR = 0x110

    @classmethod
    def masked(cls, i):
        return cls(i & 0xFF00)


class Method(enum.IntEnum):
    BINDING = 0x1
    SHARED_SECRET = 0x2
    ALLOCATE = 0x3
    REFRESH = 0x4
    SEND = 0x6
    DATA = 0x7
    CREATE_PERMISSION = 0x8
    CHANNEL_BIND = 0x9

    @classmethod
    def masked(cls, i):
        return cls(i & 0xFF)


def xor(a, b):
    return (i ^ j for i, j in zip(a, b))


def decode_xor_mapped_address(payload, offset, size, transaction_id):
    ptr = offset + 2 # reserved(1) + protocol(1)
    port_xor = bytes(xor(payload[ptr : ptr + 2], MAGIC_BYTES))
    ptr += 2  # port(2)  
    ip_xor = bytes(xor(payload[ptr:offset+size], MAGIC_BYTES + transaction_id))
    return ipaddress.ip_address(ip_xor), int.from_bytes(port_xor)


class Message:

    def __init__(self, method, class_, id, attrs):
        self.method = method
        self.class_ = class_
        self.id = id
        self.attrs = attrs

    @classmethod
    def auto(cls, method, class_, id=None, attrs=None):
        return cls(method, class_, id or os.urandom(12), attrs or {})


def decode_message(data):
    if len(data) < HEADER_STRUCT.size:
        raise ValueError("Incomplete message")

    rtype, rlength, rmagic, rid = HEADER_STRUCT.unpack_from(data, 0)

    if (len(data) - HEADER_STRUCT.size) < rlength:
        raise ValueError("Incomplete message")
    if rmagic != MAGIC:
        raise ValueError("Invalid message header: invalid magic")

    cls = Class.masked(rtype)
    method = Method.masked(rtype)

    offset = HEADER_STRUCT.size
    attrs = {}
    while offset < len(data):
        attr_type, attr_len = ATTR_HEADER_STRUCT.unpack_from(data, offset)
        offset += ATTR_HEADER_STRUCT.size
        if attr_type == XOR_MAPPED_ADDRESS:
            attrs["address"] = decode_xor_mapped_address(data, offset, attr_len, rid)

        # Align to 4-byte boundary
        offset += attr_len + (4 - (attr_len % 4)) % 4

    return Message(method, cls, rid, attrs)


def encode_message(message):
    header = HEADER_STRUCT.pack(message.method, message.class_, MAGIC, message.id)
    return header


def write_read(request, addr):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(request, addr)
        return sock.recvfrom(4096)


def stun_request(server_host="stun.l.google.com", server_port=19302):
    req_message = Message.auto(Method.BINDING, Class.REQUEST)
    request = encode_message(req_message)
    response, addr = write_read(request, (server_host, server_port))
    resp_message = decode_message(response)

    if resp_message.id != req_message.id:
        raise ValueError("Invalid STUN response header: unexpected transaction id")
    if resp_message.class_ != Class.RESPONSE:
        raise ValueError("Invalid STUN reply header: it's not a response")
    if resp_message.method != Method.BINDING:
        raise ValueError("Invalid STUN response header: it's not a binding")

    return resp_message.attrs["address"]


# Example usage
if __name__ == "__main__":
    ip, port = stun_request()
    host = socket.gethostbyaddr(str(ip))[0]
    print(f"{host=} {ip=!s} {port=}")

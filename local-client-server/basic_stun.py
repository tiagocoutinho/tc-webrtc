import os
import socket
import struct

MAGIC = 0x2112A442
MAGIC_BYTES = struct.pack("!I", MAGIC)

HEADER_STRUCT = struct.Struct("!HHI12s")

ATTR_HEADER_STRUCT = struct.Struct("!HH")
XOR_MAPPED_ADDRESS = 0x20

REQUEST = 0x000
RESPONSE = 0x100

BINDING = 0x1


def xor_magic(a):
    return (i ^ j for i, j in zip(a, MAGIC_BYTES))


def decode_xor_mapped_address(payload):
    offset = 2 # reserved(1) + protocol(1)
    port_xor = bytes(xor_magic(payload[offset : offset + 2]))
    offset += 2
    ip_xor = bytes(xor_magic(payload[offset : offset + 4]))
    return socket.inet_ntoa(ip_xor), int.from_bytes(port_xor)


def write_read(request, addr):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(request, addr)
        return sock.recvfrom(4096)


def stun_request(server_host="stun.l.google.com", server_port=19302):
    id_ = os.urandom(12)
    request = HEADER_STRUCT.pack(BINDING | REQUEST, 0, MAGIC, id_)
    payload, _ = write_read(request, (server_host, server_port))

    offset = HEADER_STRUCT.size
    while offset < len(payload):
        attr_type, attr_length = ATTR_HEADER_STRUCT.unpack_from(payload, offset)
        offset += ATTR_HEADER_STRUCT.size
        if attr_type == XOR_MAPPED_ADDRESS:
            return decode_xor_mapped_address(payload[offset: offset + attr_length])
        # Align to 4-byte boundary
        offset += attr_length +  (4 - (attr_length % 4)) % 4
    return "", 0


# Example usage
if __name__ == "__main__":
    ip, port = stun_request()
    host = socket.gethostbyaddr(ip)[0]
    print(f"{host=} {ip=} {port=}")

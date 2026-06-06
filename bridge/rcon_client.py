"""
Minimal Source RCON client for talking to a Factorio dedicated server.

RCON = Remote Console. A tiny TCP protocol (originally from Valve's Source
engine) for sending console commands to a game server. Factorio implements
it natively. Spec: https://developer.valvesoftware.com/wiki/Source_RCON_Protocol

This is intentionally small — no third-party packages, no async, just enough
to send a command and read whatever the server prints back.

Typical use:

    from rcon_client import RconClient
    with RconClient() as r:
        print(r.command("/version"))

Configuration comes from environment variables:
    FACTORIO_RCON_HOST     default 127.0.0.1
    FACTORIO_RCON_PORT     default 27015
    FACTORIO_RCON_PASSWORD required
"""

from __future__ import annotations

import os
import socket
import struct

# Source RCON packet types
SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0


def _pack(packet_id: int, packet_type: int, body: str) -> bytes:
    """Build one Source RCON packet.
    Layout (little-endian): size:i32 id:i32 type:i32 body... \\0 \\0
    The 'size' field is the byte count of everything AFTER itself.
    """
    payload = body.encode("utf-8") + b"\x00\x00"
    size = 4 + 4 + len(payload)
    return struct.pack("<iii", size, packet_id, packet_type) + payload


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """TCP can deliver in chunks; read exactly n bytes or raise."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("server closed connection mid-packet")
        buf += chunk
    return buf


def _read_packet(sock: socket.socket) -> tuple[int, int, str]:
    raw_size = _recv_exact(sock, 4)
    size = struct.unpack("<i", raw_size)[0]
    rest = _recv_exact(sock, size)
    pid, ptype = struct.unpack("<ii", rest[:8])
    body = rest[8:-2].decode("utf-8", errors="replace")
    return pid, ptype, body


class RconClient:
    """Single-connection, single-command-at-a-time RCON client."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        password: str | None = None,
        connect_timeout: float = 5.0,
    ) -> None:
        self.host = host or os.environ.get("FACTORIO_RCON_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("FACTORIO_RCON_PORT", "27015"))
        self.password = password or os.environ.get("FACTORIO_RCON_PASSWORD")
        if not self.password:
            raise RuntimeError(
                "set the FACTORIO_RCON_PASSWORD environment variable "
                "before creating an RconClient"
            )
        self.connect_timeout = connect_timeout
        self.sock: socket.socket | None = None
        self._next_id = 1

    def __enter__(self) -> "RconClient":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self.host, self.port), timeout=self.connect_timeout
        )
        # AUTH handshake. Some servers send an extra empty RESPONSE_VALUE
        # before the real AUTH_RESPONSE; loop until we see AUTH_RESPONSE.
        self.sock.sendall(_pack(self._next_id, SERVERDATA_AUTH, self.password))
        self._next_id += 1
        while True:
            pid, ptype, _ = _read_packet(self.sock)
            if ptype == SERVERDATA_AUTH_RESPONSE:
                if pid == -1:
                    raise RuntimeError("RCON auth failed (wrong password?)")
                return

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def command(self, cmd: str, drain_timeout: float = 1.0,
                inter_packet_timeout: float = 0.05) -> str:
        """Send one command and return concatenated output.

        Two-phase drain:
          1. After sending the command, wait up to `drain_timeout` seconds for
             the FIRST response packet (the server may be busy under sim load).
          2. After the first packet, only wait `inter_packet_timeout` for each
             subsequent packet — packets within a single response come back
             back-to-back from Factorio, so a short inter-packet gap is
             plenty.

        This avoids both (a) cutting off slow first responses and (b) waiting
        the full drain timeout after the last packet of every call. Each call
        costs `(time to first packet) + inter_packet_timeout`.
        """
        if self.sock is None:
            raise RuntimeError("not connected")
        # Drain any stale packets from prior commands first.
        self.sock.settimeout(0)
        try:
            while True:
                _read_packet(self.sock)
        except (BlockingIOError, socket.timeout):
            pass
        self.sock.sendall(_pack(self._next_id, SERVERDATA_EXECCOMMAND, cmd))
        self._next_id += 1
        parts: list[str] = []
        # Phase 1: wait up to drain_timeout for the first packet.
        self.sock.settimeout(drain_timeout)
        try:
            _, _, body = _read_packet(self.sock)
            parts.append(body)
        except socket.timeout:
            return ""
        # Phase 2: keep reading while packets keep arriving fast.
        self.sock.settimeout(inter_packet_timeout)
        try:
            while True:
                _, _, body = _read_packet(self.sock)
                parts.append(body)
        except socket.timeout:
            pass
        return "".join(parts)

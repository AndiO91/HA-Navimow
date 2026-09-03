"""Minimal client for the Navimow mobile application's private cloud.

This protocol is undocumented and intentionally isolated from the official
Smart Home OAuth client.  It is used read-only for map geometry.

Protocol details are based on the MIT-licensed vahesoo/NaviMower project.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_public_key

PASSPORT_HOSTS = {
    "fra": ("api-passport-fra.willand.com", "api-passport-fra.ninebot.com"),
    "sg": ("api-passport-sg.willand.com", "api-passport-sg.ninebot.com"),
    "us": (
        "api-passport-us.ninebot.com",
        "api-passport-ore.ninebot.com",
        "api-passport-ore.willand.com",
    ),
    "bj": ("api-passport-bj.willand.com", "api-passport-bj.ninebot.com"),
}
MOWER_HOSTS = {
    "fra": ("navimow-fra.ninebot.com", "navimow-fra.willand.com"),
    "sg": ("navimow-sg.willand.com",),
    "us": ("navimow-fra.ninebot.com", "navimow-ore.willand.com"),
    "bj": ("navimow-bj.ninebot.com", "navimow-bj.willand.com"),
}
REGION_ALIASES = {"eu": "fra", "sea": "sg", "ore": "us"}
ALL_PASSPORT_HOSTS = tuple(
    dict.fromkeys(host for hosts in PASSPORT_HOSTS.values() for host in hosts)
)

CLIENT_ID = "mowerbot_app_prod"
CLIENT_KEY = "830247f0-da96-5c21-8cf0-ca09299795f9"
APP_VERSION = "402000003"
OS_VERSION = "13"

SESSION_KEY = bytes.fromhex("d0db95e2b4b2eeb99af3cfb638386209")
WRAP_PUB_PEM = b"""-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDRiEqrCME5SI2er9B+ZDweKWGe
TWnMn2dFG8rt+M6iKDv4Lui4p6BdHX2dbTgCRHNpJNz1tAsOGSPfcmcIkGxt3x+a
gs5YEmpkQq0zEYBSw8Stin2WVaPrUur00dEYr0qlNqDWIbMIuDOG554Sk11mUjY/
rzN0+TxJ5YNsU3kbwQIDAQAB
-----END PUBLIC KEY-----"""
KEY_DATA = {
    "keyDataOne": "4c9239e5377",
    "keyDataTwo": "c416f9ed",
    "keyDataThree": "230d8ee5",
    "keyDataFour": "53a22?h}",
}
_PUBLIC_NUMBERS = load_pem_public_key(WRAP_PUB_PEM).public_numbers()
_AUTH_ERROR_CODES = {90015, 90016, 401900, 401901, 401902, 401905, 1005}


class PrivateCloudError(Exception):
    """A private-cloud transport or business request failed."""

    def __init__(self, code: Any, description: str = "") -> None:
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description


class PrivateCloudAuthError(PrivateCloudError):
    """The private-cloud session needs new user credentials."""


@dataclass
class PrivateTokens:
    """Private mobile-app session tokens."""

    access_token: str
    refresh_token: str
    uuid: str = ""
    region: str = "fra"


def canonical_region(region: str | None) -> str:
    """Normalize known regional aliases."""
    value = str(region or "fra").strip().lower()
    return REGION_ALIASES.get(value, value)


def _sign(values: dict[str, Any]) -> str:
    return hashlib.sha256(
        "&".join(f"{key}={values[key]}" for key in sorted(values)).encode()
    ).hexdigest()


def _passport_headers(path: str, params: dict[str, Any]) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    values = {
        "app_version": APP_VERSION,
        "clientKey": CLIENT_KEY,
        "os": "Android",
        "os_language": "en",
        "os_version": OS_VERSION,
        "timestamp": timestamp,
        "url": path,
        **params,
    }
    return {
        "app_version": APP_VERSION,
        "clientId": CLIENT_ID,
        "os": "Android",
        "os_language": "en",
        "os_version": OS_VERSION,
        "timestamp": timestamp,
        "sign": _sign(values),
        "content-type": "application/json",
        "user-agent": "Segway_Mowerbot/4.02.0 (android)",
    }


def _passport_request(
    host: str, path: str, params: dict[str, Any], *, method: str
) -> dict[str, Any]:
    url = f"https://{host}{path}"
    body = None
    if method == "POST":
        body = json.dumps(params).encode()
    elif params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        data=body,
        headers=_passport_headers(path, params),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as err:
        try:
            return json.loads(err.read())
        except Exception as inner:
            raise PrivateCloudError(err.code, "Passport HTTP error") from inner
    except urllib.error.URLError as err:
        raise PrivateCloudError("network", str(err.reason)) from err


def lookup_region(username: str) -> str:
    """Find the account region before sending the password."""
    params = {"account": username, "device": "ANDROID"}
    last_transport_error: PrivateCloudError | None = None
    for host in ALL_PASSPORT_HOSTS:
        try:
            result = _passport_request(host, "/v3/region", params, method="GET")
        except PrivateCloudError as err:
            last_transport_error = err
            continue
        if str(result.get("resultCode")) == "90000":
            region = str((result.get("data") or {}).get("region") or "")
            if region:
                return region
        if str(result.get("resultCode")) != "00002":
            break
    if last_transport_error is not None:
        raise last_transport_error
    raise PrivateCloudAuthError("00002", "Private Navimow account not found")


def passport_login(username: str, password: str) -> PrivateTokens:
    """Authenticate against the owning regional Passport service."""
    raw_region = lookup_region(username)
    region = canonical_region(raw_region)
    params = {"username": username, "password": password, "device": "ANDROID"}
    last_error: PrivateCloudError | None = None
    for host in PASSPORT_HOSTS.get(region, ALL_PASSPORT_HOSTS):
        try:
            result = _passport_request(host, "/v3/user/login", params, method="POST")
        except PrivateCloudError as err:
            last_error = err
            continue
        code = str(result.get("resultCode"))
        if code != "90000":
            raise PrivateCloudAuthError(code, str(result.get("resultDesc", "")))
        data = result.get("data") or {}
        return PrivateTokens(
            str(data.get("access_token") or ""),
            str(data.get("refresh_token") or ""),
            str(data.get("uuid") or ""),
            str(data.get("region") or raw_region),
        )
    if last_error is not None:
        raise last_error
    raise PrivateCloudError("network", "No Passport host responded")


def passport_refresh(tokens: PrivateTokens) -> PrivateTokens:
    """Refresh a private mobile-app session."""
    region = canonical_region(tokens.region)
    params = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "device": "ANDROID",
    }
    last_error: PrivateCloudError | None = None
    for host in PASSPORT_HOSTS.get(region, ALL_PASSPORT_HOSTS):
        try:
            result = _passport_request(host, "/v3/user/refresh", params, method="POST")
        except PrivateCloudError as err:
            last_error = err
            continue
        code = str(result.get("resultCode"))
        if code != "90000":
            raise PrivateCloudAuthError(code, str(result.get("resultDesc", "")))
        data = result.get("data") or {}
        return PrivateTokens(
            str(data.get("access_token") or ""),
            str(data.get("refresh_token") or ""),
            str(data.get("uuid") or tokens.uuid),
            str(data.get("region") or tokens.region),
        )
    if last_error is not None:
        raise last_error
    raise PrivateCloudError("network", "No Passport host responded")


def _pkcs7(value: bytes) -> bytes:
    padding = 16 - len(value) % 16
    return value + bytes([padding]) * padding


def _unpkcs7(value: bytes) -> bytes:
    return value[: -value[-1]]


def _aes_encrypt(key: bytes, value: bytes) -> bytes:
    encryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).encryptor()
    return encryptor.update(_pkcs7(value)) + encryptor.finalize()


def _aes_decrypt(key: bytes, value: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).decryptor()
    return _unpkcs7(decryptor.update(value) + decryptor.finalize())


def _rsa_wrap(key: bytes) -> bytes:
    padding = bytearray()
    while len(padding) < 125 - len(key):
        byte = os.urandom(1)[0]
        if byte:
            padding.append(byte)
    encoded = bytes([0, 2]) + bytes(padding) + bytes([0]) + key
    number = pow(
        int.from_bytes(encoded, "big"),
        _PUBLIC_NUMBERS.e,
        _PUBLIC_NUMBERS.n,
    )
    return number.to_bytes(128, "big")


def _pack(payload: dict[str, Any]) -> dict[str, str]:
    encoded_data = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()
    plaintext = json.dumps(
        {
            "data": encoded_data,
            **KEY_DATA,
            "platform": 2,
            "timeStamp": int(time.time()),
        },
        separators=(",", ":"),
    ).encode()
    request_key = bytes(0x41 + byte % 26 for byte in os.urandom(16))
    return {
        "d": base64.b64encode(_aes_encrypt(request_key, plaintext)).decode(),
        # MD5 is required only as a wire-protocol checksum, not for security.
        "h": hashlib.md5(plaintext, usedforsecurity=False).hexdigest(),
        "k": base64.b64encode(_rsa_wrap(request_key)).decode(),
        "p": "101",
        "t": "0",
    }


def _decode_response(response: dict[str, Any]) -> dict[str, Any]:
    if "r" not in response:
        return response
    plaintext = _aes_decrypt(SESSION_KEY, base64.b64decode(response["r"]))
    return json.loads(base64.b64decode(json.loads(plaintext)["data"]))


class PrivateCloudClient:
    """Thread-safe, read-only client for private map endpoints."""

    def __init__(
        self,
        device_id: str,
        *,
        tokens: PrivateTokens | None = None,
        uid: str = "",
    ) -> None:
        self.device_id = device_id
        self.tokens = tokens or PrivateTokens("", "")
        self.uid = uid
        self._lock = threading.RLock()

    @property
    def host(self) -> str:
        region = canonical_region(self.tokens.region)
        return MOWER_HOSTS.get(region, MOWER_HOSTS["fra"])[0]

    def authenticate(self, username: str, password: str) -> None:
        self.tokens = passport_login(username, password)
        self.mower_login()

    def _common(self, *, access_token: str = "", uid: str = "") -> dict[str, Any]:
        return {
            "manufacturer": "samsung_samsung_SM-G930F",
            "systemVersion": OS_VERSION,
            "platform": "and",
            "uid": uid,
            "device_id": self.device_id,
            "client_ver": APP_VERSION,
            "language": "en",
            "access_token": access_token,
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"https://{self.host}{path}",
            data=json.dumps(_pack(payload), separators=(",", ":")).encode(),
            headers={"Content-Type": "text/html", "ninebot-version": "1"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return _decode_response(json.loads(response.read()))
        except urllib.error.HTTPError as err:
            try:
                return _decode_response(json.loads(err.read()))
            except Exception as inner:
                raise PrivateCloudError(err.code, "Private-cloud HTTP error") from inner
        except urllib.error.URLError as err:
            raise PrivateCloudError("network", str(err.reason)) from err

    def mower_login(self) -> None:
        field = {
            "uuid": self.tokens.uuid,
            "token": self.tokens.access_token,
            "refresh_token": self.tokens.refresh_token,
            "region": self.tokens.region,
        }
        result = self._post("/user/user/login", {**field, **self._common()})
        uid = (
            (result.get("data") or {}).get("uid") if isinstance(result, dict) else None
        )
        if not uid:
            raise PrivateCloudAuthError(
                result.get("code") if isinstance(result, dict) else "login",
                "Private mower login returned no user id",
            )
        self.uid = str(uid)

    def _reauthenticate(self) -> None:
        self.tokens = passport_refresh(self.tokens)
        self.mower_login()

    def call(self, path: str, extra: dict[str, Any] | None = None) -> Any:
        with self._lock:
            if not self.uid:
                self._reauthenticate()
            body = self._common(access_token=self.tokens.access_token, uid=self.uid)
            body.update(extra or {})
            result = self._post(path, body)
            code = result.get("code") if isinstance(result, dict) else None
            if code == 1:
                return result.get("data")
            if code in _AUTH_ERROR_CODES:
                self._reauthenticate()
                body = self._common(access_token=self.tokens.access_token, uid=self.uid)
                body.update(extra or {})
                result = self._post(path, body)
                if isinstance(result, dict) and result.get("code") == 1:
                    return result.get("data")
            description = (
                str(result.get("desc") or "")
                if isinstance(result, dict)
                else str(result)
            )
            if code in _AUTH_ERROR_CODES:
                raise PrivateCloudAuthError(code, description)
            raise PrivateCloudError(code, description)

    def auth_list(self) -> list[dict[str, Any]]:
        data = self.call("/vehicle/vehicle/auth-list")
        return data if isinstance(data, list) else (data or {}).get("list") or []

    def location(self, serial: str, vehicle_type: int = 3) -> dict[str, Any]:
        return (
            self.call(
                "/vehicle/vehicle/get-location",
                {"vehicle_sn": serial, "vehicle_type": vehicle_type},
            )
            or {}
        )

    def map_list(self, serial: str) -> Any:
        return self.call("/map/index/map-list", {"vehicle_sn": serial})

    def map_detail(self, serial: str, map_id: str, map_base_id: str) -> Any:
        return self.call(
            "/map/index/map-detail",
            {
                "vehicle_sn": serial,
                "map_id": map_id,
                "map_base_id": map_base_id,
            },
        )

    def session_state(self) -> dict[str, str]:
        """Return updated non-password session material for persistence."""
        return {
            "access_token": self.tokens.access_token,
            "refresh_token": self.tokens.refresh_token,
            "uuid": self.tokens.uuid,
            "region": self.tokens.region,
            "uid": self.uid,
            "device_id": self.device_id,
        }

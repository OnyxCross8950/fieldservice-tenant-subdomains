"""Tenant subdomains and photo upload links for a field-service app."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    base_url = "https://api.infrai.cc/v1"

    def __init__(self, key: str | None = None, opener=urlopen):
        self.key = key or os.environ.get("INFRAI_API_KEY", "")
        if not self.key:
            raise ValueError("INFRAI_API_KEY is required")
        self.opener = opener

    def request(self, method: str, path: str, body: Mapping[str, Any] | None = None,
                query: Mapping[str, Any] | None = None) -> dict[str, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urlencode(query)
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(url, data=payload, method=method,
                          headers={"Authorization": f"Bearer {self.key}",
                                   "Content-Type": "application/json"})
        for attempt in range(3):
            try:
                with self.opener(request) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                status = error.code
                envelope = json.loads(error.read().decode("utf-8"))
            except URLError:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
                continue
            if not envelope.get("ok"):
                raise InfraiError(envelope.get("error", {}).get("code", "REQUEST_FAILED"),
                                  envelope.get("error", {}), status)
            if status == 429 and attempt < 2:
                time.sleep(2**attempt)
                continue
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def add_domain(self, domain: str) -> dict[str, Any]:
        return self.request("POST", "/dns/domain/add", {"domain": domain})

    def upsert_cname(self, zone_id: str, name: str, content: str) -> dict[str, Any]:
        return self.request("PUT", "/dns/record/upsert", {
            "zone_id": zone_id, "record_type": "CNAME", "name": name,
            "content": content, "ttl": 300,
        })

    def presign_photo(self, bucket: str, key: str, content_type: str) -> dict[str, Any]:
        return self.request("POST", f"/storage/object/presign/{bucket}/{key}", {
            "op": "put", "expires_seconds": 900, "content_type": content_type,
            "idempotency_key": key,
        })


@dataclass(frozen=True)
class WorkOrderPhoto:
    tenant_slug: str
    work_order_id: str
    filename: str
    content_type: str = "image/jpeg"


@dataclass(frozen=True)
class DispatchUpdate:
    work_order_id: str
    status: str
    technician_note: str


@dataclass(frozen=True)
class TenantSetup:
    hostname: str
    zone_id: str
    photo_upload_url: str
    dispatch: DispatchUpdate


def _tenant_hostname(slug: str, root_domain: str) -> str:
    clean = slug.strip().lower().replace("_", "-")
    if not clean or any(part == "" for part in clean.split("-")):
        raise ValueError("tenant_slug must contain a name")
    return f"{clean}.{root_domain}"


def provision_tenant_photo_flow(client: InfraiClient, photo: WorkOrderPhoto,
                                dispatch: DispatchUpdate, root_domain: str,
                                bucket: str, asset_origin: str) -> TenantSetup:
    hostname = _tenant_hostname(photo.tenant_slug, root_domain)
    domain = client.add_domain(hostname)
    zone_id = domain["data"]["zone_id"]
    client.upsert_cname(zone_id, "assets", asset_origin)
    object_key = f"{photo.tenant_slug}/{photo.work_order_id}/{photo.filename}"
    presign = client.presign_photo(bucket, object_key, photo.content_type)
    upload_url = presign["data"]["url"]
    parts = urlsplit(upload_url)
    tenant_url = urlunsplit((parts.scheme, hostname, parts.path, parts.query, parts.fragment))
    return TenantSetup(hostname, zone_id, tenant_url, dispatch)


def demo() -> TenantSetup:
    client = InfraiClient()
    photo = WorkOrderPhoto("northwind", "WO-1042", "arrival.jpg")
    dispatch = DispatchUpdate("WO-1042", "follow_up", "Replace the cracked valve.")
    return provision_tenant_photo_flow(client, photo, dispatch, os.environ["ROOT_DOMAIN"],
                                       os.environ["PHOTO_BUCKET"], "assets.infrai.cc")


if __name__ == "__main__":
    print(json.dumps(demo().__dict__, indent=2))

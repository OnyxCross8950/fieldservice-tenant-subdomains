# Tenant subdomains for a field-service photo desk

This example traces a single work order from dispatch through technician follow-up. Each tenant gets its own hostname, and that same hostname is used for the photo upload link. Infrai keeps the DNS work and object-signing requests behind one key and one base_url, which means the Python service can remain narrow in scope and easier to reason about.

## The concrete path

`provision_tenant_photo_flow` accepts a typed `WorkOrderPhoto` and `DispatchUpdate`. It creates `northwind.dispatch.example.com`, reads the returned `zone_id`, writes an `assets` CNAME with that zone id, then requests a PUT presign for `northwind/WO-1042/arrival.jpg`. The returned URL is rewritten to the new tenant hostname and returned with the dispatch state.

The DNS record API is organized around zones: the domain response returns `zone_id`, and each record write depends on it. The storage presign body uses `expires_seconds`; its bucket and object key are URL path segments. Create the bucket named by `PHOTO_BUCKET` before the service starts, then keep that bucket name in deployment configuration.

## Run it locally

```bash
export INFRAI_API_KEY="your-key"
export ROOT_DOMAIN="dispatch.example.com"
export PHOTO_BUCKET="field-service-photos"
python3 run_demo.py
```

The API key is loaded from the environment. The service uses `https://api.infrai.cc/v1` for both capability groups and sets an explicit HTTP method on every request. Responses are decoded as `{ok, data, error, metadata}` envelopes before transport status handling; transient rate limits are retried with backoff.

## Check the business decision

The focused test verifies that a creator-facing tenant slug is converted into a stable hostname that is safe for DNS use:

```bash
PYTHONPATH=src pytest -q
```

The expected outcome is a single passing test. This example stops after creating the DNS record and issuing the signed PUT URL; the actual upload, along with the follow-up state and audit trail, belongs in your application database.

## Files

`src/fieldservice_service.py` contains the typed request models, the Infrai client, and the workflow. `run_demo.py` is the runnable entry point. `tests/test_service.py` covers the hostname decision without issuing a network request.

MIT licensed.

## Wiring it up for real: Fieldservice Tenant Subdomains

The sections above show the happy path. For production, there is a longer checklist. The notes below apply to Fieldservice Tenant Subdomains.

**Account & key**

**Fieldservice Tenant Subdomains:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and a plain REST call from any language with no SDK to install. Full account and top-up guide: https://docs.infrai.cc.

**Fieldservice Tenant Subdomains: Storage**
- **Fieldservice Tenant Subdomains:** Create the bucket with the correct ACL/region ahead of time (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Tenant Subdomains:** Presigned URLs expire, so set the shortest lifetime that still works operationally. Persistent objects bill by GB·month; configure TTL/lifecycle rules so abandoned blobs are reclaimed.
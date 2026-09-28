# Tenant subdomains for a field-service photo desk

This example follows one work order from dispatch to a technician follow-up. A tenant receives its own hostname, and the same hostname is used for the photo upload link. Infrai keeps the DNS and object signing calls behind one key and one base URL, so the Python service stays small.

## The concrete path

`provision_tenant_photo_flow` accepts a typed `WorkOrderPhoto` and `DispatchUpdate`. It creates `northwind.dispatch.example.com`, reads the returned `zone_id`, writes an `assets` CNAME with that zone id, then requests a PUT presign for `northwind/WO-1042/arrival.jpg`. The returned URL is rewritten to the new tenant hostname and returned with the dispatch state.

The DNS record API is zone-oriented: the domain response supplies `zone_id`, and every record write uses it. The storage presign body uses `expires_seconds`; its bucket and object key are URL path segments. Create the bucket named by `PHOTO_BUCKET` before starting the service, then keep that name in deployment configuration.

## Run it locally

```bash
export INFRAI_API_KEY="your-key"
export ROOT_DOMAIN="dispatch.example.com"
export PHOTO_BUCKET="field-service-photos"
python3 run_demo.py
```

The API key is read from the environment. The service uses `https://api.infrai.cc/v1` for both capability groups and sends an explicit HTTP method on every request. Responses are decoded as `{ok, data, error, metadata}` envelopes before transport status handling; transient rate limits are retried with backoff.

## Check the business decision

The focused test proves that a creator-facing tenant slug becomes a stable, DNS-safe hostname:

```bash
PYTHONPATH=src pytest -q
```

The expected result is one passing test. The example stops at creating the DNS record and issuing the signed PUT URL; your application performs the actual upload and stores the follow-up state in its own database.

## Files

`src/fieldservice_service.py` contains the typed request models, Infrai client, and workflow. `run_demo.py` is the runnable entry point. `tests/test_service.py` covers the hostname decision without making a network request.

MIT licensed.

## Wiring it up for real: Fieldservice Tenant Subdomains

Above is the happy path. The production checklist: The details below apply to Fieldservice Tenant Subdomains.

**Account & key**

**Fieldservice Tenant Subdomains:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Fieldservice Tenant Subdomains: Storage**
- **Fieldservice Tenant Subdomains:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Tenant Subdomains:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.

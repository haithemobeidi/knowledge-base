---
stack: [cloudflare-r2, s3-compatible, presigned-urls, aws4fetch, node]
kind: gotcha
last_verified: 2026-07-22
---

# R2 presigned-PUT size/type limits ARE enforceable — but aws4fetch silently unsigns them

Any app that lets clients upload straight to Cloudflare R2 via presigned PUT
URLs (the standard "server never proxies the bytes" pattern) eventually needs
to cap upload size and content type — otherwise a signed-in client gets a
free window to park objects of any size on your paid bucket.

Two layers of misinformation make this look impossible, and one library trap
makes a working fix silently decorative. All three claims below were
**measured against a live R2 bucket** (2026-07-22), not inferred.

## The misleading landscape

1. **S3's official answer doesn't exist on R2.** On AWS S3 you'd use a POST
   policy with a `content-length-range` condition. R2 does not support POST
   object uploads, so every S3 tutorial dead-ends.
2. **Community consensus says "impossible."** Cloudflare community threads on
   this exact question conclude R2 presigned PUTs can't bound size and
   recommend fronting the bucket with a Worker. This is **wrong** — see below.

## What actually works

SigV4 lets you include headers in the signature. R2 **does verify** signed
`Content-Length` and `Content-Type` on a query-signed (presigned) PUT — a
request whose actual body size or MIME type differs from what was signed is
rejected with `403 SignatureDoesNotMatch` before any bytes land. Measured
matrix:

```
signed len=10,   body=10                    → 200
signed len=10,   body=100                   → 403 SignatureDoesNotMatch
signed type=jpeg, sent type=jpeg            → 200
signed type=jpeg, sent type=text/plain      → 403
signed type=jpeg, header omitted            → 403
```

So the server-side presign flow becomes: client declares `{size, contentType}`
→ server validates against per-kind caps → server signs BOTH into the URL →
the cap now binds the actual bytes, not the client's claim. No Worker needed.

## The trap: aws4fetch drops these headers from the signature by default

aws4fetch (the zero-dependency SigV4 signer commonly used with R2) keeps an
internal *unsignable headers* list that includes `content-length` and
`content-type`. Pass them in `headers` and it signs the request **without
them** — no warning, no error. `X-Amz-SignedHeaders` in the produced URL says
`host`, every upload succeeds regardless of size, and your "limit" is
decorative. A naive verification pass even *passes*: match-PUT works,
mismatch-PUT also works, and if you only test the happy path you ship it.

The fix is one option:

```js
const signed = await client.sign(url, {
  method: 'PUT',
  headers: { 'content-length': String(size), 'content-type': contentType },
  aws: { signQuery: true, allHeaders: true },   // ← allHeaders is the fix
});
```

The uploader must then send exactly those headers (most HTTP clients set
`Content-Length` automatically from the body; set `Content-Type` explicitly).

## Verification protocol (the transferable lesson)

1. **Read `X-Amz-SignedHeaders` in the URL you minted.** If it doesn't list
   `content-length`/`content-type`, they are not enforced, whatever your
   signing code appears to say. This is a one-line assert worth keeping in a
   test.
2. **Test the MISMATCH case, not the match case.** A signed-limits scheme that
   only ever sees compliant clients proves nothing — the entire point is the
   403 on a lying client. (This is what caught the aws4fetch trap: the first
   probe run "passed" 6/6 because nothing was actually signed.)

## Companion guard: quota that can't be outrun

Signed sizes bound each object; a per-user quota bounds the total. If the
server caches R2 usage (ListObjectsV2 sums) with a TTL, bump the cached figure
by each approved presign's **declared** size immediately — otherwise a burst of
presigns inside one TTL window sails past the quota before the next listing
sees the bytes.

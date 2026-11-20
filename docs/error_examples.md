# Error handling examples

Captured from a local run (`uvicorn app.main:app --port 4000`). Redirects to internal addresses are covered by `test_redirect_to_internal_address_is_blocked`.

```
$ curl -X POST http://localhost:4000/link-analysis -d '{"url":"https://stripe.com"}'
{"success":true,"website":"https://stripe.com","brand":{"name":"Stripe","category":"Financial Infrastructure & Payment Processing","summary":"Stripe is a global technology company that builds economic infrastructure ... (served from cache)
```

```
$ curl -X POST http://localhost:4000/link-analysis -d '{"url":"http://localhost:8080/admin"}'
{"success":false,"error":"Invalid URL","detail":"Access to this host is not allowed"}
[HTTP 400 in 0.002096s]
```

```
$ curl -X POST http://localhost:4000/link-analysis -d '{"url":"http://169.254.169.254/latest/meta-data"}'
{"success":false,"error":"Invalid URL","detail":"Access to private or internal network addresses is not allowed"}
[HTTP 400 in 0.001489s]
```

```
$ curl -X POST http://localhost:4000/link-analysis -d '{"url":"ftp://example.com"}'
{"success":false,"error":"Invalid URL","detail":"Only HTTP and HTTPS URLs are allowed"}
[HTTP 400 in 0.001371s]
```

```
$ curl -X POST http://localhost:4000/link-analysis -d '{"url":"https://this-domain-does-not-exist-12345.com"}'
{"success":false,"error":"Invalid URL","detail":"Cannot resolve host: this-domain-does-not-exist-12345.com"}
[HTTP 400 in 0.153591s]
```

```
$ curl -X POST http://localhost:4000/link-analysis -d '{"url":"https://httpbin.org/status/404"}'
{"success":false,"error":"Website could not be fetched","detail":"Website returned HTTP 404. The page may be restricted, missing or blocking automated access."}
[HTTP 502 in 1.025519s]
```

```
$ curl -X POST http://localhost:4000/link-analysis -d '{}'
{"success":false,"error":"Validation error","detail":"body.url: Field required"}
[HTTP 422 in 0.002404s]
```

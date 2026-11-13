# API

> Contract first: write the endpoint here, then implement it. Judges and teammates read this.

## Conventions

- Base URL: `http://localhost:3000/api` (local), `APP_URL + /api` elsewhere.
- JSON in, JSON out; `Content-Type: application/json`.
- Auth: `Authorization: Bearer <token>` (replace if different).
- Timestamps: ISO 8601 UTC.
- Errors: non-2xx with `{ "error": { "code": "SNAKE_CASE", "message": "human readable" } }`.
- Pagination: `?limit=&cursor=` returning `{ "items": [], "nextCursor": null }`.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | no | Liveness, returns `{ "ok": true }` |
| GET | `/items` | yes | List items |
| POST | `/items` | yes | Create item |
| GET | `/items/:id` | yes | Read one |
| PATCH | `/items/:id` | yes | Update |
| DELETE | `/items/:id` | yes | Delete |

## Example

```http
POST /api/items
Authorization: Bearer <token>
Content-Type: application/json

{ "title": "First item" }
```

```http
201 Created

{ "id": "0f8f...", "title": "First item", "createdAt": "2026-11-13T10:00:00Z" }
```

## Status codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Validation failed (`error.code = VALIDATION_FAILED`) |
| 401 | Missing/invalid token |
| 404 | Not found |
| 409 | Conflict |
| 500 | Unhandled — log with request id |

## OpenAPI

When the surface grows past ~8 endpoints, generate `openapi.yaml` from the code and link it here.

# API reference

All endpoints are JSON over HTTP on port 8000. FastAPI also serves an interactive schema at `/docs` and the raw OpenAPI spec at `/openapi.json`.

Errors use FastAPI's standard shape: `{"detail": "<message>"}`. Request-body validation failures (wrong types, unknown `format`) return `422` with FastAPI's detailed error list.

## Accepted URL forms

Anywhere a `url` is accepted, any of these work (whitespace is stripped, `http`/`https` and any `*.youtube.com` subdomain are fine, extra query params are ignored):

- `https://www.youtube.com/watch?v=ID`
- `https://youtu.be/ID`
- `https://www.youtube.com/shorts/ID`
- `https://www.youtube.com/embed/ID`
- `https://www.youtube.com/live/ID`
- A bare 11-character video ID (`[A-Za-z0-9_-]{11}`)

Anything else returns `400 "Not a valid YouTube URL or video ID"`.

---

## `POST /api/info`

Fetch video metadata without downloading.

**Request**
```json
{ "url": "https://youtu.be/dQw4w9WgXcQ" }
```

**200 Response**
```json
{
  "id": "dQw4w9WgXcQ",
  "title": "…",
  "duration": 212.0,
  "thumbnail": "https://…",
  "uploader": "…"
}
```

| Status | When |
|---|---|
| 400 | URL isn't a recognisable YouTube URL/ID |
| 502 | yt-dlp failed (private/removed video, live stream with no duration, YouTube blocking). `detail` holds yt-dlp's cleaned-up message. |

---

## `POST /api/jobs`

Start a conversion. Returns immediately; poll for progress.

**Request**
```json
{ "url": "dQw4w9WgXcQ", "format": "mp3", "start": 30, "end": 75.5 }
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `url` | string | required | See accepted forms above |
| `format` | `"mp3"` \| `"m4a"` \| `"wav"` | `"mp3"` | |
| `start` | number \| null | `null` | Seconds. Must be `>= 0`. |
| `end` | number \| null | `null` | Seconds. Must be `> 0` and `> start`. Clamped to the video length at run time. |

**202 Response**: a [Job object](#job-object) with `status: "queued"`.

| Status | When |
|---|---|
| 400 | Invalid URL, or `"Invalid trim range"` |
| 422 | Body fails schema validation (e.g. `format: "flac"`) |

---

## `GET /api/jobs/{id}`

**200**: a [Job object](#job-object). **404**: unknown ID (including any job from before the last restart).

---

## `GET /api/jobs/{id}/file`

Download the finished audio. The filename is the video title, keeping only letters, digits, spaces, `-`, `_` and `.`, capped at 80 characters (falling back to `audio`), plus the extension.

| Status | When |
|---|---|
| 200 | Audio file |
| 404 | Unknown job |
| 409 | Job isn't `done` yet (or failed) |

---

## Job object

```json
{
  "id": "6f1c…",
  "status": "downloading",
  "progress": 42,
  "title": "…",
  "duration": 212.0,
  "format": "mp3",
  "error": null,
  "created_at": "2026-10-17T13:28:44.123456Z"
}
```

`status` is one of `queued`, `fetching`, `downloading`, `processing`, `done`, `error`. `title`/`duration` are `null` until the `fetching` stage completes. `error` is set only when `status` is `error`; unexpected internal failures surface as the generic `"Processing failed"` (the traceback goes to the server log). See [Architecture → Job lifecycle](architecture.md#job-lifecycle) for how `progress` maps to stages.

## Example: curl end-to-end

```sh
id=$(curl -s localhost:8000/api/jobs -H 'Content-Type: application/json' \
  -d '{"url":"dQw4w9WgXcQ","format":"m4a","start":0,"end":30}' | jq -r .id)

until curl -s localhost:8000/api/jobs/$id | jq -e '.status=="done" or .status=="error"' >/dev/null; do sleep 1; done

curl -OJ localhost:8000/api/jobs/$id/file
```

Next: [Development guide](development.md).

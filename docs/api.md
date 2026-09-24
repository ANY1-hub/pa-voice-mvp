# API reference

All routes below are under the FastAPI app. JWT routes require:

```http
Authorization: Bearer <access_token>
```

Token lifetime: **24 hours**. User IDs are server-generated UUID v4 values.

## Auth

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/auth/bootstrap-status` | Public – `{ needs_bootstrap: bool }` |
| POST | `/api/v1/auth/register` | Only when 0 users; first user = SuperUser |
| POST | `/api/v1/auth/login` | Returns access token; **429** after repeated failures |
| GET | `/api/v1/auth/me` | Current user (`must_change_password`, `display_name`, `timezone`) |
| POST | `/api/v1/auth/change-password` | Change password; clears `must_change_password` |
| POST | `/api/v1/auth/display-name` | Set preferred name (how Jarvis should address the user) |
| POST | `/api/v1/auth/timezone` | Store browser IANA timezone for local reminder clocks |

Public registration is closed after the first SuperUser; further accounts only via Admin API. Admin-created users must change password on first login, then set `display_name` before chat.

## Admin (SuperUser only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/users` | List users |
| POST | `/api/v1/admin/users` | Create user (optional `is_superuser`) |
| PATCH | `/api/v1/admin/users/{user_id}` | Update `is_active` / `is_superuser` |

## Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/text` | Text message → Memory context → LLM → TTS |
| POST | `/api/v1/chat/voice` | Audio upload → STT → Memory → LLM → TTS; **413** over 10 MB (before parse) |

Both require `Authorization: Bearer <token>`.

### `POST /api/v1/chat/text` — JSON body (`TextChatRequest`)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `text` | string | yes | Length 1–4000 |
| `language` | string \| null | no | Default `null`. Max length 8. Forced chat language when set (typically `en` / `de` / `hu`); omit for auto-detect |
| `gui_language` | `"en"` \| `"de"` \| `"hu"` \| null | no | Default `null`. Help-flag / GUI language for weak-path fallback only. Empty string is rejected |

### `POST /api/v1/chat/voice` — multipart form

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `audio` | file | yes | wav / webm / …; empty body → 400; over 10 MB → 413 before full parse |
| `language` | string \| null | no | Default omit/`null`. Forced chat language when set (typically `en` / `de` / `hu`) |
| `gui_language` | string \| null | no | Default omit/`null`. Must be exactly `en`, `de`, or `hu` when present (else 422) |

### Response (`ChatResponse`) — text and voice

| Field | Type | Notes |
|-------|------|-------|
| `transcript` | string | Sanitized user utterance |
| `response` | string | Assistant reply text |
| `audio_base64` | string \| null | Optional base64 TTS audio |
| `correlation_id` | string \| null | UUID v4 for this turn |
| `status` | string | Default `"ok"`; `"error"` when the turn failed |
| `error_type` | string \| null | `"llm"` / `"tts"` when that stage failed |
| `duration_ms` | number | Wall time of the turn (default `0.0`) |
| `tokens` | integer \| null | Prompt + completion usage when the LLM reported it |

## Notes / Reminders / Skills / Memory

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/notes` | List notes for the current user |
| GET | `/api/v1/reminders` | List reminders for the current user |
| GET | `/api/v1/reminders/due` | Due reminders (open-tab poll + TTS) |
| POST | `/api/v1/reminders/{reminder_id}/ack` | Acknowledge a delivered reminder |
| GET | `/api/v1/skills/phrases` | Spoken trigger phrases (EN/DE/HU) |
| POST | `/api/v1/memory/working` | Write working-memory item |
| GET | `/api/v1/memory/working` | List working-memory items |
| POST | `/api/v1/memory/semantic` | Write semantic-memory fact |
| GET | `/api/v1/memory/semantic` | Search / list semantic facts |

Memory and chat routes are tenant-isolated via JWT `user_id` (see `docs/decisions/001-dependency-injection-memory.md`).

## Health

`GET /health` cheap-pings Mongo and returns **200** `status: ok` only when the DB is reachable; otherwise **503** with an honest non-ok status (no secrets in the body).

Skill trigger phrases (EN / DE / HU) for Notes, Reminders, Web Search and Active Recall: [docs/user-guide.md](user-guide.md).

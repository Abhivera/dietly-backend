# Dietly API — Frontend Reference

Base URL (local): `http://localhost:8000`  
API prefix: `/api/v1`  
Interactive docs: `/docs`  
Static uploads: `/media/...`

---

## Authentication

Most routes require a JWT from login or register.

```http
Authorization: Bearer <access_token>
```

| Endpoint | Auth |
|----------|------|
| `POST /api/v1/auth/register` | No |
| `POST /api/v1/auth/login` | No |
| `POST /api/v1/public/analyze-food` | No (IP rate limit) |
| `GET /`, `GET /health`, `GET /health/db` | No |
| Everything else under `/api/v1` | Yes |
| `/api/v1/admin/*` | Yes + `role: "admin"` |

Token lifetime is configured by `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 7 days).

---

## Error responses

All HTTP errors use this shape:

```json
{
  "detail": "Human-readable or structured error",
  "message": "Same as detail when detail is a string, else generic text"
}
```

**422 validation** — `detail` is an array of FastAPI error objects:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "..."
    }
  ],
  "message": "Request validation failed"
}
```

Common status codes: `400`, `401`, `403`, `404`, `409`, `422`, `500`, `503`.

---

## Auth

### Register

`POST /api/v1/auth/register`

**Request body**

```json
{
  "email": "user@example.com",
  "password": "minimum8chars",
  "full_name": "Optional Name"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `email` | string (email) | yes | Stored lowercased |
| `password` | string | yes | 8–128 chars |
| `full_name` | string | no | Max 100; defaults from email local-part |

**Response `201`**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:** `409` — email already registered.

---

### Login

`POST /api/v1/auth/login`

**Request body**

```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response `200`**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:** `401` — invalid email or password.

---

## Current user (`/users/me`)

### Get profile

`GET /api/v1/users/me`

**Response `200`**

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "Jane",
  "avatar_url": "http://127.0.0.1:8000/media/...",
  "role": "user",
  "gender": null,
  "age": 28,
  "weight": 65,
  "height": 170,
  "goal_weight": 60,
  "step_goal": 8000,
  "created_at": "2026-05-20T10:00:00Z",
  "updated_at": "2026-05-20T12:00:00Z"
}
```

---

### Update profile

`PUT /api/v1/users/me`

Send only fields to change.

**Request body** (all optional)

```json
{
  "full_name": "Jane Doe",
  "avatar_url": "https://...",
  "gender": "female",
  "age": 28,
  "weight": 65,
  "height": 170,
  "goal_weight": 60
}
```

**Response `200`:** same shape as `GET /users/me`.

---

### Update step goal

`PATCH /api/v1/users/me/step-goal`

**Request body**

```json
{
  "step_goal": 10000
}
```

`step_goal`: integer, 1000–100000.

**Response `200`:** `UserResponse`.

---

### Upload avatar

`POST /api/v1/users/me/avatar`

**Content-Type:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | image file | yes |

**Response `200`:** `UserResponse` with updated `avatar_url`.

**Errors:** `400` — not an image.

---

### Meal logging streak

`GET /api/v1/users/me/streak`

Consecutive UTC days with at least one meal image (`is_meal: true`). Steps do not affect streak.

**Response `200`**

```json
{
  "current_streak": 5,
  "longest_streak": 12,
  "last_logged_date": "2026-05-19",
  "streak_days": 5
}
```

`streak_days` is a computed alias of `current_streak`.

---

### Net calories (one day)

`GET /api/v1/users/me/net-calories?date=2026-05-20`

| Query | Type | Default | Notes |
|-------|------|---------|-------|
| `date` | `YYYY-MM-DD` | today (UTC) | Cannot be in the future |

**Response `200`**

```json
{
  "date": "2026-05-20",
  "calories_eaten": 1850,
  "calories_burned_manual": 300,
  "calories_burned_steps": 120,
  "calories_burned_total": 420,
  "net_calories": 1430
}
```

- **Eaten:** sum of `estimated_calories` on meal images (`is_meal`) created that UTC day.
- **Manual burn:** `user_calories.total_burned` for that day (0 if no row).
- **Steps burn:** `daily_steps.kcal_burned` for that day (0 if no sync).

---

## Food images

### Shared: `Image` object

Returned by upload, list, detail, relog, and meal summary.

```json
{
  "id": 42,
  "filename": "uuid.jpg",
  "original_filename": "lunch.jpg",
  "file_url": "http://127.0.0.1:8000/media/users/1/...",
  "s3_key": "users/1/...",
  "s3_bucket": "local",
  "file_size": 245000,
  "content_type": "image/jpeg",
  "description": "Optional text",
  "tags": null,
  "owner_id": 1,
  "created_at": "2026-05-20T12:00:00+00:00",
  "updated_at": null,
  "analysis": {
    "is_food": true,
    "is_meal": true,
    "meal_name": "Grilled chicken salad",
    "food_items": ["chicken", "lettuce", "tomato"],
    "description": "A balanced lunch plate...",
    "calories": 450,
    "nutrients": {
      "protein": 35,
      "carbs": 20,
      "fat": 18,
      "sugar": 5
    },
    "confidence": 0.85,
    "completed_at": "2026-05-20T12:00:05+00:00",
    "exercise_recommendations": {
      "steps": 9000,
      "walking_km": 9.0
    }
  }
}
```

---

### Upload and analyze (log meal)

`POST /api/v1/images/upload-and-analyze`

**Content-Type:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | image | yes |
| `description` | string | no | Extra context for the vision model |

**Response `200`**

```json
{
  "success": true,
  "image": { "...": "Image object above" },
  "user_description": "optional, echoed if sent"
}
```

**Errors:** `400` invalid image; `503` upload/analysis unavailable.

---

### List images

`GET /api/v1/images?skip=0&limit=20&date=2026-05-20`

Provide **at most one** of `date`, `week`, or `month`:

| Query | Format | Example |
|-------|--------|---------|
| `date` | `YYYY-MM-DD` | `2026-05-20` |
| `week` | `YYYY-Www` | `2026-W21` |
| `month` | `YYYY-MM` | `2026-05` |

**Response `200`**

```json
{
  "images": [ { "...": "Image" } ],
  "total": 3,
  "skip": 0,
  "limit": 20
}
```

Note: `total` is the count of items in the current page, not full DB total.

---

### Get one image

`GET /api/v1/images/{image_id}`

**Response `200`:** `Image` object.  
**Errors:** `404`.

---

### Fresh presigned URL

`GET /api/v1/images/{image_id}/fresh-url?expiration=3600`

**Response `200`:** `Image` object; `file_url` is replaced with a fresh presigned URL when storage is private.

---

### Suggested meal name

`GET /api/v1/images/{image_id}/suggested-name`

**Response `200`**

```json
{
  "meal_name": "Grilled chicken salad"
}
```

---

### Relog meal (duplicate row, same file)

`POST /api/v1/images/{image_id}/relog`

**Response `200`**

```json
{
  "success": true,
  "image": { "...": "new Image row" }
}
```

**Errors:** `404` not found; `400` no completed analysis.

---

### Toggle meal flag

`PATCH /api/v1/images/is-meal/{image_id}`

**Request body**

```json
{
  "is_meal": true
}
```

Only allowed when `analysis.is_food` is `true`.

**Response `200`**

```json
{
  "success": true,
  "image_id": 42,
  "is_meal": true
}
```

---

### Delete image

`DELETE /api/v1/images/{image_id}`

**Response `200`**

```json
{
  "success": true,
  "message": "Image deleted successfully"
}
```

---

## Meal summary

`GET /api/v1/meal/?date=2026-05-20`

Same date filters as image list (`date`, `week`, or `month` — one only).

Includes only images where `analysis.is_meal` is true.

**Response `200`**

```json
{
  "total_meals": 3,
  "total_calories": 1350,
  "total_exercise": {
    "steps": 27000,
    "walking_km": 27.0
  },
  "meals": [ { "...": "Image" } ]
}
```

---

## Activity calories (manual burn)

### Activity types (`log-activity`)

`walking` | `running` | `cycling` | `swimming` | `yoga` | `strength_training`

Calories are computed server-side from MET, user `weight`, and `duration_minutes`.

---

### Log structured activity

`POST /api/v1/user-calories/log-activity`

**Request body**

```json
{
  "activity_type": "running",
  "duration_minutes": 30,
  "activity_date": "2026-05-20"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `activity_type` | yes | See enum above |
| `duration_minutes` | yes | 1–480 |
| `activity_date` | no | Defaults to today (UTC); cannot be future |

Appends to the day row (creates if missing). Duplicate names get suffix `(2)`, `(3)`, etc.

**Response `200`:** `UserCaloriesResponse` (below).

**Errors:** `400` invalid type, future date, or daily total > 5000 kcal.

---

### Create full day entry

`POST /api/v1/user-calories/`

**Request body**

```json
{
  "activity_date": "2026-05-20",
  "calories_burned": [
    { "activity_name": "Morning run", "calories": "320" },
    { "activity_name": "Yoga", "calories": "150" }
  ]
}
```

- `calories` values are **strings** (API validates as integers).
- Activity names must be unique (case-insensitive).
- Daily total cannot exceed 5000.

**Response `200`:** `UserCaloriesResponse`.  
**Errors:** `400` if a row already exists for that date.

---

### List entries

`GET /api/v1/user-calories/?skip=0&limit=100&start_date=2026-05-01&end_date=2026-05-20`

**Response `200`:** array of `UserCaloriesResponse`.

---

### Get by date

`GET /api/v1/user-calories/date/{activity_date}`

`activity_date`: `YYYY-MM-DD`.

**Response `200`:** `UserCaloriesResponse`.  
**Errors:** `404`.

---

### Get by id

`GET /api/v1/user-calories/{calories_id}`

**Response `200`:** `UserCaloriesResponse`.

---

### Update entry

`PUT /api/v1/user-calories/{calories_id}`

**Request body** (all optional)

```json
{
  "activity_date": "2026-05-21",
  "calories_burned": [
    { "activity_name": "Run", "calories": "400" }
  ]
}
```

**Response `200`:** `UserCaloriesResponse`.

---

### Delete entry

`DELETE /api/v1/user-calories/{calories_id}`

**Response `200`**

```json
{
  "success": true,
  "message": "Calorie entry deleted successfully"
}
```

---

### `UserCaloriesResponse`

```json
{
  "id": 10,
  "user_id": 1,
  "activity_date": "2026-05-20",
  "calories_burned": [
    { "activity_name": "Running · 30 min", "calories": "320" }
  ],
  "total_burned": 320,
  "created_at": "2026-05-20T08:00:00Z",
  "updated_at": null
}
```

---

### Burn summary (date range)

`GET /api/v1/user-calories/summary/range?start_date=2026-05-01&end_date=2026-05-20`

**Response `200`**

```json
{
  "total_calories_burned": 2400,
  "average_calories_per_day": 120.0,
  "date_range_start": "2026-05-01",
  "date_range_end": "2026-05-20",
  "entries_count": 8,
  "activities_summary": {
    "Running · 30 min": 960,
    "Walking · 45 min": 400
  }
}
```

---

### Burn summary (recent days)

`GET /api/v1/user-calories/summary/recent?days=7`

`days`: 1–365, default `7`. Same response shape as range summary.

---

## Daily steps (mobile sync)

### Sync batch

`POST /api/v1/daily-steps/sync`

**Request body**

```json
{
  "days": [
    {
      "step_date": "2026-05-20",
      "step_count": 8500,
      "distance_km": 6.2,
      "source": "healthkit"
    }
  ]
}
```

| Field | Notes |
|-------|-------|
| `source` | `"healthkit"` or `"health_connect"` |
| `days` | 1–400 items; unique `step_date` per request |
| `step_count` | 0–200000 |
| `distance_km` | optional, 0–1000 |

**Response `200`:** array of `DailyStepsResponse`:

```json
[
  {
    "id": 1,
    "user_id": 1,
    "step_date": "2026-05-20",
    "step_count": 8500,
    "distance_km": 6.2,
    "kcal_burned": 340,
    "source": "healthkit",
    "synced_at": "2026-05-20T18:00:00Z"
  }
]
```

---

### List step rows (sparse)

`GET /api/v1/daily-steps/?start_date=2026-05-01&end_date=2026-05-20&skip=0&limit=100`

Only dates with synced data appear. For charts, prefer `/steps/summary`.

---

### Get one day (raw)

`GET /api/v1/daily-steps/{step_date}`

**Errors:** `404` if never synced.

---

## Step charts (dense series)

`GET /api/v1/steps/summary?start_date=2026-05-14&end_date=2026-05-20`

| Query | Default | Notes |
|-------|---------|-------|
| `end_date` | today (UTC) | Cannot be future |
| `start_date` | `end_date` | Max range 367 days |

Every calendar day in range is returned. Missing DB rows use zeros.

**Response `200`**

```json
{
  "days": [
    {
      "date": "2026-05-14",
      "steps": 0,
      "kcal_burned": 0,
      "distance_km": 0.0,
      "source": null
    },
    {
      "date": "2026-05-20",
      "steps": 8500,
      "kcal_burned": 340,
      "distance_km": 6.2,
      "source": "healthkit"
    }
  ]
}
```

---

## Public food analysis (no auth)

For landing pages / try-before-signup. Does **not** save images.

`POST /api/v1/public/analyze-food`

**Content-Type:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | image | yes (max 10MB) |
| `description` | string | no |

**Response `200`**

```json
{
  "success": true,
  "analysis": {
    "is_food": true,
    "is_meal": true,
    "meal_name": "Pasta plate",
    "food_items": ["pasta", "sauce"],
    "description": "...",
    "calories": 600,
    "nutrients": { "protein": 20, "carbs": 80, "fat": 15, "sugar": 8 },
    "confidence": 0.9,
    "exercise_recommendations": { "steps": 12000, "walking_km": 12.0 },
    "completed_at": "2026-05-20T12:00:00+00:00",
    "note": "Only when is_food is false"
  },
  "rate_limit": {
    "remaining_requests": 4,
    "limit": 5,
    "period": "24 hours"
  }
}
```

---

## Admin API

Requires `Authorization: Bearer <token>` and user `role: "admin"`.

### Dashboard stats

`GET /api/v1/admin/stats`

**Response `200`**

```json
{
  "total_users": 120,
  "admin_users": 2,
  "total_images": 4500
}
```

---

### List users

`GET /api/v1/admin/users?skip=0&limit=50&email_contains=gmail`

**Response `200`**

```json
{
  "items": [ { "...": "UserResponse" } ],
  "total": 120,
  "skip": 0,
  "limit": 50
}
```

---

### Get user

`GET /api/v1/admin/users/{user_id}`

**Response `200`:** `UserResponse`.

---

### Patch user profile

`PATCH /api/v1/admin/users/{user_id}`

Does not change `email`, password, or `role`.

**Request body** (all optional): `full_name`, `avatar_url`, `gender`, `age`, `weight`, `height`, `goal_weight`, `step_goal`.

---

### Set user role

`PATCH /api/v1/admin/users/{user_id}/role`

**Request body**

```json
{
  "role": "admin"
}
```

`role`: `"user"` | `"admin"`.

---

### Delete user

`DELETE /api/v1/admin/users/{user_id}`

**Response `200`**

```json
{
  "success": true,
  "message": "User 5 deleted."
}
```

Cannot delete your own account (`400`).

---

### List user's images

`GET /api/v1/admin/users/{user_id}/images`

**Response `200`**

```json
{
  "user_id": 5,
  "total": 12,
  "images": [ { "...": "Image-like dict" } ]
}
```

---

### Get any image

`GET /api/v1/admin/images/{image_id}`

**Response `200`:** image detail (any owner).

---

### Delete any image

`DELETE /api/v1/admin/images/{image_id}`

**Response `200`**

```json
{
  "success": true,
  "message": "Image 42 deleted."
}
```

---

## Health (no auth)

| Method | Path | Response |
|--------|------|----------|
| GET | `/` | `{ "message": "Dietly API is running", "docs": "/docs" }` |
| GET | `/health` | `{ "status": "healthy" }` |
| GET | `/health/db` | `{ "status": "healthy", "database": "connected" }` or `503` |

---

## Frontend tips

1. **Store the token** after login/register; attach `Authorization: Bearer ...` on every protected call.
2. **Dates** for streaks, net calories, and meal filters use **UTC calendar days** unless noted.
3. **Image URLs** may expire when using private object storage — call `GET .../fresh-url` before displaying old rows.
4. **Multipart uploads** use `FormData`: `file` plus optional `description` for meal logging and public analyze.
5. **OpenAPI** at `/docs` and `/openapi.json` stay in sync with the server; use them to generate TypeScript clients.

---

## Quick endpoint index

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/auth/register` | Sign up |
| POST | `/api/v1/auth/login` | Sign in |
| GET | `/api/v1/users/me` | Profile |
| PUT | `/api/v1/users/me` | Update profile |
| PATCH | `/api/v1/users/me/step-goal` | Step target |
| POST | `/api/v1/users/me/avatar` | Avatar upload |
| GET | `/api/v1/users/me/streak` | Streak |
| GET | `/api/v1/users/me/net-calories` | Daily net kcal |
| POST | `/api/v1/images/upload-and-analyze` | Log meal photo |
| GET | `/api/v1/images` | Image history |
| GET | `/api/v1/images/{id}` | Image detail |
| GET | `/api/v1/images/{id}/fresh-url` | Refresh URL |
| PATCH | `/api/v1/images/is-meal/{id}` | Mark meal |
| DELETE | `/api/v1/images/{id}` | Delete image |
| GET | `/api/v1/meal/` | Meal summary |
| POST | `/api/v1/user-calories/log-activity` | Quick activity log |
| GET | `/api/v1/user-calories/summary/recent` | Burn stats |
| POST | `/api/v1/daily-steps/sync` | Sync steps |
| GET | `/api/v1/steps/summary` | Step chart data |
| POST | `/api/v1/public/analyze-food` | Try without account |

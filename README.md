# AI-Powered Quiz API

A production-ready REST API for a full-featured quiz platform with AI-generated questions, JWT authentication, analytics, and leaderboards.

---
## Live Demo on Railway 

| | |
|---|---|
| **Interactive Docs** | https://web-production-2decb.up.railway.app/docs/ |
| **Admin Panel** | https://web-production-2decb.up.railway.app/admin/ |

---
---

## Live Demo on Render

| Feature | Link |
|--------|------|
| **API Docs**  | https://quiz-api-qkxw.onrender.com/ |

---

## Quick Start

```bash
# 1. Clone and enter
git clone <repo-url> && cd quiz_api

# 2. Create virtual environment
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — add your AI provider API key (see AI Integration section)

# 5. Run migrations
python manage.py migrate

# 6. Create a superuser (optional)
python manage.py createsuperuser

# 7. Start the server
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/v1/`.

---

## Database Schema

```
users                       user_profiles
─────────────────────       ──────────────────────────
id (UUID PK)                id (UUID PK)
email (unique)              user_id (FK → users, 1:1)
username (unique)           total_quizzes_taken
role (student/educator/     total_questions_answered
      admin)                total_correct_answers
first_name, last_name       total_points
bio, avatar_url             streak_days
is_active, is_staff         last_activity_date
email_verified              preferred_difficulty
date_joined, last_login     preferred_topics (JSON)

quizzes                     questions
────────────────────────    ──────────────────────────
id (UUID PK)                id (UUID PK)
creator_id (FK → users)     quiz_id (FK → quizzes)
title, description          question_type (mcq/tf)
topic                       order
difficulty (easy/med/hard)  text
status (draft/generating/   explanation
        published/archived/ options (JSON array)
        failed)             correct_answer (JSON)
question_count              points
time_limit_minutes
is_public, allow_retake
pass_percentage
ai_model_used               user_answers
attempt_count, avg_score    ──────────────────────────
                            id (UUID PK)
quiz_attempts               attempt_id (FK)
────────────────────────    question_id (FK)
id (UUID PK)                selected_answer (JSON)
user_id (FK → users)        is_correct
quiz_id (FK → quizzes)      points_earned
status (in_progress/        time_taken_seconds
        completed/
        timed_out/
        abandoned)
score_percentage
correct_answers
total_questions
time_taken_seconds
started_at, completed_at
difficulty_at_attempt
```

### Key Relationships
- **User → Quiz**: one-to-many (a user creates many quizzes)
- **Quiz → Question**: one-to-many with cascade delete
- **User + Quiz → QuizAttempt**: many-to-many bridge with state
- **QuizAttempt → UserAnswer**: one-to-many (one answer per question)
- **User → UserProfile**: one-to-one (stats + preferences)

---

## API Endpoints

### Authentication  `POST`
| Endpoint | Description |
|---|---|
| `POST /api/v1/auth/register/` | Register new user, returns JWT tokens |
| `POST /api/v1/auth/login/` | Login, returns JWT tokens |
| `POST /api/v1/auth/logout/` | Blacklist refresh token |
| `POST /api/v1/auth/token/refresh/` | Rotate refresh token |

### Users  🔒 requires auth
| Endpoint | Description |
|---|---|
| `GET/PATCH /api/v1/users/me/` | View / update own profile |
| `POST /api/v1/users/me/change-password/` | Change password |
| `GET/PATCH /api/v1/users/me/preferences/` | Quiz preferences |
| `GET /api/v1/users/<username>/profile/` | Public profile |
| `GET /api/v1/users/` | List all users (admin only) |
| `GET/PATCH/DELETE /api/v1/users/<id>/` | Manage user (admin only) |

### Quizzes
| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/v1/quizzes/` | Public | List published quizzes. Filter by `difficulty`, `topic`; search by title |
| `GET /api/v1/quizzes/mine/` | 🔒 | My created quizzes |
| `POST /api/v1/quizzes/create/` | 🔒 | Create quiz + AI generation (10/hr throttle) |
| `GET /api/v1/quizzes/<id>/` | 🔒 | Quiz detail with questions (no answers) |
| `PATCH /api/v1/quizzes/<id>/edit/` | 🔒 owner | Edit title, description, etc. |
| `DELETE /api/v1/quizzes/<id>/delete/` | 🔒 owner | Archive quiz (soft delete) |
| `POST /api/v1/quizzes/<id>/regenerate/` | 🔒 owner | Re-generate questions with AI |

### Quiz Attempts
| Endpoint | Description |
|---|---|
| `POST /api/v1/quizzes/<quiz_id>/attempt/` | Start an attempt |
| `GET /api/v1/quizzes/attempts/` | My attempt history |
| `POST /api/v1/quizzes/attempts/<id>/answer/` | Submit a single answer |
| `POST /api/v1/quizzes/attempts/<id>/answers/bulk/` | Submit all answers at once |
| `POST /api/v1/quizzes/attempts/<id>/submit/` | Finalise + score the attempt |
| `GET /api/v1/quizzes/attempts/<id>/results/` | Get scored results |

### Analytics   requires auth
| Endpoint | Description |
|---|---|
| `GET /api/v1/analytics/dashboard/` | Personal dashboard (cached 5 min) |
| `GET /api/v1/analytics/leaderboard/` | Global leaderboard (cached 1 hr). `?quiz=<id>` for quiz-specific |
| `GET /api/v1/analytics/quizzes/<id>/` | Quiz statistics (creator/admin) |
| `GET /api/v1/analytics/quizzes/<id>/questions/` | Per-question difficulty stats |
| `GET /api/v1/analytics/admin/overview/` | Platform stats (admin only) |

### Pagination
All list endpoints return a consistent pagination envelope:
```json
{
  "pagination": { "count": 42, "total_pages": 3, "current_page": 1, "next": "...", "previous": null },
  "results": [...]
}
```

### Error Envelope
All errors return a consistent structure:
```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found.",
    "details": {}
  }
}
```

---

## AI Integration

The API supports three free-tier AI providers. Set `AI_SERVICE` in `.env`:

| Provider | Model | Free Tier | Env var |
|---|---|---|---|
| Groq ✅ (currently used) | `llama-3.3-70b-versatile` | Free | `GROQ_API_KEY` |
| OpenAI | `gpt-4o-mini` | $5 credit | `OPENAI_API_KEY` |
| Anthropic | `claude-haiku-4-5-20251001` | $5 credit | `ANTHROPIC_API_KEY` |
| Google | `gemini-1.5-flash` | Generous free tier | `GEMINI_API_KEY` |

**How it works:**
1. Client sends `POST /api/v1/quizzes/create/` with topic, count, difficulty
2. Quiz record created with `status=generating`
3. AI provider is called with a structured prompt requesting a JSON array of questions
4. Response is parsed and validated; malformed questions are dropped
5. Questions are bulk-inserted; quiz status set to `published`
6. Results are cached for 24 hours keyed on `(topic, count, difficulty)` — identical requests skip the AI call

**Failure handling:** On AI failure, the quiz is set to `status=failed` with the error stored. The client receives `502 Bad Gateway`. The quiz can be retried via `POST .../regenerate/`.

---

## Design Decisions

### Why `options` and `correct_answer` as JSON fields?
Storing answer choices as JSON (rather than a separate `choices` table) reduces JOIN complexity for what is essentially a read-heavy, insert-once operation. The trade-off is no relational integrity on option IDs — mitigated by validation in `Question.check_answer()`.

### Why synchronous AI calls?
For simplicity and deployability. The quiz creation endpoint returns once AI generation is done (~5-10s). For production scale, this should move to a background task (Celery + Redis). The code is structured to make this swap trivial — `QuizCreateView.create()` just needs to dispatch a task instead of calling `generate_quiz_questions()` inline.

### Soft deletes
Quizzes are never hard-deleted — they're archived. This preserves attempt history and analytics integrity. Users are also soft-deactivated (`is_active=False`).

### Denormalised stats
`Quiz.attempt_count` / `avg_score` and `UserProfile.total_*` fields are denormalised counters updated incrementally after each attempt. This makes list views fast without aggregation queries. `Quiz.update_stats()` and `QuizAttempt._update_user_profile()` handle the updates.

### Analytics snapshots
`QuizAnalyticsSnapshot` stores daily per-quiz statistics generated by the `snapshot_analytics` management command. This decouples expensive aggregations from request time. Run it daily:
```bash
python manage.py snapshot_analytics
```

---

## Deployment (Railway)

1. Push to GitHub
2. Create a new Railway project, connect your repo
3. Add a PostgreSQL plugin
4. Set environment variables (copy from `.env.example`, add real values)
5. Railway auto-detects the `Procfile` and runs migrations + gunicorn

The `release:` line in the Procfile (`python manage.py migrate`) runs automatically on each deploy.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use `pytest-django` and mock the AI service so no real API keys are required.

---

## Project Structure

```
quiz_api/
├── quiz_api/                # Django project config
│   ├── settings.py          # All settings, env-var driven
│   ├── urls.py              # Root URL routing
│   ├── exceptions.py        # Consistent error envelope
│   ├── pagination.py        # Standardised pagination
│   └── permissions.py       # IsAdminUser, IsOwnerOrAdmin, etc.
│
├── apps/
│   ├── users/               # Auth, profiles, preferences
│   │   ├── models.py        # User, UserProfile
│   │   ├── serializers.py
│   │   ├── views/
│   │   └── urls/
│   │
│   ├── quizzes/             # Core quiz domain
│   │   ├── models.py        # Quiz, Question, QuizAttempt, UserAnswer
│   │   ├── serializers.py
│   │   ├── ai_service.py    # Provider-agnostic AI abstraction
│   │   ├── views/
│   │   │   ├── quiz_views.py     # CRUD + AI generation
│   │   │   └── attempt_views.py  # Start/answer/submit/results
│   │   └── urls.py
│   │
│   └── analytics/           # Dashboards, leaderboards, stats
│       ├── models.py        # Snapshots, summaries
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── management/commands/snapshot_analytics.py
│
├── tests/
│   └── test_api.py          # Full integration test suite
│
├── manage.py
├── requirements.txt
├── Procfile
└── .env.example
```

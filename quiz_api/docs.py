from django.http import HttpResponse


SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Quiz API — Documentation</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.min.css"/>
  <style>
    body { margin: 0; background: #0f1117; }
    #swagger-ui .topbar { display: none; }
    #swagger-ui .swagger-ui .info .title { color: #fff; }
  </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.min.js"></script>
<script>
  window.onload = () => {
    SwaggerUIBundle({
      spec: SPEC,
      dom_id: '#swagger-ui',
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: 'BaseLayout',
      deepLinking: true,
      tryItOutEnabled: true,
      persistAuthorization: true,
    });
  };

  const SPEC = {
    openapi: "3.0.3",
    info: {
      title: "AI-Powered Quiz API",
      version: "1.0.0",
      description: "REST API for a quiz platform with AI-generated questions, JWT authentication, attempt tracking, and analytics.\\n\\n**Quick start:** Register → Login → Copy the `access` token → Click **Authorize** → Paste `Bearer <token>`"
    },
    servers: [{ url: "/api/v1", description: "Local dev" }],
    components: {
      securitySchemes: {
        BearerAuth: { type: "http", scheme: "bearer", bearerFormat: "JWT" }
      },
      schemas: {
        Error: {
          type: "object",
          properties: {
            error: {
              type: "object",
              properties: {
                code: { type: "string", example: "not_found" },
                message: { type: "string", example: "The requested resource was not found." },
                details: { type: "object" }
              }
            }
          }
        },
        Tokens: {
          type: "object",
          properties: {
            access: { type: "string" },
            refresh: { type: "string" }
          }
        },
        User: {
          type: "object",
          properties: {
            id: { type: "string", format: "uuid" },
            email: { type: "string", format: "email" },
            username: { type: "string" },
            full_name: { type: "string" },
            role: { type: "string", enum: ["student", "educator", "admin"] },
            bio: { type: "string" },
            avatar_url: { type: "string" },
            date_joined: { type: "string", format: "date-time" },
            profile: { "$ref": "#/components/schemas/UserProfile" }
          }
        },
        UserProfile: {
          type: "object",
          properties: {
            total_quizzes_taken: { type: "integer" },
            total_points: { type: "integer" },
            accuracy_percentage: { type: "number" },
            streak_days: { type: "integer" },
            preferred_difficulty: { type: "string" },
            preferred_topics: { type: "array", items: { type: "string" } }
          }
        },
        Quiz: {
          type: "object",
          properties: {
            id: { type: "string", format: "uuid" },
            title: { type: "string" },
            topic: { type: "string" },
            difficulty: { type: "string", enum: ["easy", "medium", "hard"] },
            status: { type: "string", enum: ["draft","generating","published","archived","failed"] },
            question_count: { type: "integer" },
            time_limit_minutes: { type: "integer", nullable: true },
            is_public: { type: "boolean" },
            attempt_count: { type: "integer" },
            avg_score: { type: "number" },
            creator_username: { type: "string" },
            created_at: { type: "string", format: "date-time" }
          }
        },
        QuizDetail: {
          allOf: [
            { "$ref": "#/components/schemas/Quiz" },
            {
              type: "object",
              properties: {
                description: { type: "string" },
                questions: {
                  type: "array",
                  items: { "$ref": "#/components/schemas/Question" }
                }
              }
            }
          ]
        },
        Question: {
          type: "object",
          properties: {
            id: { type: "string", format: "uuid" },
            order: { type: "integer" },
            question_type: { type: "string", enum: ["mcq", "tf"] },
            text: { type: "string" },
            options: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  id: { type: "string" },
                  text: { type: "string" }
                }
              }
            },
            points: { type: "integer" },
            explanation: { type: "string", description: "Shown after answering" }
          }
        },
        Attempt: {
          type: "object",
          properties: {
            id: { type: "string", format: "uuid" },
            quiz: { "$ref": "#/components/schemas/Quiz" },
            status: { type: "string", enum: ["in_progress","completed","timed_out","abandoned"] },
            score_percentage: { type: "number" },
            correct_answers: { type: "integer" },
            total_questions: { type: "integer" },
            total_points_earned: { type: "integer" },
            time_taken_seconds: { type: "integer" },
            started_at: { type: "string", format: "date-time" },
            completed_at: { type: "string", format: "date-time", nullable: true }
          }
        },
        Pagination: {
          type: "object",
          properties: {
            pagination: {
              type: "object",
              properties: {
                count: { type: "integer" },
                total_pages: { type: "integer" },
                current_page: { type: "integer" },
                next: { type: "string", nullable: true },
                previous: { type: "string", nullable: true }
              }
            },
            results: { type: "array", items: {} }
          }
        }
      }
    },
    security: [{ BearerAuth: [] }],
    tags: [
      { name: "Auth", description: "Register, login, logout, token refresh" },
      { name: "Users", description: "Profile management and preferences" },
      { name: "Quizzes", description: "Quiz CRUD and AI generation" },
      { name: "Attempts", description: "Start, answer, submit, and review quiz attempts" },
      { name: "Analytics", description: "Dashboards, leaderboards, and stats" }
    ],
    paths: {
      "/auth/register/": {
        post: {
          tags: ["Auth"], summary: "Register a new user",
          security: [],
          requestBody: {
            required: true,
            content: { "application/json": { schema: {
              type: "object", required: ["email","username","password","password_confirm"],
              properties: {
                email: { type: "string", format: "email", example: "user@example.com" },
                username: { type: "string", example: "johndoe" },
                password: { type: "string", example: "Str0ngPass!" },
                password_confirm: { type: "string", example: "Str0ngPass!" },
                first_name: { type: "string" },
                last_name: { type: "string" },
                role: { type: "string", enum: ["student", "educator"], default: "student" }
              }
            }}}
          },
          responses: {
            "201": { description: "User created", content: { "application/json": { schema: {
              type: "object",
              properties: {
                user: { "$ref": "#/components/schemas/User" },
                tokens: { "$ref": "#/components/schemas/Tokens" },
                message: { type: "string" }
              }
            }}}},
            "400": { description: "Validation error", content: { "application/json": { schema: { "$ref": "#/components/schemas/Error" }}}}
          }
        }
      },
      "/auth/login/": {
        post: {
          tags: ["Auth"], summary: "Login and receive JWT tokens",
          security: [],
          requestBody: {
            required: true,
            content: { "application/json": { schema: {
              type: "object", required: ["email","password"],
              properties: {
                email: { type: "string", format: "email", example: "user@example.com" },
                password: { type: "string", example: "Str0ngPass!" }
              }
            }}}
          },
          responses: {
            "200": { description: "Login successful", content: { "application/json": { schema: {
              type: "object",
              properties: {
                user: { "$ref": "#/components/schemas/User" },
                tokens: { "$ref": "#/components/schemas/Tokens" }
              }
            }}}},
            "400": { description: "Invalid credentials" }
          }
        }
      },
      "/auth/logout/": {
        post: {
          tags: ["Auth"], summary: "Logout — blacklist the refresh token",
          requestBody: {
            required: true,
            content: { "application/json": { schema: {
              type: "object", required: ["refresh"],
              properties: { refresh: { type: "string" } }
            }}}
          },
          responses: {
            "200": { description: "Logged out" },
            "400": { description: "Invalid token" }
          }
        }
      },
      "/auth/token/refresh/": {
        post: {
          tags: ["Auth"], summary: "Rotate refresh token, get new access token",
          security: [],
          requestBody: {
            required: true,
            content: { "application/json": { schema: {
              type: "object", required: ["refresh"],
              properties: { refresh: { type: "string" } }
            }}}
          },
          responses: {
            "200": { description: "New tokens", content: { "application/json": { schema: { "$ref": "#/components/schemas/Tokens" }}}}
          }
        }
      },
      "/users/me/": {
        get: {
          tags: ["Users"], summary: "Get own profile",
          responses: { "200": { description: "User profile", content: { "application/json": { schema: { "$ref": "#/components/schemas/User" }}}}}
        },
        patch: {
          tags: ["Users"], summary: "Update own profile",
          requestBody: {
            content: { "application/json": { schema: {
              type: "object",
              properties: {
                first_name: { type: "string" },
                last_name: { type: "string" },
                bio: { type: "string" },
                avatar_url: { type: "string" }
              }
            }}}
          },
          responses: { "200": { description: "Updated profile" }}
        }
      },
      "/users/me/change-password/": {
        post: {
          tags: ["Users"], summary: "Change password",
          requestBody: {
            required: true,
            content: { "application/json": { schema: {
              type: "object",
              required: ["current_password","new_password","new_password_confirm"],
              properties: {
                current_password: { type: "string" },
                new_password: { type: "string" },
                new_password_confirm: { type: "string" }
              }
            }}}
          },
          responses: { "200": { description: "Password changed" }, "400": { description: "Validation error" }}
        }
      },
      "/users/me/preferences/": {
        get: { tags: ["Users"], summary: "Get quiz preferences", responses: { "200": { description: "Preferences" }}},
        patch: {
          tags: ["Users"], summary: "Update quiz preferences",
          requestBody: {
            content: { "application/json": { schema: {
              type: "object",
              properties: {
                preferred_difficulty: { type: "string", enum: ["easy","medium","hard"] },
                preferred_topics: { type: "array", items: { type: "string" } }
              }
            }}}
          },
          responses: { "200": { description: "Updated preferences" }}
        }
      },
      "/quizzes/": {
        get: {
          tags: ["Quizzes"], summary: "List published public quizzes",
          security: [],
          parameters: [
            { name: "difficulty", in: "query", schema: { type: "string", enum: ["easy","medium","hard"] }},
            { name: "topic", in: "query", schema: { type: "string" }},
            { name: "search", in: "query", schema: { type: "string" }, description: "Search in title, topic, tags" },
            { name: "ordering", in: "query", schema: { type: "string" }, example: "-created_at" },
            { name: "page", in: "query", schema: { type: "integer" }},
            { name: "page_size", in: "query", schema: { type: "integer" }}
          ],
          responses: { "200": { description: "Paginated quiz list" }}
        }
      },
      "/quizzes/create/": {
        post: {
          tags: ["Quizzes"],
          summary: "Create a quiz — triggers AI question generation",
          description: "Throttled to **10 requests per hour** per user. Quiz is created in `generating` status, AI is called, then status becomes `published`.",
          requestBody: {
            required: true,
            content: { "application/json": { schema: {
              type: "object",
              required: ["title","topic","difficulty","question_count"],
              properties: {
                title: { type: "string", example: "Python Basics" },
                description: { type: "string" },
                topic: { type: "string", example: "Python programming fundamentals" },
                difficulty: { type: "string", enum: ["easy","medium","hard"] },
                question_count: { type: "integer", minimum: 1, maximum: 50, example: 5 },
                time_limit_minutes: { type: "integer", nullable: true, example: 15 },
                is_public: { type: "boolean", default: true },
                tags: { type: "array", items: { type: "string" } }
              }
            }}}
          },
          responses: {
            "201": { description: "Quiz created with AI-generated questions", content: { "application/json": { schema: { "$ref": "#/components/schemas/QuizDetail" }}}},
            "400": { description: "Validation error" },
            "429": { description: "AI generation throttle exceeded (10/hr)" },
            "502": { description: "AI service failed" }
          }
        }
      },
      "/quizzes/mine/": {
        get: {
          tags: ["Quizzes"], summary: "My created quizzes (all statuses)",
          responses: { "200": { description: "Paginated list of own quizzes" }}
        }
      },
      "/quizzes/{id}/": {
        get: {
          tags: ["Quizzes"], summary: "Quiz detail — includes questions, no correct answers",
          parameters: [{ name: "id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          responses: {
            "200": { description: "Quiz with questions", content: { "application/json": { schema: { "$ref": "#/components/schemas/QuizDetail" }}}},
            "404": { description: "Not found" }
          }
        }
      },
      "/quizzes/{id}/edit/": {
        patch: {
          tags: ["Quizzes"], summary: "Edit quiz metadata (owner/admin only)",
          parameters: [{ name: "id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          requestBody: {
            content: { "application/json": { schema: {
              type: "object",
              properties: {
                title: { type: "string" },
                description: { type: "string" },
                time_limit_minutes: { type: "integer" },
                is_public: { type: "boolean" },
                status: { type: "string", enum: ["published","archived"] }
              }
            }}}
          },
          responses: { "200": { description: "Updated quiz" }, "403": { description: "Forbidden" }}
        }
      },
      "/quizzes/{id}/delete/": {
        delete: {
          tags: ["Quizzes"], summary: "Archive quiz — soft delete (owner/admin only)",
          parameters: [{ name: "id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          responses: { "200": { description: "Quiz archived" }, "403": { description: "Forbidden" }}
        }
      },
      "/quizzes/{id}/regenerate/": {
        post: {
          tags: ["Quizzes"], summary: "Re-run AI generation — replaces all questions",
          parameters: [{ name: "id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          responses: { "200": { description: "Quiz with new questions" }, "502": { description: "AI service failed" }}
        }
      },
      "/quizzes/{quiz_id}/attempt/": {
        post: {
          tags: ["Attempts"], summary: "Start a new attempt",
          description: "Returns the existing active attempt if one is already in progress.",
          parameters: [{ name: "quiz_id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          responses: {
            "201": { description: "Attempt started", content: { "application/json": { schema: {
              type: "object",
              properties: {
                attempt_id: { type: "string", format: "uuid" },
                quiz_title: { type: "string" },
                question_count: { type: "integer" },
                time_limit_minutes: { type: "integer", nullable: true },
                started_at: { type: "string", format: "date-time" },
                expires_at: { type: "string", format: "date-time", nullable: true }
              }
            }}}},
            "200": { description: "Existing in-progress attempt returned" },
            "403": { description: "Private quiz" },
            "409": { description: "Retakes not allowed" }
          }
        }
      },
      "/quizzes/attempts/": {
        get: {
          tags: ["Attempts"], summary: "My attempt history",
          parameters: [
            { name: "status", in: "query", schema: { type: "string", enum: ["in_progress","completed","timed_out","abandoned"] }},
            { name: "quiz", in: "query", schema: { type: "string", format: "uuid" }},
            { name: "ordering", in: "query", schema: { type: "string" }, example: "-started_at" }
          ],
          responses: { "200": { description: "Paginated attempt history" }}
        }
      },
      "/quizzes/attempts/{attempt_id}/answer/": {
        post: {
          tags: ["Attempts"], summary: "Submit a single answer (can be updated before final submit)",
          parameters: [{ name: "attempt_id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          requestBody: {
            required: true,
            content: { "application/json": { schema: {
              type: "object",
              required: ["question_id","selected_answer"],
              properties: {
                question_id: { type: "string", format: "uuid" },
                selected_answer: {
                  description: "List of option id(s), e.g. ['b'] for MCQ or ['true'] for T/F",
                  type: "array", items: { type: "string" }, example: ["b"]
                },
                time_taken_seconds: { type: "integer", example: 12 }
              }
            }}}
          },
          responses: {
            "200": { description: "Answer saved", content: { "application/json": { schema: {
              type: "object",
              properties: {
                question_id: { type: "string" },
                answer_saved: { type: "boolean" },
                is_correct: { type: "boolean" },
                points_earned: { type: "integer" }
              }
            }}}},
            "400": { description: "Timed out" }
          }
        }
      },
      "/quizzes/attempts/{attempt_id}/answers/bulk/": {
        post: {
          tags: ["Attempts"], summary: "Submit all answers at once",
          parameters: [{ name: "attempt_id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          requestBody: {
            required: true,
            content: { "application/json": { schema: {
              type: "object",
              properties: {
                answers: {
                  type: "array",
                  items: {
                    type: "object",
                    properties: {
                      question_id: { type: "string", format: "uuid" },
                      selected_answer: { type: "array", items: { type: "string" } },
                      time_taken_seconds: { type: "integer" }
                    }
                  }
                }
              }
            }}}
          },
          responses: { "200": { description: "All answers saved" }}
        }
      },
      "/quizzes/attempts/{attempt_id}/submit/": {
        post: {
          tags: ["Attempts"], summary: "Finalise attempt — scores it and returns full results",
          parameters: [{ name: "attempt_id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          responses: {
            "200": { description: "Attempt scored", content: { "application/json": { schema: { "$ref": "#/components/schemas/Attempt" }}}},
            "409": { description: "Already submitted" }
          }
        }
      },
      "/quizzes/attempts/{attempt_id}/results/": {
        get: {
          tags: ["Attempts"], summary: "Get full results with per-question breakdown and correct answers",
          parameters: [{ name: "attempt_id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          responses: {
            "200": { description: "Detailed results including correct answers and explanations" },
            "400": { description: "Attempt not yet submitted" }
          }
        }
      },
      "/analytics/dashboard/": {
        get: {
          tags: ["Analytics"], summary: "Personal dashboard — performance, streaks, achievements",
          description: "Cached per user for 5 minutes.",
          responses: { "200": { description: "Dashboard payload" }}
        }
      },
      "/analytics/leaderboard/": {
        get: {
          tags: ["Analytics"], summary: "Leaderboard — global or per-quiz",
          description: "Cached for 1 hour.",
          parameters: [
            { name: "quiz", in: "query", schema: { type: "string", format: "uuid" }, description: "Filter to a specific quiz" },
            { name: "period", in: "query", schema: { type: "string", enum: ["weekly","monthly","all_time"] }}
          ],
          responses: { "200": { description: "Ranked list of users" }}
        }
      },
      "/analytics/quizzes/{quiz_id}/": {
        get: {
          tags: ["Analytics"], summary: "Quiz analytics — score distribution, pass rate, daily trend (creator/admin only)",
          parameters: [{ name: "quiz_id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          responses: { "200": { description: "Quiz analytics" }, "403": { description: "Not authorised" }}
        }
      },
      "/analytics/quizzes/{quiz_id}/questions/": {
        get: {
          tags: ["Analytics"], summary: "Per-question difficulty ratings (creator/admin only)",
          parameters: [{ name: "quiz_id", in: "path", required: true, schema: { type: "string", format: "uuid" }}],
          responses: { "200": { description: "Question analytics" }}
        }
      },
      "/analytics/admin/overview/": {
        get: {
          tags: ["Analytics"], summary: "Platform-wide stats (admin only)",
          responses: {
            "200": { description: "Platform overview" },
            "403": { description: "Admin only" }
          }
        }
      }
    }
  };
</script>
</body>
</html>"""


def api_docs(request):
    return HttpResponse(SWAGGER_HTML, content_type='text/html')

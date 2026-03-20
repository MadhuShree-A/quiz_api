"""
tests/test_api.py — Integration tests covering the complete user flow.

Run with:
    pytest tests/test_api.py -v
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()

# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def student(db):
    user = User.objects.create_user(
        email='student@test.com',
        username='student1',
        password='Str0ngPass!',
        role='student',
    )
    return user


@pytest.fixture
def educator(db):
    user = User.objects.create_user(
        email='educator@test.com',
        username='educator1',
        password='Str0ngPass!',
        role='educator',
    )
    return user


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email='admin@test.com',
        username='admin1',
        password='Str0ngPass!',
    )


@pytest.fixture
def auth_client(api_client, student):
    api_client.force_authenticate(user=student)
    return api_client


@pytest.fixture
def educator_client(api_client, educator):
    api_client.force_authenticate(user=educator)
    return api_client


@pytest.fixture
def mock_ai_questions():
    return [
        {
            'order': 1,
            'question_type': 'mcq',
            'text': 'What is the capital of France?',
            'options': [
                {'id': 'a', 'text': 'London'},
                {'id': 'b', 'text': 'Paris'},
                {'id': 'c', 'text': 'Berlin'},
                {'id': 'd', 'text': 'Madrid'},
            ],
            'correct_answer': ['b'],
            'explanation': 'Paris is the capital of France.',
            'points': 1,
        },
        {
            'order': 2,
            'question_type': 'tf',
            'text': 'The Earth is flat.',
            'options': [
                {'id': 'true', 'text': 'True'},
                {'id': 'false', 'text': 'False'},
            ],
            'correct_answer': ['false'],
            'explanation': 'The Earth is an oblate spheroid.',
            'points': 1,
        },
    ]


@pytest.fixture
def published_quiz(db, educator, mock_ai_questions):
    from apps.quizzes.models import Quiz, Question
    quiz = Quiz.objects.create(
        creator=educator,
        title='Test Quiz',
        topic='Geography',
        difficulty='easy',
        status=Quiz.Status.PUBLISHED,
        question_count=2,
        is_public=True,
    )
    for q in mock_ai_questions:
        Question.objects.create(
            quiz=quiz,
            order=q['order'],
            question_type=q['question_type'],
            text=q['text'],
            options=q['options'],
            correct_answer=q['correct_answer'],
            explanation=q['explanation'],
            points=q['points'],
        )
    return quiz


# ─── Auth Tests ────────────────────────────────────────────────────────────────

class TestRegistration:
    def test_register_success(self, api_client, db):
        res = api_client.post('/api/v1/auth/register/', {
            'email': 'new@test.com',
            'username': 'newuser',
            'password': 'Str0ngPass!',
            'password_confirm': 'Str0ngPass!',
        })
        assert res.status_code == status.HTTP_201_CREATED
        assert 'tokens' in res.data
        assert res.data['tokens']['access']

    def test_register_password_mismatch(self, api_client, db):
        res = api_client.post('/api/v1/auth/register/', {
            'email': 'new@test.com',
            'username': 'newuser',
            'password': 'Str0ngPass!',
            'password_confirm': 'WrongPass!',
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, api_client, student):
        res = api_client.post('/api/v1/auth/register/', {
            'email': student.email,
            'username': 'another',
            'password': 'Str0ngPass!',
            'password_confirm': 'Str0ngPass!',
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_register_as_admin(self, api_client, db):
        res = api_client.post('/api/v1/auth/register/', {
            'email': 'hacker@test.com',
            'username': 'hacker',
            'password': 'Str0ngPass!',
            'password_confirm': 'Str0ngPass!',
            'role': 'admin',
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST


class TestLogin:
    def test_login_success(self, api_client, student):
        res = api_client.post('/api/v1/auth/login/', {
            'email': student.email,
            'password': 'Str0ngPass!',
        })
        assert res.status_code == status.HTTP_200_OK
        assert 'tokens' in res.data
        assert 'access' in res.data['tokens']
        assert 'refresh' in res.data['tokens']

    def test_login_wrong_password(self, api_client, student):
        res = api_client.post('/api/v1/auth/login/', {
            'email': student.email,
            'password': 'WrongPassword!',
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_inactive_user(self, api_client, student):
        student.is_active = False
        student.save()
        res = api_client.post('/api/v1/auth/login/', {
            'email': student.email,
            'password': 'Str0ngPass!',
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST


# ─── User Profile Tests ────────────────────────────────────────────────────────

class TestUserProfile:
    def test_get_own_profile(self, auth_client):
        res = auth_client.get('/api/v1/users/me/')
        assert res.status_code == status.HTTP_200_OK
        assert 'username' in res.data

    def test_update_own_profile(self, auth_client):
        res = auth_client.patch('/api/v1/users/me/', {'bio': 'I love quizzes!'})
        assert res.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_get_profile(self, api_client):
        res = api_client.get('/api/v1/users/me/')
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_change_password(self, auth_client):
        res = auth_client.post('/api/v1/users/me/change-password/', {
            'current_password': 'Str0ngPass!',
            'new_password': 'NewStr0ngPass!',
            'new_password_confirm': 'NewStr0ngPass!',
        })
        assert res.status_code == status.HTTP_200_OK


# ─── Quiz Tests ────────────────────────────────────────────────────────────────

class TestQuizList:
    def test_list_public_quizzes_unauthenticated(self, api_client, published_quiz):
        res = api_client.get('/api/v1/quizzes/')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['pagination']['count'] >= 1

    def test_filter_by_difficulty(self, api_client, published_quiz):
        res = api_client.get('/api/v1/quizzes/?difficulty=easy')
        assert res.status_code == status.HTTP_200_OK

    def test_search_by_topic(self, api_client, published_quiz):
        res = api_client.get('/api/v1/quizzes/?search=Geography')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['pagination']['count'] >= 1


class TestQuizCreate:
    @patch('apps.quizzes.views.quiz_views.generate_quiz_questions')
    def test_create_quiz_success(self, mock_gen, auth_client, mock_ai_questions):
        mock_gen.return_value = mock_ai_questions
        res = auth_client.post('/api/v1/quizzes/create/', {
            'title': 'My Quiz',
            'topic': 'Python Programming',
            'difficulty': 'medium',
            'question_count': 2,
        })
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data['status'] == 'published'
        assert len(res.data['questions']) == 2

    @patch('apps.quizzes.views.quiz_views.generate_quiz_questions')
    def test_create_quiz_ai_failure(self, mock_gen, auth_client):
        from apps.quizzes.ai_service import AIServiceError
        mock_gen.side_effect = AIServiceError('AI is down')
        res = auth_client.post('/api/v1/quizzes/create/', {
            'title': 'Fail Quiz',
            'topic': 'Testing',
            'difficulty': 'easy',
            'question_count': 3,
        })
        assert res.status_code == status.HTTP_502_BAD_GATEWAY

    def test_create_quiz_invalid_question_count(self, auth_client):
        res = auth_client.post('/api/v1/quizzes/create/', {
            'title': 'Bad Quiz',
            'topic': 'Testing',
            'difficulty': 'easy',
            'question_count': 100,  # exceeds max
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST


class TestQuizDetail:
    def test_get_published_quiz(self, auth_client, published_quiz):
        res = auth_client.get(f'/api/v1/quizzes/{published_quiz.id}/')
        assert res.status_code == status.HTTP_200_OK
        assert 'questions' in res.data
        # Correct answers must NOT be in the response
        for q in res.data['questions']:
            assert 'correct_answer' not in q

    def test_unauthenticated_cannot_get_detail(self, api_client, published_quiz):
        res = api_client.get(f'/api/v1/quizzes/{published_quiz.id}/')
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ─── Attempt Flow Tests ────────────────────────────────────────────────────────

class TestAttemptFlow:
    def test_full_attempt_flow(self, auth_client, published_quiz):
        # 1. Start attempt
        res = auth_client.post(f'/api/v1/quizzes/{published_quiz.id}/attempt/')
        assert res.status_code == status.HTTP_201_CREATED
        attempt_id = res.data['attempt_id']

        # 2. Submit answers
        questions = published_quiz.questions.all()
        for q in questions:
            res = auth_client.post(
                f'/api/v1/quizzes/attempts/{attempt_id}/answer/',
                {
                    'question_id': str(q.id),
                    'selected_answer': q.correct_answer,
                    'time_taken_seconds': 10,
                }
            )
            assert res.status_code == status.HTTP_200_OK
            assert res.data['is_correct'] is True

        # 3. Submit attempt
        res = auth_client.post(f'/api/v1/quizzes/attempts/{attempt_id}/submit/')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['score_percentage'] == 100.0
        assert res.data['status'] == 'completed'

        # 4. Get results
        res = auth_client.get(f'/api/v1/quizzes/attempts/{attempt_id}/results/')
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data['answers']) == 2

    def test_cannot_start_attempt_on_private_quiz(self, api_client, educator, db):
        from apps.quizzes.models import Quiz
        private_quiz = Quiz.objects.create(
            creator=educator,
            title='Private',
            topic='Secret',
            difficulty='easy',
            status=Quiz.Status.PUBLISHED,
            question_count=1,
            is_public=False,
        )
        other_user = User.objects.create_user(
            email='other@test.com', username='other', password='pass'
        )
        api_client.force_authenticate(user=other_user)
        res = api_client.post(f'/api/v1/quizzes/{private_quiz.id}/attempt/')
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_double_start_returns_existing_attempt(self, auth_client, published_quiz):
        res1 = auth_client.post(f'/api/v1/quizzes/{published_quiz.id}/attempt/')
        assert res1.status_code == status.HTTP_201_CREATED
        res2 = auth_client.post(f'/api/v1/quizzes/{published_quiz.id}/attempt/')
        assert res2.status_code == status.HTTP_200_OK
        assert res1.data['attempt_id'] == res2.data['attempt_id']

    def test_cannot_view_results_before_submitting(self, auth_client, published_quiz):
        res = auth_client.post(f'/api/v1/quizzes/{published_quiz.id}/attempt/')
        attempt_id = res.data['attempt_id']
        res = auth_client.get(f'/api/v1/quizzes/attempts/{attempt_id}/results/')
        assert res.status_code == status.HTTP_400_BAD_REQUEST


# ─── Analytics Tests ───────────────────────────────────────────────────────────

class TestAnalytics:
    def test_dashboard_authenticated(self, auth_client):
        res = auth_client.get('/api/v1/analytics/dashboard/')
        assert res.status_code == status.HTTP_200_OK
        assert 'profile' in res.data
        assert 'weekly_activity' in res.data

    def test_leaderboard_accessible(self, auth_client):
        res = auth_client.get('/api/v1/analytics/leaderboard/')
        assert res.status_code == status.HTTP_200_OK
        assert isinstance(res.data, list)

    def test_quiz_analytics_owner_only(self, auth_client, educator_client, published_quiz):
        # Student who is NOT the creator should be forbidden
        res = auth_client.get(f'/api/v1/analytics/quizzes/{published_quiz.id}/')
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # Educator who IS the creator should succeed
        res = educator_client.get(f'/api/v1/analytics/quizzes/{published_quiz.id}/')
        assert res.status_code == status.HTTP_200_OK

    def test_admin_overview_requires_admin(self, auth_client, api_client, admin_user):
        # Student cannot access
        res = auth_client.get('/api/v1/analytics/admin/overview/')
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # Admin can access
        api_client.force_authenticate(user=admin_user)
        res = api_client.get('/api/v1/analytics/admin/overview/')
        assert res.status_code == status.HTTP_200_OK
        assert 'total_users' in res.data


# ─── AI Service Tests ──────────────────────────────────────────────────────────

class TestAIService:
    @patch('apps.quizzes.ai_service.requests.post')
    def test_openai_success(self, mock_post):
        import json
        from apps.quizzes.ai_service import generate_quiz_questions
        from django.test import override_settings

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            'choices': [{'message': {'content': json.dumps([
                {
                    'order': 1, 'question_type': 'mcq',
                    'text': 'Q1?',
                    'options': [
                        {'id': 'a', 'text': 'A'}, {'id': 'b', 'text': 'B'},
                        {'id': 'c', 'text': 'C'}, {'id': 'd', 'text': 'D'},
                    ],
                    'correct_answer': ['a'],
                    'explanation': 'Because A.',
                    'points': 1,
                }
            ])}}]
        }
        mock_post.return_value = mock_resp

        with override_settings(AI_SERVICE='openai', OPENAI_API_KEY='fake-key'):
            result = generate_quiz_questions('Python', 1, 'easy', use_cache=False)

        assert len(result) == 1
        assert result[0]['text'] == 'Q1?'

    @patch('apps.quizzes.ai_service.requests.post')
    def test_ai_failure_raises_error(self, mock_post):
        import requests as req_lib
        from apps.quizzes.ai_service import generate_quiz_questions, AIServiceError
        from django.test import override_settings

        mock_post.side_effect = req_lib.RequestException('Connection error')

        with override_settings(AI_SERVICE='openai', OPENAI_API_KEY='fake-key'):
            with pytest.raises(AIServiceError):
                generate_quiz_questions('Python', 1, 'easy', use_cache=False)

"""
AI Quiz Generation Service
==========================
Supports OpenAI, Anthropic Claude, and Google Gemini.
Set AI_SERVICE in your .env file.
"""

import json
import hashlib
import logging
import re
import time
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Raised when AI generation fails for any reason."""


SYSTEM_PROMPT = """You are an expert quiz generator. When asked to create quiz questions,
you MUST respond with ONLY a valid JSON array — no preamble, no markdown, no explanation.

Each element must follow this exact schema:
{
  "order": <int starting at 1>,
  "question_type": "<mcq|tf>",
  "text": "<question text>",
  "explanation": "<brief explanation of the correct answer>",
  "points": 1,
  "options": [
    {"id": "a", "text": "..."},
    {"id": "b", "text": "..."},
    {"id": "c", "text": "..."},
    {"id": "d", "text": "..."}
  ],
  "correct_answer": ["a"]
}

Rules:
- For MCQ: provide exactly 4 options (a, b, c, d), correct_answer is a list with one id.
- For T/F: provide 2 options [{"id":"true","text":"True"},{"id":"false","text":"False"}].
- Return ONLY the raw JSON array, no markdown fences, no extra text.
"""


def _build_prompt(topic: str, count: int, difficulty: str) -> str:
    guidance = {
        'easy': 'Use straightforward factual questions suitable for beginners.',
        'medium': 'Mix factual and analytical questions of moderate challenge.',
        'hard': 'Use challenging questions requiring deep understanding.',
    }.get(difficulty, '')
    return (
        f'Generate exactly {count} quiz questions about "{topic}". '
        f'Difficulty: {difficulty}. {guidance} '
        f'Mix mcq and tf types. '
        f'Return ONLY the JSON array.'
    )


def _cache_key(topic: str, count: int, difficulty: str) -> str:
    raw = f'{topic.lower()}:{count}:{difficulty}'
    return 'ai_quiz:' + hashlib.md5(raw.encode()).hexdigest()[:12]


def _parse_questions(raw: str) -> list[dict]:
    """Robustly extract a JSON array from raw LLM text."""
    cleaned = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ('questions', 'data', 'quiz', 'items'):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
            for v in parsed.values():
                if isinstance(v, list):
                    return v
    except json.JSONDecodeError:
        pass

    match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise AIServiceError('AI response could not be parsed as a JSON array.')


def _validate_questions(questions: list[dict]) -> list[dict]:
    valid = []
    for i, q in enumerate(questions, 1):
        try:
            assert isinstance(q.get('text'), str) and q['text'].strip(), 'missing text'
            assert isinstance(q.get('options'), list) and len(q['options']) >= 2, 'bad options'
            assert isinstance(q.get('correct_answer'), list) and q['correct_answer'], 'bad answer'
            q.setdefault('order', i)
            q.setdefault('question_type', 'mcq')
            q.setdefault('explanation', '')
            q.setdefault('points', 1)
            valid.append(q)
        except AssertionError as exc:
            logger.warning('Dropping malformed question %d: %s', i, exc)
    if not valid:
        raise AIServiceError('AI returned no valid questions after validation.')
    return valid


def _call_openai(prompt: str) -> str:
    import requests
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise AIServiceError('OPENAI_API_KEY is not set.')
    resp = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']


def _call_anthropic(prompt: str) -> str:
    import requests
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise AIServiceError('ANTHROPIC_API_KEY is not set.')
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json',
        },
        json={
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 4096,
            'system': SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()['content'][0]['text']


def _call_gemini(prompt: str) -> str:
    import requests
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise AIServiceError('GEMINI_API_KEY is not set.')
    url = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    f'gemini-2.0-flash:generateContent?key={api_key}'  
      )
    resp = requests.post(
        url,
        json={
            'contents': [{'parts': [{'text': SYSTEM_PROMPT + '\n\n' + prompt}]}],
            'generationConfig': {
                'temperature': 0.7,
                'maxOutputTokens': 4096,
            },
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()['candidates'][0]['content']['parts'][0]['text']

def _call_groq(prompt: str) -> str:
    import requests
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise AIServiceError('GROQ_API_KEY is not set.')
    resp = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': 'llama-3.3-70b-versatile',
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']


_PROVIDERS = {
    'openai': _call_openai,
    'anthropic': _call_anthropic,
    'gemini': _call_gemini,
    'groq': _call_groq,
}


def generate_quiz_questions(
    topic: str,
    count: int,
    difficulty: str,
    use_cache: bool = True,
) -> list[dict]:
    """
    Generate `count` questions about `topic` at `difficulty`.
    Returns a validated list of question dicts.
    Raises AIServiceError on failure.
    """
    if use_cache:
        key = _cache_key(topic, count, difficulty)
        cached = cache.get(key)
        if cached:
            logger.info('AI cache hit: topic=%s', topic)
            return cached

    service = getattr(settings, 'AI_SERVICE', 'openai').lower()
    caller = _PROVIDERS.get(service)
    if not caller:
        raise AIServiceError(
            f'Unknown AI_SERVICE "{service}". Choose: openai, anthropic, gemini.'
        )

    prompt = _build_prompt(topic, count, difficulty)
    max_retries = 2

    for attempt in range(1, max_retries + 1):
        try:
            raw = caller(prompt)
            questions = _parse_questions(raw)
            questions = _validate_questions(questions)

            if use_cache:
                cache.set(key, questions, timeout=getattr(settings, 'AI_GENERATION_CACHE_TTL', 86400))

            logger.info('AI generated %d questions via %s for topic="%s"', len(questions), service, topic)
            return questions

        except AIServiceError:
            raise
        except Exception as exc:
            logger.warning('AI attempt %d/%d failed: %s', attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                raise AIServiceError(f'AI generation failed after {max_retries} attempts: {exc}') from exc
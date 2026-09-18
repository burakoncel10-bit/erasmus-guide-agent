"""
Erasmus Guide — core agent.

Three things distinguish this from a prompt wrapped around an API call:

1. Context is loaded per mode, not all at once. Each mode declares the
   reference files it needs; nothing else enters the model's window.
2. Essay scoring returns a fixed JSON schema, not prose. The rubric's promise
   of comparable feedback is enforced by the data structure rather than by
   asking the model nicely.
3. Results are persisted, so progress is something the system knows rather
   than something the student has to re-state every session.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

KNOWLEDGE = Path(__file__).with_name("knowledge")
MODEL = "gemini-3.6-flash"
# Tried in order when the primary model is overloaded (503) or rate-limited.
# A lite model is last: slightly weaker output beats no output.
FALLBACK_MODELS = ["gemini-3.7-flash", "gemini-3.5-flash-lite"]
RETRYABLE_CODES = {429, 500, 503, 504}
RETRIES_PER_MODEL = 3

EXAM_DATE = date(2027, 1, 15)

# Which reference files each mode needs. The point of splitting the knowledge
# base was to avoid sending all of it every time; this table is where that
# decision actually gets made.
MODE_CONTEXT = {
    "feedback": ["feedback-rubrigi.md", "akademik-kelime.md", "kalip-cumleler.md"],
    "plan": ["calisma-plani.md"],
    "exercise": ["essay-topic-bankasi.md", "essay-turleri.md"],
    "progress": ["ilerleme-takibi.md"],
}

RUBRIC_CRITERIA = [
    ("task_achievement", "Task Achievement / Topic'e Sadakat"),
    ("coherence", "Yapı ve Tutarlılık"),
    ("lexical", "Akademik Dil"),
    ("grammar", "Gramer ve Cümle Yapısı"),
    ("mechanics", "Noktalama, Yazım ve Format"),
]


# ---------------------------------------------------------------------------
# context loading
# ---------------------------------------------------------------------------

def load_context(mode: str) -> str:
    """Read only the reference files this mode declares."""
    parts = []
    for name in MODE_CONTEXT.get(mode, []):
        path = KNOWLEDGE / name
        if path.exists():
            parts.append(f"=== {name} ===\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def context_report(mode: str) -> tuple:
    """Which files were loaded and how many characters — shown in the UI so the
    selective loading is visible rather than merely claimed."""
    names = MODE_CONTEXT.get(mode, [])
    size = sum(
        len((KNOWLEDGE / n).read_text(encoding="utf-8"))
        for n in names
        if (KNOWLEDGE / n).exists()
    )
    total = sum(p.stat().st_size for p in KNOWLEDGE.glob("*.md"))
    return names, size, total


def current_phase(today: date | None = None) -> str:
    """Phase drives how heavy a study plan may be."""
    today = today or date.today()
    days = (EXAM_DATE - today).days
    if days > 150:
        return "Faz 1 — kurulum ve temel (yoğun)"
    if days > 45:
        return "Faz 2 — sürdürme (düşük tempo, devamlılık kritik)"
    return "Faz 3 — sınav öncesi yoğunlaşma"


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------

def call_model(prompt: str, json_mode: bool = False) -> str:
    """Call Gemini, riding out transient overload.

    A 503 ("high demand") is Google's capacity problem, not ours, and usually
    clears in seconds. So each model gets a few attempts with backoff, then the
    next model in FALLBACK_MODELS is tried. Non-transient errors (bad key,
    bad request) are raised immediately.
    """
    import time

    from google import genai
    from google.genai import errors, types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil")

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if json_mode else "text/plain"
    )
    last_error = None
    for model in [MODEL, *FALLBACK_MODELS]:
        for attempt in range(RETRIES_PER_MODEL):
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt, config=config
                )
                return response.text or ""
            except errors.APIError as e:
                if e.code not in RETRYABLE_CODES:
                    raise
                last_error = e
                if attempt < RETRIES_PER_MODEL - 1:
                    time.sleep(2 ** (attempt + 1))  # 2s, 4s
    raise RuntimeError(
        "Gemini modelleri şu an aşırı yoğun, birkaç dakika sonra tekrar dene. "
        f"(Son hata: {last_error})"
    )


def parse_json(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    return json.loads(text)


# ---------------------------------------------------------------------------
# essay scoring
# ---------------------------------------------------------------------------

@dataclass
class Score:
    total: int
    criteria: dict = field(default_factory=dict)   # key -> {"score": int, "comment": str}
    corrections: list = field(default_factory=list)
    strengths: list = field(default_factory=list)
    priority: str = ""
    raw: str = ""


SCORING_SCHEMA = """{
  "criteria": {
    "task_achievement": {"score": 0-10, "comment": "tek cümle gerekçe"},
    "coherence":        {"score": 0-10, "comment": "tek cümle gerekçe"},
    "lexical":          {"score": 0-10, "comment": "tek cümle gerekçe"},
    "grammar":          {"score": 0-10, "comment": "tek cümle gerekçe"},
    "mechanics":        {"score": 0-10, "comment": "tek cümle gerekçe"}
  },
  "corrections": [
    {"original": "öğrencinin cümlesi", "revised": "düzeltilmiş hali", "why": "kısa sebep"}
  ],
  "strengths": ["gerçekten iyi olan şey", "..."],
  "priority": "Bir sonraki essay'de odaklanılacak TEK şey"
}"""


def score_essay(essay: str, topic: str = "") -> Score:
    """Score an essay against the 50-point rubric, returning structured data.

    The model is asked for JSON rather than prose so that every review has the
    same shape and two reviews a month apart can be compared directly. Prose
    feedback drifts in format; a schema cannot.
    """
    prompt = f"""Sen Erasmus İngilizce yeterlilik sınavına hazırlanan bir üniversite
öğrencisinin essay hocasısın. Aşağıdaki rubriğe göre değerlendir.

{load_context("feedback")}

Essay konusu: {topic or "belirtilmemiş"}

Öğrencinin essay'i:
\"\"\"
{essay}
\"\"\"

Kurallar:
- En az 5, en fazla 10 cümle düzeltmesi ver. Daha azı yüzeysel, daha fazlası boğar.
- Övgüyle bitirme. Gerçekten iyi olan şeyleri strengths'e yaz ama sorun varken
  onları yumuşatma.
- Suçluluk üretme. Ne yapılacağını söyle.
- Yorumları Türkçe yaz, düzeltilen cümleleri İngilizce bırak.
- priority alanına sadece TEK bir odak yaz.

Sadece şu JSON şemasında cevap ver, başka hiçbir şey yazma:
{SCORING_SCHEMA}"""

    raw = call_model(prompt, json_mode=True)
    data = parse_json(raw)
    criteria = data.get("criteria", {})
    total = sum(int(criteria.get(k, {}).get("score", 0)) for k, _ in RUBRIC_CRITERIA)
    return Score(
        total=total,
        criteria=criteria,
        corrections=data.get("corrections", []),
        strengths=data.get("strengths", []),
        priority=data.get("priority", ""),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# study plan
# ---------------------------------------------------------------------------

def make_plan(weak_areas: str, hours_per_week: int, history: list) -> str:
    recent = ""
    if history:
        lines = [f"- {h['created_at'][:10]}: {h['total']}/50" for h in history[:5]]
        recent = "Öğrencinin son essay puanları:\n" + "\n".join(lines)

    prompt = f"""Sen Erasmus sınavına hazırlanan bir öğrencinin çalışma koçusun.

{load_context("plan")}

Bugün: {date.today().isoformat()}
Sınav tarihi: {EXAM_DATE.isoformat()}
Bulunulan faz: {current_phase()}
Haftalık ayrılabilen süre: {hours_per_week} saat
Öğrencinin belirttiği zayıf alanlar: {weak_areas or "belirtilmemiş"}
{recent}

Bu haftaya özel, gün gün bir plan yaz. Fazın temposuna sadık kal — Faz 2'de ağır
plan verme, çünkü uygulanmayan plan terk edilir ve terk edilen plan hiç plandan
kötüdür. Toplam süre haftalık bütçeyi aşmasın.

Türkçe yaz. Markdown kullan. Gereksiz giriş cümlesi yazma, doğrudan planla başla."""
    return call_model(prompt)


# ---------------------------------------------------------------------------
# exercise generation
# ---------------------------------------------------------------------------

def make_exercise(kind: str) -> str:
    if kind == "reading":
        task = """10 paragraflık bir akademik okuma parçası üret (her paragraf 5-7 cümle,
B1-B2 seviye). Ardından TAM 10 adet boşluk doldurma cümlesi yaz — her paragraftan
bir tane, sırayla.

Kesin kurallar:
- Cevap, ilgili paragrafta GEÇEN bir kelime olmalı. Paragrafta olmayan kelime cevap olamaz.
- Şıklı soru YOK.
- Sonda cevap anahtarı ver, her cevabın yanına kaynak paragraf numarasını yaz."""
    elif kind == "essay":
        task = """Sınav formatına uygun bir essay sorusu seç ve öğrenciye ver.
Soruyu verdikten sonra: hangi essay türü olduğunu, hangi yapının beklendiğini ve
300-500 kelime için önerilen paragraf dağılımını yaz. Essay'i SEN yazma."""
    else:
        task = """Dinleme pratiği için gerçek kaynak öner. Transkript ÜRETME —
model üretimi metin gerçek konuşmanın hızını, aksanını ve duraklamalarını
taşımaz. Seviyeye uygun 3-4 gerçek kaynak öner ve her biri için nasıl
çalışılacağını yaz."""

    prompt = f"""Sen Erasmus İngilizce sınavı için alıştırma hazırlayan bir hocasın.

{load_context("exercise")}

{task}

Açıklamaları Türkçe, materyali İngilizce yaz."""
    return call_model(prompt)

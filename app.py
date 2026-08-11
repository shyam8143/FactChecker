import os
import json
import re
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % GEMINI_MODEL
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")
MAX_HISTORY = 5
DEFAULT_LANG = "en"

LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
}

SYSTEM_PROMPTS = {
    "en": (
        "You are a professional AI fact-checker. Analyze the social media post or news headline "
        "provided and fact-check it against known facts, official records and credible reporting. "
        "Respond with ONLY valid JSON, no markdown, no extra text, in exactly this format:\n"
        '{"verdict": "TRUE|FALSE|MISLEADING|UNVERIFIED", "confidence": 85, '
        '"explanation": "2-3 lines", "sources": ["source1", "source2", "source3"]}\n'
        "confidence must be an integer between 0 and 100. sources must contain exactly 3 "
        "credible, real source suggestions (e.g. official government sites, verified news "
        "organisations like Reuters, AFP, BBC, PIB). explanation must be in English."
    ),
    "hi": (
        "You are a professional AI fact-checker. Analyze the social media post or news headline "
        "provided and fact-check it against known facts, official records and credible reporting. "
        "Respond with ONLY valid JSON, no markdown, no extra text, in exactly this format:\n"
        '{"verdict": "TRUE|FALSE|MISLEADING|UNVERIFIED", "confidence": 85, '
        '"explanation": "2-3 lines", "sources": ["source1", "source2", "source3"]}\n'
        "confidence must be an integer between 0 and 100. sources must contain exactly 3 "
        "credible, real source suggestions (e.g. official government sites, verified news "
        'organisations like Reuters, AFP, BBC, PIB). explanation must be written in Hindi '
        "within the JSON string."
    ),
    "te": (
        "You are a professional AI fact-checker. Analyze the social media post or news headline "
        "provided and fact-check it against known facts, official records and credible reporting. "
        "Respond with ONLY valid JSON, no markdown, no extra text, in exactly this format:\n"
        '{"verdict": "TRUE|FALSE|MISLEADING|UNVERIFIED", "confidence": 85, '
        '"explanation": "2-3 lines", "sources": ["source1", "source2", "source3"]}\n'
        "confidence must be an integer between 0 and 100. sources must contain exactly 3 "
        "credible, real source suggestions (e.g. official government sites, verified news "
        'organisations like Reuters, AFP, BBC, PIB). explanation must be written in Telugu '
        "within the JSON string."
    ),
    "ta": (
        "You are a professional AI fact-checker. Analyze the social media post or news headline "
        "provided and fact-check it against known facts, official records and credible reporting. "
        "Respond with ONLY valid JSON, no markdown, no extra text, in exactly this format:\n"
        '{"verdict": "TRUE|FALSE|MISLEADING|UNVERIFIED", "confidence": 85, '
        '"explanation": "2-3 lines", "sources": ["source1", "source2", "source3"]}\n'
        "confidence must be an integer between 0 and 100. sources must contain exactly 3 "
        "credible, real source suggestions (e.g. official government sites, verified news "
        'organisations like Reuters, AFP, BBC, PIB). explanation must be written in Tamil '
        "within the JSON string."
    ),
}


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("No valid JSON found in model response")


def parse_verdict(data):
    verdict = str(data.get("verdict", "UNVERIFIED")).strip().upper()
    if verdict not in ("TRUE", "FALSE", "MISLEADING", "UNVERIFIED"):
        verdict = "UNVERIFIED"

    try:
        confidence = int(data.get("confidence", 50))
    except (TypeError, ValueError):
        confidence = 50
    confidence = max(0, min(100, confidence))

    explanation = str(data.get("explanation", "")).strip() or "No explanation provided."

    sources = data.get("sources", [])
    if not isinstance(sources, list):
        sources = [str(sources)]
    sources = [str(s).strip() for s in sources if str(s).strip()]
    while len(sources) < 3:
        sources.append("Verify via official government sources")
    sources = sources[:3]

    return {"verdict": verdict, "confidence": confidence, "explanation": explanation, "sources": sources}


def fallback_result():
    return {
        "verdict": "UNVERIFIED",
        "confidence": 0,
        "explanation": "Could not reach the fact-check AI. Please check your GEMINI_API_KEY and internet connection, then try again.",
        "sources": [
            "Official government sources",
            "Major verified news agencies (Reuters, AFP)",
            "Fact-checking sites (snopes.com, factcheck.org)",
        ],
    }


def check_fact(claim, lang):
    prompt = (
        SYSTEM_PROMPTS[lang]
        + '\n\nClaim to fact-check: """'
        + claim
        + '"""'
    )
    url = GEMINI_API_URL
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
        },
    }
    response = requests.post(url, headers=headers, params=params, json=body, timeout=60)
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("No candidates in Gemini response: %s" % str(data)[:500])
    text = candidates[0]["content"]["parts"][0]["text"]
    return extract_json(text)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/check", methods=["POST"])
def check():
    data = request.get_json(silent=True) or {}
    claim = (data.get("claim") or "").strip()
    lang = (data.get("lang") or DEFAULT_LANG).strip()
    if lang not in SYSTEM_PROMPTS:
        lang = DEFAULT_LANG

    if not claim:
        return jsonify({"error": "Please enter a claim to fact-check."}), 400
    if len(claim) > 3000:
        return jsonify({"error": "Claim is too long (max 3000 characters)."}), 400

    if not GEMINI_API_KEY:
        result = fallback_result()
        result["explanation"] = (
            "GEMINI_API_KEY not found. On Vercel, set it in Project > Settings > Environment "
            "Variables (key must start with AIza) and redeploy; locally, add it to .env."
        )
    else:
        try:
            result = parse_verdict(check_fact(claim, lang))
        except Exception:
            result = fallback_result()

    entry = {
        "claim": claim,
        "verdict": result["verdict"],
        "confidence": result["confidence"],
        "explanation": result["explanation"],
        "sources": result["sources"],
        "lang": lang,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    history = load_history()
    history.insert(0, entry)
    del history[MAX_HISTORY:]
    save_history(history)

    return jsonify({"result": entry, "history": history})


@app.route("/api/history", methods=["GET"])
def history():
    return jsonify({"history": load_history()})


@app.route("/api/clear_history", methods=["POST"])
def clear_history():
    save_history([])
    return jsonify({"history": [], "ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
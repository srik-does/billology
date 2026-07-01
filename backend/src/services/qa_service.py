"""Dual-path grounded Q&A (US9 / FR-018, Principle VI).

Numeric path: derive a constrained query *intent* (category / month / aggregate),
run a safe allowlisted query, and compute the figure in deterministic Decimal code
over the returned rows. The LLM never authors SQL and never computes the number.

Semantic path: embed the question locally, retrieve real saved rows via the
match_bills pgvector RPC, and (optionally) summarize over those rows only.

Anything we can't answer from saved records returns an explicit "not available" —
never an estimate.

Routing is heuristic-first (works without a Groq key); the LLM is an optional
enhancement for the semantic summary.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Any, Callable, Optional

from src.services import persistence

# Map keyword hints in the question to a controlled category name.
_CATEGORY_HINTS = [
    ("recharge", "Telecom/Recharge"),
    ("telecom", "Telecom/Recharge"),
    ("mobile", "Telecom/Recharge"),
    ("grocer", "Groceries"),
    ("utilit", "Utilities"),
    ("electric", "Utilities"),
    ("food", "Food & Dining"),
    ("dining", "Food & Dining"),
    ("restaurant", "Food & Dining"),
    ("shopping", "Shopping"),
]

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_NUMERIC_TRIGGERS = (
    "how much",
    "how many",
    "total",
    "spend",
    "spent",
    "sum",
    "count",
    "number of",
    "last time",
    "latest",
    "most recent",
    "average",
    "avg",
)


def _to_decimal(v) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


# Numeric answers are code-generated template strings; translate the templates
# (the figures themselves are computed, never translated).
_TEMPLATES = {
    "en": {
        "sum": "You spent ₹{total} on {cat}{who}{when} across {n} bill(s).",
        "count": "You have {n} {cat} bill(s){who}{when}.",
        "average": "Your average {cat} bill{who}{when} is ₹{avg} (over {n} bill(s)).",
        "latest": "Your most recent {cat} bill was ₹{amount} on {date} ({merchant}).",
        "unanswerable": "I don't have that information in your saved bills.",
        "ask": "Please ask a question about your spending.",
        # Item-level answers (aggregate over individual line items, not whole bills).
        "item_sum": "You spent ₹{total} on {item}{who}{when} across {n} purchase(s).",
        "item_count": "You bought {item}{who}{when} {n} time(s).",
        "item_average": "On average you spent ₹{avg} on {item} per purchase{who}{when} ({n} purchase(s)).",
        "item_latest": "You last bought {item} for ₹{amount} on {date} ({merchant}).",
    },
    "hi": {
        "sum": "आपने {cat}{who}{when} पर {n} बिल में कुल ₹{total} खर्च किए।",
        "count": "आपके पास {cat}{who}{when} के {n} बिल हैं।",
        "average": "आपका औसत {cat} बिल{who}{when} ₹{avg} है ({n} बिल पर)।",
        "latest": "आपका सबसे हालिया {cat} बिल ₹{amount} था, {date} को ({merchant})।",
        "unanswerable": "आपके सहेजे गए बिलों में यह जानकारी उपलब्ध नहीं है।",
        "ask": "कृपया अपने खर्च के बारे में कोई प्रश्न पूछें।",
        "item_sum": "आपने {item}{who}{when} पर {n} बार में कुल ₹{total} खर्च किए।",
        "item_count": "आपने {item}{who}{when} {n} बार खरीदा।",
        "item_average": "आप {item} पर प्रति खरीद औसतन ₹{avg} खर्च करते हैं{who}{when} ({n} खरीद)।",
        "item_latest": "आपने आख़िरी बार {item} ₹{amount} में {date} को खरीदा ({merchant})।",
    },
    "te": {
        "sum": "మీరు {cat}{who}{when} పై {n} బిల్లులలో మొత్తం ₹{total} ఖర్చు చేశారు.",
        "count": "మీ వద్ద {cat}{who}{when} బిల్లులు {n} ఉన్నాయి.",
        "average": "మీ సగటు {cat} బిల్లు{who}{when} ₹{avg} ({n} బిల్లులపై).",
        "latest": "మీ ఇటీవలి {cat} బిల్లు ₹{amount}, {date} న ({merchant}).",
        "unanswerable": "మీ సేవ్ చేసిన బిల్లులలో ఆ సమాచారం లేదు.",
        "ask": "దయచేసి మీ ఖర్చు గురించి ప్రశ్న అడగండి.",
        "item_sum": "మీరు {item}{who}{when} పై {n} సార్లు మొత్తం ₹{total} ఖర్చు చేశారు.",
        "item_count": "మీరు {item}{who}{when} {n} సార్లు కొన్నారు.",
        "item_average": "మీరు {item} పై ఒక్కో కొనుగోలుకు సగటున ₹{avg} ఖర్చు చేస్తారు{who}{when} ({n} కొనుగోళ్లు).",
        "item_latest": "మీరు చివరిసారి {item} ను ₹{amount} కు {date} న కొన్నారు ({merchant}).",
    },
    # The languages below are machine-authored translations pending
    # native-speaker review (same status as the client string tables).
    "ta": {
        "sum": "நீங்கள் {cat}{who}{when} மீது {n} பில்களில் மொத்தம் ₹{total} செலவழித்தீர்கள்.",
        "count": "உங்களிடம் {cat}{who}{when} பில்கள் {n} உள்ளன.",
        "average": "உங்கள் சராசரி {cat} பில்{who}{when} ₹{avg} ({n} பில்களில்).",
        "latest": "உங்கள் சமீபத்திய {cat} பில் ₹{amount}, {date} அன்று ({merchant}).",
        "unanswerable": "உங்கள் சேமித்த பில்களில் அந்தத் தகவல் இல்லை.",
        "ask": "உங்கள் செலவு பற்றி ஒரு கேள்வி கேளுங்கள்.",
        "item_sum": "நீங்கள் {item}{who}{when} மீது {n} முறை மொத்தம் ₹{total} செலவழித்தீர்கள்.",
        "item_count": "நீங்கள் {item}{who}{when} {n} முறை வாங்கினீர்கள்.",
        "item_average": "நீங்கள் {item} மீது ஒரு வாங்கலுக்கு சராசரியாக ₹{avg} செலவழிக்கிறீர்கள்{who}{when} ({n} வாங்கல்கள்).",
        "item_latest": "நீங்கள் கடைசியாக {item} ஐ ₹{amount} க்கு {date} அன்று வாங்கினீர்கள் ({merchant}).",
    },
    "kn": {
        "sum": "ನೀವು {cat}{who}{when} ಮೇಲೆ {n} ಬಿಲ್‌ಗಳಲ್ಲಿ ಒಟ್ಟು ₹{total} ಖರ್ಚು ಮಾಡಿದ್ದೀರಿ.",
        "count": "ನಿಮ್ಮ ಬಳಿ {cat}{who}{when} ಬಿಲ್‌ಗಳು {n} ಇವೆ.",
        "average": "ನಿಮ್ಮ ಸರಾಸರಿ {cat} ಬಿಲ್{who}{when} ₹{avg} ({n} ಬಿಲ್‌ಗಳಲ್ಲಿ).",
        "latest": "ನಿಮ್ಮ ಇತ್ತೀಚಿನ {cat} ಬಿಲ್ ₹{amount}, {date} ರಂದು ({merchant}).",
        "unanswerable": "ನಿಮ್ಮ ಉಳಿಸಿದ ಬಿಲ್‌ಗಳಲ್ಲಿ ಆ ಮಾಹಿತಿ ಇಲ್ಲ.",
        "ask": "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಖರ್ಚಿನ ಬಗ್ಗೆ ಪ್ರಶ್ನೆ ಕೇಳಿ.",
        "item_sum": "ನೀವು {item}{who}{when} ಮೇಲೆ {n} ಬಾರಿ ಒಟ್ಟು ₹{total} ಖರ್ಚು ಮಾಡಿದ್ದೀರಿ.",
        "item_count": "ನೀವು {item}{who}{when} {n} ಬಾರಿ ಖರೀದಿಸಿದ್ದೀರಿ.",
        "item_average": "ನೀವು {item} ಮೇಲೆ ಪ್ರತಿ ಖರೀದಿಗೆ ಸರಾಸರಿ ₹{avg} ಖರ್ಚು ಮಾಡುತ್ತೀರಿ{who}{when} ({n} ಖರೀದಿಗಳು).",
        "item_latest": "ನೀವು ಕೊನೆಯ ಬಾರಿ {item} ಅನ್ನು ₹{amount} ಕ್ಕೆ {date} ರಂದು ಖರೀದಿಸಿದ್ದೀರಿ ({merchant}).",
    },
    "ml": {
        "sum": "നിങ്ങൾ {cat}{who}{when} ൽ {n} ബില്ലുകളിലായി ആകെ ₹{total} ചെലവഴിച്ചു.",
        "count": "നിങ്ങൾക്ക് {cat}{who}{when} ബില്ലുകൾ {n} ഉണ്ട്.",
        "average": "നിങ്ങളുടെ ശരാശരി {cat} ബിൽ{who}{when} ₹{avg} ({n} ബില്ലുകളിൽ).",
        "latest": "നിങ്ങളുടെ ഏറ്റവും പുതിയ {cat} ബിൽ ₹{amount}, {date} ന് ({merchant}).",
        "unanswerable": "നിങ്ങളുടെ സേവ് ചെയ്ത ബില്ലുകളിൽ ആ വിവരം ഇല്ല.",
        "ask": "ദയവായി നിങ്ങളുടെ ചെലവിനെക്കുറിച്ച് ഒരു ചോദ്യം ചോദിക്കൂ.",
        "item_sum": "നിങ്ങൾ {item}{who}{when} ന് {n} തവണയായി ആകെ ₹{total} ചെലവഴിച്ചു.",
        "item_count": "നിങ്ങൾ {item}{who}{when} {n} തവണ വാങ്ങി.",
        "item_average": "നിങ്ങൾ {item} ന് ഓരോ വാങ്ങലിനും ശരാശരി ₹{avg} ചെലവഴിക്കുന്നു{who}{when} ({n} വാങ്ങലുകൾ).",
        "item_latest": "നിങ്ങൾ അവസാനമായി {item} ₹{amount} ന് {date} ന് വാങ്ങി ({merchant}).",
    },
    "bn": {
        "sum": "আপনি {cat}{who}{when} এ {n} বিলে মোট ₹{total} খরচ করেছেন।",
        "count": "আপনার {cat}{who}{when} বিল আছে {n}টি।",
        "average": "আপনার গড় {cat} বিল{who}{when} ₹{avg} ({n}টি বিলে)।",
        "latest": "আপনার সাম্প্রতিকতম {cat} বিল ছিল ₹{amount}, {date} তারিখে ({merchant})।",
        "unanswerable": "আপনার সংরক্ষিত বিলে সেই তথ্য নেই।",
        "ask": "অনুগ্রহ করে আপনার খরচ নিয়ে একটি প্রশ্ন করুন।",
        "item_sum": "আপনি {item}{who}{when} এ {n} বার মোট ₹{total} খরচ করেছেন।",
        "item_count": "আপনি {item}{who}{when} {n} বার কিনেছেন।",
        "item_average": "আপনি {item} এ প্রতি কেনায় গড়ে ₹{avg} খরচ করেন{who}{when} ({n} বার কেনা)।",
        "item_latest": "আপনি শেষবার {item} ₹{amount} এ {date} তারিখে কিনেছেন ({merchant})।",
    },
    "mr": {
        "sum": "तुम्ही {cat}{who}{when} वर {n} बिलांमध्ये एकूण ₹{total} खर्च केले.",
        "count": "तुमच्याकडे {cat}{who}{when} ची {n} बिले आहेत.",
        "average": "तुमचे सरासरी {cat} बिल{who}{when} ₹{avg} आहे ({n} बिलांवर).",
        "latest": "तुमचे अलीकडील {cat} बिल ₹{amount} होते, {date} रोजी ({merchant}).",
        "unanswerable": "तुमच्या जतन केलेल्या बिलांमध्ये ती माहिती नाही.",
        "ask": "कृपया तुमच्या खर्चाबद्दल प्रश्न विचारा.",
        "item_sum": "तुम्ही {item}{who}{when} वर {n} वेळा एकूण ₹{total} खर्च केले.",
        "item_count": "तुम्ही {item}{who}{when} {n} वेळा खरेदी केले.",
        "item_average": "तुम्ही {item} वर प्रत्येक खरेदीला सरासरी ₹{avg} खर्च करता{who}{when} ({n} खरेदी).",
        "item_latest": "तुम्ही शेवटची {item} ₹{amount} ला {date} रोजी खरेदी केली ({merchant}).",
    },
    "gu": {
        "sum": "તમે {cat}{who}{when} પર {n} બિલમાં કુલ ₹{total} ખર્ચ કર્યો.",
        "count": "તમારી પાસે {cat}{who}{when} નાં {n} બિલ છે.",
        "average": "તમારું સરેરાશ {cat} બિલ{who}{when} ₹{avg} છે ({n} બિલ પર).",
        "latest": "તમારું તાજેતરનું {cat} બિલ ₹{amount} હતું, {date} ના રોજ ({merchant}).",
        "unanswerable": "તમારાં સાચવેલાં બિલમાં તે માહિતી નથી.",
        "ask": "કૃપા કરી તમારા ખર્ચ વિશે પ્રશ્ન પૂછો.",
        "item_sum": "તમે {item}{who}{when} પર {n} વાર કુલ ₹{total} ખર્ચ કર્યો.",
        "item_count": "તમે {item}{who}{when} {n} વાર ખરીદ્યું.",
        "item_average": "તમે {item} પર દરેક ખરીદી માટે સરેરાશ ₹{avg} ખર્ચ કરો છો{who}{when} ({n} ખરીદી).",
        "item_latest": "તમે છેલ્લે {item} ₹{amount} માં {date} ના રોજ ખરીદ્યું ({merchant}).",
    },
    "pa": {
        "sum": "ਤੁਸੀਂ {cat}{who}{when} 'ਤੇ {n} ਬਿੱਲਾਂ ਵਿੱਚ ਕੁੱਲ ₹{total} ਖਰਚ ਕੀਤੇ।",
        "count": "ਤੁਹਾਡੇ ਕੋਲ {cat}{who}{when} ਦੇ {n} ਬਿੱਲ ਹਨ।",
        "average": "ਤੁਹਾਡਾ ਔਸਤ {cat} ਬਿੱਲ{who}{when} ₹{avg} ਹੈ ({n} ਬਿੱਲਾਂ 'ਤੇ)।",
        "latest": "ਤੁਹਾਡਾ ਸਭ ਤੋਂ ਤਾਜ਼ਾ {cat} ਬਿੱਲ ₹{amount} ਸੀ, {date} ਨੂੰ ({merchant})।",
        "unanswerable": "ਤੁਹਾਡੇ ਸੰਭਾਲੇ ਬਿੱਲਾਂ ਵਿੱਚ ਉਹ ਜਾਣਕਾਰੀ ਨਹੀਂ।",
        "ask": "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੇ ਖਰਚ ਬਾਰੇ ਸਵਾਲ ਪੁੱਛੋ।",
        "item_sum": "ਤੁਸੀਂ {item}{who}{when} 'ਤੇ {n} ਵਾਰ ਕੁੱਲ ₹{total} ਖਰਚ ਕੀਤੇ।",
        "item_count": "ਤੁਸੀਂ {item}{who}{when} {n} ਵਾਰ ਖਰੀਦਿਆ।",
        "item_average": "ਤੁਸੀਂ {item} 'ਤੇ ਹਰ ਖਰੀਦ ਲਈ ਔਸਤਨ ₹{avg} ਖਰਚ ਕਰਦੇ ਹੋ{who}{when} ({n} ਖਰੀਦਾਂ)।",
        "item_latest": "ਤੁਸੀਂ ਆਖਰੀ ਵਾਰ {item} ₹{amount} ਵਿੱਚ {date} ਨੂੰ ਖਰੀਦਿਆ ({merchant})।",
    },
    "or": {
        "sum": "ଆପଣ {cat}{who}{when} ରେ {n} ବିଲ୍‌ରେ ମୋଟ ₹{total} ଖର୍ଚ୍ଚ କରିଛନ୍ତି।",
        "count": "ଆପଣଙ୍କ ପାଖରେ {cat}{who}{when} ର {n} ବିଲ୍ ଅଛି।",
        "average": "ଆପଣଙ୍କ ହାରାହାରି {cat} ବିଲ୍{who}{when} ₹{avg} ({n} ବିଲ୍ ଉପରେ)।",
        "latest": "ଆପଣଙ୍କ ସଦ୍ୟତମ {cat} ବିଲ୍ ₹{amount} ଥିଲା, {date} ରେ ({merchant})।",
        "unanswerable": "ଆପଣଙ୍କ ସେଭ୍ ହୋଇଥିବା ବିଲ୍‌ରେ ସେହି ସୂଚନା ନାହିଁ।",
        "ask": "ଦୟାକରି ଆପଣଙ୍କ ଖର୍ଚ୍ଚ ବିଷୟରେ ପ୍ରଶ୍ନ ପଚାରନ୍ତୁ।",
        "item_sum": "ଆପଣ {item}{who}{when} ରେ {n} ଥର ମୋଟ ₹{total} ଖର୍ଚ୍ଚ କରିଛନ୍ତି।",
        "item_count": "ଆପଣ {item}{who}{when} {n} ଥର କିଣିଛନ୍ତି।",
        "item_average": "ଆପଣ {item} ରେ ପ୍ରତି କିଣାରେ ହାରାହାରି ₹{avg} ଖର୍ଚ୍ଚ କରନ୍ତି{who}{when} ({n} କିଣା)।",
        "item_latest": "ଆପଣ ଶେଷ ଥର {item} କୁ ₹{amount} ରେ {date} ରେ କିଣିଥିଲେ ({merchant})।",
    },
    "as": {
        "sum": "আপুনি {cat}{who}{when} ত {n} বিলত মুঠ ₹{total} খৰচ কৰিছে।",
        "count": "আপোনাৰ {cat}{who}{when} ৰ {n} খন বিল আছে।",
        "average": "আপোনাৰ গড় {cat} বিল{who}{when} ₹{avg} ({n} খন বিলত)।",
        "latest": "আপোনাৰ শেহতীয়া {cat} বিল আছিল ₹{amount}, {date} ত ({merchant})।",
        "unanswerable": "আপোনাৰ সংৰক্ষিত বিলত সেই তথ্য নাই।",
        "ask": "অনুগ্ৰহ কৰি আপোনাৰ খৰচৰ বিষয়ে প্ৰশ্ন সোধক।",
        "item_sum": "আপুনি {item}{who}{when} ত {n} বাৰ মুঠ ₹{total} খৰচ কৰিছে।",
        "item_count": "আপুনি {item}{who}{when} {n} বাৰ কিনিছে।",
        "item_average": "আপুনি {item} ত প্ৰতি কিনাত গড়ে ₹{avg} খৰচ কৰে{who}{when} ({n} বাৰ কিনা)।",
        "item_latest": "আপুনি শেষবাৰ {item} ₹{amount} ত {date} ত কিনিছিল ({merchant})।",
    },
    "ur": {
        "sum": "آپ نے {cat}{who}{when} پر {n} بلوں میں کل ₹{total} خرچ کیے۔",
        "count": "آپ کے پاس {cat}{who}{when} کے {n} بل ہیں۔",
        "average": "آپ کا اوسط {cat} بل{who}{when} ₹{avg} ہے ({n} بلوں پر)۔",
        "latest": "آپ کا حالیہ ترین {cat} بل ₹{amount} تھا، {date} کو ({merchant})۔",
        "unanswerable": "آپ کے محفوظ بلوں میں وہ معلومات نہیں۔",
        "ask": "براہ کرم اپنے خرچ کے بارے میں سوال پوچھیں۔",
        "item_sum": "آپ نے {item}{who}{when} پر {n} بار کل ₹{total} خرچ کیے۔",
        "item_count": "آپ نے {item}{who}{when} {n} بار خریدا۔",
        "item_average": "آپ {item} پر ہر خرید پر اوسطاً ₹{avg} خرچ کرتے ہیں{who}{when} ({n} خریداری)۔",
        "item_latest": "آپ نے آخری بار {item} ₹{amount} میں {date} کو خریدا ({merchant})۔",
    },
}


def _t(key: str) -> str:
    from src.services.request_context import language

    return _TEMPLATES.get(language.get(), _TEMPLATES["en"]).get(key, _TEMPLATES["en"][key])


def _classify(question: str) -> str:
    q = question.lower()
    return "numeric" if any(t in q for t in _NUMERIC_TRIGGERS) else "semantic"


# --- forgiving matching -------------------------------------------------------


def _norm(s: str) -> str:
    """Collapse to lowercase alphanumerics so 'D-Mart' == 'd mart' == 'DMART'."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _fuzzy_merchant(needle: str, merchant: str) -> bool:
    """Spelling/punctuation-tolerant merchant match (fixes the 'small change in
    search keys → No bills found' cliff)."""
    a, b = _norm(needle), _norm(merchant)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.8


# Question words that carry no retrieval signal.
_STOPWORDS = frozenset(
    "the a an my i me of on in at for to from did do was is are and or with "
    "how much many what where when which who show find get all any bill bills "
    "spend spent spending buy bought purchase purchased paid pay last this "
    "that month year time recent latest total amount".split()
)


def _tokens(s: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9]+", (s or "").lower())
        if len(t) >= 3 and t not in _STOPWORDS
    }


def _keyword_score(question_tokens: set[str], row_text: str) -> int:
    """Count question tokens that hit the row's descriptive text (tolerating
    joined/split words: 'dmart' hits 'd mart' and vice versa)."""
    row_tokens = _tokens(row_text)
    joined = _norm(row_text)
    score = 0
    for qt in question_tokens:
        if qt in row_tokens or (len(qt) >= 4 and qt in joined):
            score += 1
    return score


def _intent(question: str) -> dict[str, Any]:
    q = question.lower()
    category = next((name for hint, name in _CATEGORY_HINTS if hint in q), None)
    month = next((num for token, num in _MONTHS.items() if re.search(rf"\b{token}", q)), None)
    if any(w in q for w in ("last time", "latest", "most recent")):
        aggregate = "latest"
    elif any(w in q for w in ("how many", "count", "number of")):
        aggregate = "count"
    else:
        aggregate = "sum"
    return {"category": category, "month": month, "merchant": None, "aggregate": aggregate}


def _llm_intent(question: str, db, llm) -> Optional[dict[str, Any]]:
    """LLM translates the question; every field is validated/allowlisted here.

    The LLM picks WHICH filters apply (Principle VI: question → query); it never
    computes the figure. Returns None on any failure → heuristic fallback.
    """
    if llm is None:
        return None
    try:
        from datetime import date

        cats = [c.get("name") for c in db.select("categories") if c.get("name")]
        raw = llm.derive_intent(question, cats, date.today().isoformat())
    except Exception:  # noqa: BLE001 - LLM optional
        return None
    if not isinstance(raw, dict):
        return None

    path = raw.get("path")
    if path not in ("numeric", "semantic"):
        return None
    category = raw.get("category")
    if not (isinstance(category, str) and category in cats):
        category = None
    month = raw.get("month")
    if not (isinstance(month, str) and re.fullmatch(r"\d{4}-\d{2}", month)):
        month = None
    merchant = raw.get("merchant")
    merchant = (
        merchant.strip() if isinstance(merchant, str) and 0 < len(merchant.strip()) <= 60 else None
    )
    aggregate = raw.get("aggregate")
    if aggregate not in ("sum", "count", "latest", "average"):
        aggregate = "sum"
    return {
        "path": path,
        "category": category,
        "month": month,
        "merchant": merchant,
        "aggregate": aggregate,
    }


def _load_bills(db) -> list[dict[str, Any]]:
    """Fetch saved bills with their category name resolved (single small dataset)."""
    cats = {c["id"]: c.get("name") for c in db.select("categories")}
    rows = []
    for b in db.select("bills"):
        if b.get("status") and b["status"] != "saved":
            continue
        rows.append(
            {
                "id": b.get("id"),
                "merchant": b.get("merchant"),
                "bill_date": b.get("bill_date"),
                "total_amount": b.get("total_amount"),
                "category": cats.get(b.get("category_id")),
                "tags": b.get("tags"),
            }
        )
    return rows


def _searchable_text(row: dict[str, Any], items_by_bill: dict[Any, list[str]]) -> str:
    """All descriptive text for keyword matching: merchant, category, tags, items."""
    parts = [row.get("merchant") or "", row.get("category") or "", row.get("tags") or ""]
    parts.extend(items_by_bill.get(row.get("id"), []))
    return " ".join(parts)


def _load_items_full(db) -> dict[Any, list[dict[str, Any]]]:
    """Per-bill line items (description + amount) for itemized semantic answers.

    Lets the summarizer break a bill down item-by-item instead of seeing only
    the total. Amounts are the real stored ``line_total`` values (Principle VI:
    the answer is grounded in saved records, never invented)."""
    by_bill: dict[Any, list[dict[str, Any]]] = {}
    for item in db.select("line_items"):
        desc = item.get("description")
        if not desc:
            continue
        by_bill.setdefault(item.get("bill_id"), []).append(
            {
                "item": desc,
                "amount": str(item["line_total"]) if item.get("line_total") is not None else None,
            }
        )
    return by_bill


def _summary(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "merchant": row.get("merchant"),
        "bill_date": row.get("bill_date"),
        "total_amount": str(row.get("total_amount"))
        if row.get("total_amount") is not None
        else None,
        "category": row.get("category"),
    }


def _summary_with_items(row: dict, items_full: dict[Any, list[dict[str, Any]]]) -> dict:
    """A semantic record carrying its bill's line-item breakdown when available,
    so questions like 'break down this bill' can be answered from the items."""
    summary = _summary(row)
    items = items_full.get(row.get("id"))
    if items:
        summary["line_items"] = items
    return summary


def _unanswerable(reason: Optional[str] = None) -> dict:
    return {
        "path": "unanswerable",
        "answer": reason or _t("unanswerable"),
        "records": [],
        "executed_query": None,
    }


def _apply_filters(intent: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if intent["category"]:
        rows = [r for r in rows if (r["category"] or "").lower() == intent["category"].lower()]
    if intent["month"] is not None:
        if isinstance(intent["month"], int):  # heuristic path: bare month number
            rows = [r for r in rows if _month_of(r["bill_date"]) == intent["month"]]
        else:  # LLM path: "YYYY-MM"
            rows = [r for r in rows if str(r["bill_date"] or "").startswith(intent["month"])]
    if intent.get("merchant"):
        needle = intent["merchant"]
        rows = [
            r
            for r in rows
            if _fuzzy_merchant(needle, r["merchant"] or "")
            or _keyword_score(_tokens(needle), r.get("tags") or "") > 0
        ]
    return rows


def _item_tokens(question: str, intent: dict[str, Any]) -> set[str]:
    """Question words that could name a specific product, with the matched
    merchant and category-hint words removed (those are not item names)."""
    toks = _tokens(question)
    if intent.get("merchant"):
        toks -= _tokens(intent["merchant"])
    toks -= {t for hint, _ in _CATEGORY_HINTS for t in _tokens(hint)}
    return toks


def _load_line_items(db) -> list[dict[str, Any]]:
    """Saved line items joined with their parent bill's merchant/date/category."""
    cats = {c["id"]: c.get("name") for c in db.select("categories")}
    bills = {
        b["id"]: b for b in db.select("bills") if not (b.get("status") and b["status"] != "saved")
    }
    rows: list[dict[str, Any]] = []
    for item in db.select("line_items"):
        bill = bills.get(item.get("bill_id"))
        if bill is None:
            continue
        rows.append(
            {
                "description": item.get("description") or "",
                "line_total": item.get("line_total"),
                "merchant": bill.get("merchant"),
                "bill_date": bill.get("bill_date"),
                "category": cats.get(bill.get("category_id")),
            }
        )
    return rows


def _item_record(row: dict) -> dict:
    """A purchase record: the item's own amount (line_total), not the bill total."""
    return {
        "merchant": row.get("merchant"),
        "bill_date": row.get("bill_date"),
        "total_amount": str(row["line_total"]) if row.get("line_total") is not None else None,
        "category": row.get("category"),
        "item": row.get("description"),
    }


def _item_numeric(question: str, db, intent: dict[str, Any]) -> Optional[dict]:
    """Aggregate over individual LINE ITEMS when the question names a specific
    product (e.g. "how much did I spend on paneer at this restaurant?").

    Returns None when the question's item words match no saved line-item
    description, so the caller falls back to whole-bill aggregation. The figure
    is summed in Decimal code from real ``line_total`` values (Principle I).
    """
    item_tokens = _item_tokens(question, intent)
    if not item_tokens:
        return None

    rows = _load_line_items(db)
    # The same bill-level filters (merchant / month) narrow the purchases.
    if intent.get("merchant"):
        rows = [r for r in rows if _fuzzy_merchant(intent["merchant"], r["merchant"] or "")]
    if intent["month"] is not None:
        if isinstance(intent["month"], int):
            rows = [r for r in rows if _month_of(r["bill_date"]) == intent["month"]]
        else:
            rows = [r for r in rows if str(r["bill_date"] or "").startswith(intent["month"])]

    matched = [r for r in rows if _keyword_score(item_tokens, r["description"]) > 0]
    if not matched:
        return None

    words = re.findall(r"[a-z0-9]+", question.lower())
    item = " ".join(w for w in words if w in item_tokens) or "that item"
    who = f" at {intent['merchant']}" if intent.get("merchant") else ""
    when = f" in {intent['month']}" if intent["month"] is not None else ""
    desc = f"{intent['aggregate']}(line_total) WHERE item~'{item}'{who}{when}"

    if intent["aggregate"] == "latest":
        latest = max(matched, key=lambda r: r["bill_date"] or "")
        return {
            "path": "numeric",
            "answer": _t("item_latest").format(
                item=item,
                amount=latest["line_total"],
                date=latest["bill_date"],
                merchant=latest["merchant"],
            ),
            "records": [_item_record(latest)],
            "executed_query": desc,
        }
    if intent["aggregate"] == "count":
        return {
            "path": "numeric",
            "answer": _t("item_count").format(item=item, who=who, when=when, n=len(matched)),
            "records": [_item_record(r) for r in matched],
            "executed_query": desc,
        }
    total = sum((_to_decimal(r["line_total"]) for r in matched), Decimal("0"))
    if intent["aggregate"] == "average":
        avg = (total / len(matched)).quantize(Decimal("0.01"))
        return {
            "path": "numeric",
            "answer": _t("item_average").format(
                item=item, who=who, when=when, avg=avg, n=len(matched)
            ),
            "records": [_item_record(r) for r in matched],
            "executed_query": desc,
        }
    return {
        "path": "numeric",
        "answer": _t("item_sum").format(total=total, item=item, who=who, when=when, n=len(matched)),
        "records": [_item_record(r) for r in matched],
        "executed_query": desc,
    }


def _numeric(question: str, db, intent: Optional[dict[str, Any]] = None) -> dict:
    intent = intent or _intent(question)
    # A question that names a specific product is answered from line items, not
    # whole-bill totals (returns None → fall through to bill-level aggregation).
    item_answer = _item_numeric(question, db, intent)
    if item_answer is not None:
        return item_answer
    all_rows = _load_bills(db)
    rows = _apply_filters(intent, all_rows)

    # A named merchant is the precise filter; a guessed category must not zero
    # it out (e.g. "DMart" guessed as Shopping when its bills are Groceries).
    if not rows and intent.get("merchant") and intent["category"]:
        intent = {**intent, "category": None}
        rows = _apply_filters(intent, all_rows)

    if not rows:
        return _unanswerable()

    cat = intent["category"] or "all categories"
    when = f" in {intent['month']}" if intent["month"] is not None else ""
    who = f" at {intent['merchant']}" if intent.get("merchant") else ""
    desc = f"{intent['aggregate']}(total_amount) WHERE category={cat}{who}{when}"

    if intent["aggregate"] == "latest":
        latest = max(rows, key=lambda r: r["bill_date"] or "")
        answer = _t("latest").format(
            cat=cat,
            amount=latest["total_amount"],
            date=latest["bill_date"],
            merchant=latest["merchant"],
        )
        return {
            "path": "numeric",
            "answer": answer,
            "records": [_summary(latest)],
            "executed_query": desc,
        }

    if intent["aggregate"] == "count":
        return {
            "path": "numeric",
            "answer": _t("count").format(n=len(rows), cat=cat, who=who, when=when),
            "records": [_summary(r) for r in rows],
            "executed_query": desc,
        }

    total = sum((_to_decimal(r["total_amount"]) for r in rows), Decimal("0"))
    if intent["aggregate"] == "average":
        avg = (total / len(rows)).quantize(Decimal("0.01"))
        return {
            "path": "numeric",
            "answer": _t("average").format(cat=cat, who=who, when=when, avg=avg, n=len(rows)),
            "records": [_summary(r) for r in rows],
            "executed_query": desc,
        }
    return {
        "path": "numeric",
        "answer": _t("sum").format(total=total, cat=cat, who=who, when=when, n=len(rows)),
        "records": [_summary(r) for r in rows],
        "executed_query": desc,
    }


def _month_of(bill_date) -> Optional[int]:
    if not bill_date:
        return None
    m = re.match(r"\d{4}-(\d{2})", str(bill_date))
    return int(m.group(1)) if m else None


def _semantic(question: str, db, embed_fn, llm, k: int = 5) -> dict:
    """Hybrid retrieval: vector similarity + keyword/tag matching, merged.

    Either signal alone can surface a bill, so a wording change that misses one
    path is caught by the other; works keyword-only when no embedder is set.
    """
    # Full line items per bill, used both for keyword matching and to give the
    # summarizer an itemized breakdown (not just the total).
    items_full = _load_items_full(db)
    descriptions = {bid: [it["item"] for it in items] for bid, items in items_full.items()}

    matches: list[dict[str, Any]] = []
    if embed_fn is not None:
        from src.services.bill_writer import vector_literal

        vec = vector_literal(embed_fn(question))
        matches = db.match_bills(vec, k)
        # The match_bills RPC returns category_id (uuid) but not the category
        # name; resolve names so retrieved records carry their category.
        cat_names = {c["id"]: c.get("name") for c in db.select("categories")}
        for m in matches:
            m["category"] = cat_names.get(m.get("category_id"))

    # Keyword pass over merchant/category/tags/item descriptions.
    question_tokens = _tokens(question)
    if question_tokens:
        all_rows = _load_bills(db)
        seen_ids = {m.get("id") for m in matches}
        scored = sorted(
            (
                (row, _keyword_score(question_tokens, _searchable_text(row, descriptions)))
                for row in all_rows
                if row["id"] not in seen_ids
            ),
            key=lambda pair: -pair[1],
        )
        matches.extend(row for row, score in scored[:k] if score > 0)

    if not matches:
        return _unanswerable()

    records = [_summary_with_items(m, items_full) for m in matches[: k + 1]]
    answer = None
    if llm is not None:
        try:
            answer = llm.summarize_results(question, records)
        except Exception:
            answer = None
    if not answer:
        merchants = ", ".join(r["merchant"] for r in records if r.get("merchant"))
        answer = f"Found {len(records)} matching bill(s): {merchants}."
    return {"path": "semantic", "answer": answer, "records": records, "executed_query": None}


def answer_question(
    question: str,
    *,
    db=persistence,
    embed_fn: Optional[Callable[[str], list[float]]] = None,
    llm=None,
) -> dict:
    question = (question or "").strip()
    if not question:
        return _unanswerable(_t("ask"))
    # Preferred routing: LLM translates the question into a validated intent
    # (Principle VI). Heuristic keyword routing remains the no-LLM fallback.
    intent = _llm_intent(question, db, llm)
    if intent is not None:
        if intent["path"] == "numeric":
            result = _numeric(question, db, intent)
            # A named merchant that matched nothing may just be spelled
            # differently — degrade to retrieval (closest matches) instead of
            # a hard "no bills found". Category-only misses stay honest: "no
            # Utilities bills" is the correct answer, not a lookalike list.
            if result["path"] == "unanswerable" and intent.get("merchant"):
                fallback = _semantic(question, db, embed_fn, llm)
                if fallback["path"] != "unanswerable":
                    return fallback
            return result
        return _semantic(question, db, embed_fn, llm)
    if _classify(question) == "numeric":
        return _numeric(question, db)
    return _semantic(question, db, embed_fn, llm)

"""Conservative notebook display policy, plus heuristic redaction for LOCAL review.

Default previews withhold all free text, person/identifier values and unknown fields.
This module does not approve free text for an external AI service or certify anonymity.
"""
from datetime import date, datetime
import re

EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\w)(?:(?:\+61[ .-]?(?:\(0\)[ .-]?)?|0)[23478](?:[ .()-]*\d){8})(?!\d)")
LABELLED_PLATE = re.compile(r"\b(?:rego|registration|number\s*plate)\s*[:#=-]?\s*[A-Z0-9]{2,4}[ -]?[A-Z0-9]{2,4}\b", re.I)
BARE_PLATE = re.compile(r"\b(?:[A-Z]{3}[ -]?\d{3}|\d{3}[ -]?[A-Z]{3}|[A-Z]{2}[ -]?\d{2}[ -]?[A-Z]{2}|[A-Z]{3}[ -]?\d{2}[ -]?[A-Z])\b")

DATE_HEADERS = {'date', 'date received', 'submitted_at', 'when'}
DEPT_HEADERS = {'department', 'dept', 'area'}
RATING_HEADERS = {'rating', 'rating (1-5)', 'score', 'score (1-5)', 'score (out of 10)', 'csat', 'stars', 'how satisfied?', 'how was it'}
SITE_HEADERS = {'site', 'dealer', 'dealer_code'}
TEXT_HEADERS = {'comments', 'comment', 'customer comments', 'customer said', 'customer feedback', 'feedback', 'verbatim', 'what did they say?', 'notes', 'review', 'action', 'action taken'}
IDENTITY_HEADERS = {'name', 'customer', 'customer name', 'customer no', 'cust no', 'dms_customer_no', 'customer number', 'phone', 'mobile', 'email', 'rego', 'registration', 'reviewer', 'taken by', 'staff', 'card given by', 'logged by', 'ref', 'response_id'}
OTHER_HEADERS = {'vehicle', 'model', 'followed up?', 'follow up (y/n)', 'follow up', 'month', 'grand total', '1', '2', '3', '4', '5', '1.0', '2.0', '3.0', '4.0', '5.0'}
KNOWN_HEADERS = DATE_HEADERS | DEPT_HEADERS | RATING_HEADERS | SITE_HEADERS | TEXT_HEADERS | IDENTITY_HEADERS | OTHER_HEADERS
DEPARTMENTS = {'service', 'service dept', 'svc', 'workshop', 'sales', 'new cars', 'used cars', 'sales - new', 'sales - used', 'parts', 'parts counter', 'parts & accessories', 'p&a', 's', 'sv', 'p'}
SITES = {'rok', 'rocky', 'rockhampton', 'tsv', 'townsville', 'kmg-ips', 'hunter'}
RATING_WORDS = {'good', 'ok', 'bad', 'very satisfied', 'satisfied', 'neutral', 'dissatisfied', 'very dissatisfied'}
SAFE_SCALE_NOTES = {'Rating: 1 = Excellent, 5 = Poor', 'Rating: 1 = Poor ... 5 = Excellent (new head office scale)'}
DATE_STRING = re.compile(r"^(?:\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?|\d{1,2}[- ][A-Za-z]{3}[- ]\d{2,4})$")


def normalized(value):
    return re.sub(r'\s+', ' ', str(value).strip()).casefold()


def redact_text_for_review(value, known_names=()):
    """Heuristic LOCAL review only. Unknown names, addresses and plate formats can remain."""
    text = '' if value is None else str(value)
    for name in sorted({str(v).strip() for v in known_names if str(v).strip()}, key=len, reverse=True):
        text = re.sub(r'(?<!\w)' + re.escape(name) + r'(?!\w)', '[PERSON]', text, flags=re.I)
    text = EMAIL.sub('[EMAIL]', text)
    text = PHONE.sub('[PHONE]', text)
    text = LABELLED_PLATE.sub('[REGISTRATION]', text)
    text = BARE_PLATE.sub('[REGISTRATION]', text)
    return text


def _safe_value(value, header):
    raw = '' if value is None else str(value).strip()
    if not raw:
        return ''
    key = normalized(header)
    if key in IDENTITY_HEADERS:
        return '[IDENTIFIER WITHHELD]'
    if key in TEXT_HEADERS:
        return '[TEXT WITHHELD]'
    if key in DATE_HEADERS:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if DATE_STRING.fullmatch(raw) or (re.fullmatch(r'\d{5}(?:\.0)?', raw) and 20000 <= float(raw) <= 80000):
            return raw
    if key in DEPT_HEADERS and normalized(raw) in DEPARTMENTS:
        return raw
    if key in SITE_HEADERS and (normalized(raw) in SITES or re.fullmatch(r'(?:VIC|NSW|QLD)\d{2}', raw)):
        return raw
    if key in RATING_HEADERS:
        if (re.fullmatch(r'\d{1,2}(?:\.\d+)?', raw) and 0 <= float(raw) <= 10) or normalized(raw) in RATING_WORDS or re.fullmatch('[★☆]{1,5}', raw):
            return raw
    return '[VALUE WITHHELD]'


def safe_preview(grid, header_row=0, rows=5):
    """Show allowlisted structured values only; NEVER display response free text.

    Unknown columns/values, identities, models and notes are withheld. Source data is
    untouched. Header candidates must be reviewed separately before production mapping.
    """
    if not 0 <= header_row < len(grid):
        raise ValueError('A valid, reviewed header row is required for a preview.')
    view = grid.iloc[:rows].copy().astype(object)
    headers = grid.iloc[header_row]
    for i in range(len(view)):
        for j in range(len(view.columns)):
            value, header = grid.iloc[i, j], headers.iloc[j]
            if i < header_row:
                view.iloc[i, j] = str(value) if str(value) in SAFE_SCALE_NOTES else ('[PREAMBLE WITHHELD]' if str(value).strip() else '')
            elif i == header_row:
                view.iloc[i, j] = str(value) if normalized(value) in KNOWN_HEADERS else ('[UNREVIEWED FIELD]' if str(value).strip() else '')
            else:
                view.iloc[i, j] = _safe_value(value, header)
    return view

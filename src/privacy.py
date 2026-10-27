"""In-memory source-name masking. No vocabularies or raw comments are logged/persisted.

Names absent from source columns can remain. Deterministic masking is not a claim
of anonymisation; local residual-name review is required before text release.
"""
from collections import Counter, defaultdict
import re
import sys

from common import ROOT, by_prefix
sys.path.insert(0, str(ROOT / 'scripts'))
from privacy_preview import EMAIL, PHONE, LABELLED_PLATE, BARE_PLATE

CUSTOMER_COLUMNS = {'name', 'customer', 'customer name'}
STAFF_COLUMNS = {'staff', 'taken by', 'logged by', 'card given by'}
# Include enclosing brackets for a readable replacement of '(02) ...'.
PHONE = re.compile(r"(?<!\w)\(?(?:(?:\+61[ .-]?(?:\(0\)[ .-]?)?|0)[23478](?:[ .()-]*\d){8})\)?(?!\d)")
MASK_VERSION = 'source-name-roles-v1'


def norm(value):
    return re.sub(r'\s+', ' ', str(value).strip()).casefold()


def dealer_key(filename, site, cfg):
    if site and not str(site).upper().startswith(('HUNTER', 'KMG')):
        return cfg['site_column_dealers'].get(norm(site), 'source:' + filename)
    return by_prefix(cfg['dealers'], filename) or 'source:' + filename


def name_variants(value):
    text = re.sub(r'\s+', ' ', str(value).strip())
    if norm(text) in {'', 'nan', 'none', 'unknown', 'anonymous', 'n/a'} or not any(c.isalpha() for c in text):
        return set()
    if len(text) < 3 or any(c.isdigit() for c in text) or '@' in text:
        return set()
    variants = {text}
    first = text.split()[0]
    if len(first) >= 3 and first.isalpha():
        variants.add(first)
    return variants


class NameContext:
    def __init__(self):
        self.staff = defaultdict(set)
        self._comment_groups = {}

    def identity(self, original):
        # Only an ordinal is stored. Equality is evaluated before masking so separate
        # comments do not become duplicates merely because names were replaced.
        if original not in self._comment_groups:
            self._comment_groups[original] = len(self._comment_groups) + 1
        return self._comment_groups[original]

    def mask(self, text, dealer, customers=()):
        text = str(text or '')
        counts = Counter()
        for pattern, tag, kind in [(EMAIL, '[EMAIL]', 'email'), (PHONE, '[PHONE]', 'phone'),
                                   (LABELLED_PLATE, '[REGO]', 'rego'), (BARE_PLATE, '[REGO]', 'rego')]:
            text, n = pattern.subn(tag, text)
            counts[kind] += n
        roles = defaultdict(set)
        for token in self.staff[dealer]:
            roles[norm(token)].add('STAFF')
        for value in customers:
            for token in name_variants(value):
                roles[norm(token)].add('CUSTOMER')
        if roles:
            choices = sorted(roles, key=len, reverse=True)
            pattern = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(t).replace(r'\ ', r'\s+') for t in choices) + r')(?!\w)', re.I)
            def replace(match):
                found = roles[norm(match.group())]
                role = next(iter(found)) if len(found) == 1 else 'PERSON'
                counts[role.lower()] += 1
                return '[' + role + ']'
            # Do not reprocess tags, including tags present in the original comment.
            pieces = re.split(r'(\[[A-Z_]+\])', text)
            text = ''.join(part if re.fullmatch(r'\[[A-Z_]+\]', part) else pattern.sub(replace, part) for part in pieces)
        metadata = {f'masked_{kind}_count': counts[kind] for kind in ('customer', 'staff', 'person', 'email', 'phone', 'rego')}
        metadata['masking_version'] = MASK_VERSION
        metadata['has_unmasked_name'] = None  # unknown until a separate local model audit
        metadata['name_audit_status'] = 'not_run'
        metadata['had_staff_name_mention'] = bool(counts['staff'])
        metadata['had_customer_name_mention'] = bool(counts['customer'])
        return text, metadata


def build_name_context(sources, cfg, find_headers):
    context = NameContext()
    for filename, sheet, grid, digest in sources:
        starts = find_headers(grid, cfg)
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(grid)
            labels = [norm(v) for v in grid.iloc[start]]
            staff_columns = [i for i, label in enumerate(labels) if label in STAFF_COLUMNS]
            site_columns = [i for i, label in enumerate(labels) if label in cfg['columns']['site']]
            for i in range(start + 1, end):
                site = str(grid.iloc[i, site_columns[0]]).strip() if site_columns else ''
                dealer = dealer_key(filename, site, cfg)
                for j in staff_columns:
                    context.staff[dealer].update(name_variants(grid.iloc[i, j]))
    return context

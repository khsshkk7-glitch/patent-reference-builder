"""Conservative patent identifier parsing; never infer an A/B kind code."""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class Patent:
    country: str
    number: str
    kind: str = ""
    role: str = "publication"

    @property
    def key(self):
        return self.country + self.number + self.kind

    @property
    def query(self):
        return ("ap=" if self.role == "application" else "pn=") + self.key

    @property
    def filename(self):
        n = self.number
        if self.country == "KR" and len(n) == 11:
            n = "10-" + n[:4] + "-" + n[4:]
        elif self.country == "KR" and len(n) == 9:
            n = n[:2] + "-" + n[2:]
        elif self.country in ("JP", "US", "WO") and n[:2] in ("19", "20") and len(n) >= 10:
            n = n[:4] + "-" + n[4:]
        # KR sample omits A; never omit a B kind because it could collide.
        suffix = " " + self.kind if self.kind and not (self.country == "KR" and self.kind == "A") else ""
        return f"{self.country} {n}{suffix}.pdf"


COUNTRIES = 'KR JP US EP WO CN DE GB FR CA AU TW AT BE BR CH CZ DK ES FI GR HK HU IE IL IN IT MX NL NO NZ PL PT RU SE SG SK TR UA ZA EA AP AR BG CL CO ID MY PH TH VN'.split()
COUNTRY_PATTERN = '|'.join(COUNTRIES)
PATTERN = re.compile(
    rf"(?<![A-Z0-9])(?P<cc>{COUNTRY_PATTERN})\s*"
    r"(?P<num>\d(?:[\d /-]*\d)?)(?:\s*\(?\s*(?P<kind>[ABC UYSH][0-9]?)\s*\)?)?(?![A-Z0-9])".replace("[ABC UYSH]", "[ABCUYSH]"),
    re.I,
)


def clean(text):
    text = unicodedata.normalize("NFKC", str(text)).upper()
    text = re.sub(r"[‐‑‒–—−]", "-", text)
    # Gregorian Japanese publication notation; era years require explicit conversion.
    text = re.sub(r"特開\s*((?:19|20)\d{2})[-\s]*(\d{1,6})", lambda m: f"JP {m[1]}-{int(m[2]):06d} A", text)
    return text


def extract(text, role="publication", country=None):
    value = clean(text)
    if country and country.upper() not in COUNTRIES:
        raise ValueError('지원하지 않는 국가/기관 코드: ' + country)
    if country and not re.search(rf"\b(?:{COUNTRY_PATTERN})\s*\d", value):
        value = country.upper() + " " + value
    found = []
    for m in PATTERN.finditer(value):
        cc, raw, kind = m["cc"].upper(), m["num"], (m["kind"] or "").upper()
        n = re.sub(r"\D", "", raw)
        if cc == "KR":
            if len(n) == 13 and n.startswith("10"):
                n = n[2:]
            if len(n) not in (9, 11):
                continue
        elif cc == "JP":
            year = re.fullmatch(r"((?:19|20)\d{2})[- /]+(\d{1,6})", raw.strip())
            if year:
                n = year[1] + year[2].zfill(6)
            if len(n) not in (6, 7, 8, 9, 10):
                continue
        elif not 6 <= len(n) <= 13:
            continue
        p = Patent(cc, n, kind, role)
        if p not in found:
            found.append(p)
    return found


def one(text, **kwargs):
    matches = extract(text, **kwargs)
    if len(matches) != 1:
        raise ValueError("특허번호가 없거나 여러 개입니다. 국가코드와 번호를 확인하세요: " + str(text))
    return matches[0]


def resolve(requested, candidates):
    """Candidates must come from the selected publication field, NOT family/citation text."""
    exact = [p for p in candidates if p.country == requested.country and p.number == requested.number
             and (not requested.kind or p.kind == requested.kind) and p.kind]
    exact = list(dict.fromkeys(exact))
    if requested.role == "application":
        raise ValueError("출원번호는 공보번호로 먼저 매핑해야 합니다. 후보 공보를 확인하세요.")
    if len(exact) != 1:
        raise ValueError("문헌 종별을 단일하게 확인할 수 없습니다: " + ", ".join(p.key for p in exact))
    return exact[0]

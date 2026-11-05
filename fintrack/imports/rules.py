"""
imports/rules.py - Feste Zuordnungen für den Kontoimport, ohne KI.

Zwei Quellen:
- Regeln des Nutzers (CategoryRule): "steht 'vodafone' im Empfänger -> Handy/Internet",
  angelegt in den Einstellungen oder als Startwissen aus einer früheren Umsatzliste
- Bekannte Händler (MERCHANTS): Tankstellen, Supermärkte, Drogerien usw. Sie zeigen auf
  Kategorien über deren Namen und gelten nur, wenn der Nutzer eine so benannte Kategorie hat

Ein Muster passt nur als ganzes Wort (bzw. Wortfolge), damit "jet" nicht in "budget" und
"dm" nicht in "admiral" trifft. Erst wird der Empfänger geprüft, dann der Verwendungszweck;
bei mehreren Treffern gewinnt das längste Muster (genauer ist besser).
"""

import re

from fintrack.models import Category, CategoryRule

# Bekannte Händler je Kategorie (Hauptkategorie, Unterkategorie) - nur für Ausgaben
MERCHANTS = {
    ('Mobilität', 'Sprit'): ['aral', 'shell', 'esso', 'jet tankstelle', 'agip', 'avia', 'star tankstelle',
                             'totalenergies', 'tankstelle', 'orlen', 'hem tankstelle'],
    ('Mobilität', 'Taxi/Fahrdienst'): ['uber', 'free now', 'freenow', 'bolt.eu', 'taxi'],
    ('Lebenshaltung', 'Lebensmittel'): ['rewe', 'aldi', 'lidl', 'edeka', 'netto', 'penny', 'kaufland', 'tegut',
                                        'globus', 'nahkauf', 'alnatura', 'denns', 'norma', 'hit markt', 'marktkauf',
                                        'bäckerei', 'baeckerei', 'metzgerei'],
    ('Lebenshaltung', 'Drogerie'): ['dm-drogerie', 'dm drogerie', 'rossmann', 'budnikowsky', 'müller drogerie'],
    ('Lebenshaltung', 'Kleidung'): ['h+m', 'h&m', 'zalando', 'zara', 'primark', 'c&a', 'about you', 'deichmann',
                                    'snipes', 'tk maxx', 'peek & cloppenburg', 'shein'],
    ('Sonstige Verträge', 'Streaming/Abos'): ['netflix', 'spotify', 'disney plus', 'disney+', 'dazn', 'audible',
                                              'youtube premium', 'paramount', 'wow tv', 'rtl+'],
    ('Sonstige Verträge', 'Handy/Internet'): ['vodafone', 'telekom deutschland', 'telefonica', 'o2 germany',
                                              '1&1', 'congstar', 'freenet', 'aldi talk'],
    ('Entertainment & Interessen', 'Kino'): ['cinestar', 'cinemaxx', 'uci kinowelt', 'kinopolis'],
}


def _compile(pattern):
    return re.compile(r'(?<![\wäöüß])' + re.escape(pattern.lower()) + r'(?![\wäöüß])')


def _category_by_name(categories):
    """(Hauptkategorie, Unterkategorie) in Kleinbuchstaben -> Kategorie, nur Ausgaben."""
    by_id = {c.id: c for c in categories}
    found = {}
    for category in categories:
        if category.parent_id and category.type != 'income':
            main = by_id.get(category.parent_id)
            if main:
                found[(main.name.strip().lower(), category.name.strip().lower())] = category.id
    return found


class RuleBook:
    """Alle Regeln eines Nutzers, einmal vorbereitet für viele Umsätze."""

    def __init__(self, user_id):
        categories = Category.query.filter_by(user_id=user_id).all()
        own = [(_compile(r.pattern), len(r.pattern), r.income, r.category_id)
               for r in CategoryRule.query.filter_by(user_id=user_id).all()]
        names = _category_by_name(categories)
        builtin = []
        for (main, sub), patterns in MERCHANTS.items():
            category_id = names.get((main.lower(), sub.lower()))
            if category_id:
                builtin += [(_compile(p), len(p), False, category_id) for p in patterns]
        # Längstes Muster zuerst
        self.own = sorted(own, key=lambda r: -r[1])
        self.builtin = sorted(builtin, key=lambda r: -r[1])

    @staticmethod
    def _match(rules, income, counterparty, purpose):
        for text in (counterparty, purpose):
            text = (text or '').lower()
            if not text:
                continue
            for regex, _, rule_income, category_id in rules:
                if rule_income == income and regex.search(text):
                    return category_id
        return None

    def own_rule(self, income, counterparty, purpose):
        return self._match(self.own, income, counterparty, purpose)

    def merchant(self, income, counterparty, purpose):
        return self._match(self.builtin, income, counterparty, purpose)

"""
test_contract_terms.py - Unit Tests für die Laufzeit- und Fristberechnung
aus contracts/terms.py. Jeder Fall entspricht einer typischen Vertragsart.
"""

import sys
import os
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.contracts.terms import add_months, contract_status, notice_deadline, term_end, yearly_cost


def contract(start, min_term=None, renewal=12, notice=3, unit='months', end_date=None,
             amount=10.0, interval='monthly'):
    return SimpleNamespace(start_date=start, min_term_months=min_term, renewal_months=renewal,
                           notice_value=notice, notice_unit=unit, end_date=end_date,
                           amount=amount, interval=interval)


class TestDateHelpers:

    @pytest.mark.parametrize('day,months,expected', [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2026, 11, 15), 3, date(2027, 2, 15)),
        (date(2026, 3, 31), -1, date(2026, 2, 28)),
        (date(2026, 1, 10), -1, date(2025, 12, 10)),
    ])
    def test_add_months_clamps_to_month_end(self, day, months, expected):
        assert add_months(day, months) == expected

    def test_term_end_is_the_last_day(self):
        """Ab 01.01. mit 12 Monaten läuft der Vertrag bis 31.12."""
        assert term_end(date(2026, 1, 1), 12) == date(2026, 12, 31)
        assert term_end(date(2026, 3, 15), 24) == date(2028, 3, 14)

    @pytest.mark.parametrize('end,value,unit,expected', [
        (date(2026, 12, 31), 3, 'months', date(2026, 9, 30)),
        (date(2026, 4, 30), 1, 'months', date(2026, 3, 31)),
        (date(2026, 12, 31), 1, 'months', date(2026, 11, 30)),
        (date(2026, 12, 31), 2, 'weeks', date(2026, 12, 17)),
        (date(2026, 12, 31), 30, 'days', date(2026, 12, 1)),
        (date(2026, 12, 31), 0, 'days', date(2026, 12, 31)),
    ])
    def test_notice_deadline(self, end, value, unit, expected):
        assert notice_deadline(end, value, unit) == expected


class TestContractStatus:

    def test_insurance_yearly_with_three_months_notice(self):
        """Typische Versicherung: Kalenderjahr, 3 Monate Frist zum 31.12."""
        result = contract_status(contract(date(2024, 1, 1)), today=date(2026, 8, 1))

        assert result['status'] == 'active'
        assert result['next_term_end'] == date(2026, 12, 31)
        assert result['cancel_by'] == date(2026, 9, 30)
        assert result['cancel_effective'] == date(2026, 12, 31)

    def test_missed_deadline_moves_to_next_term(self):
        """Frist für dieses Jahr verpasst: nächstmöglich ist das Ende des Folgejahrs"""
        result = contract_status(contract(date(2024, 1, 1)), today=date(2026, 10, 1))

        assert result['next_term_end'] == date(2026, 12, 31)
        assert result['cancel_by'] == date(2027, 9, 30)
        assert result['cancel_effective'] == date(2027, 12, 31)

    def test_deadline_day_itself_still_counts(self):
        result = contract_status(contract(date(2024, 1, 1)), today=date(2026, 9, 30))

        assert result['cancel_by'] == date(2026, 9, 30)

    def test_minimum_term_then_monthly(self):
        """Handyvertrag: 24 Monate Mindestlaufzeit, danach monatlich mit 1 Monat Frist"""
        phone = contract(date(2025, 3, 15), min_term=24, renewal=1, notice=1)

        during = contract_status(phone, today=date(2026, 6, 1))
        assert during['cancel_by'] == date(2027, 2, 14)
        assert during['cancel_effective'] == date(2027, 3, 14)

        after = contract_status(phone, today=date(2027, 5, 20))
        assert after['next_term_end'] == date(2027, 6, 14)
        assert after['cancel_by'] == date(2027, 6, 14)
        assert after['cancel_effective'] == date(2027, 7, 14)

    def test_start_on_31st_does_not_drift(self):
        """Laufzeitenden werden immer vom Startdatum gerechnet"""
        gym = contract(date(2026, 1, 31), renewal=1, notice=0, unit='days')

        assert contract_status(gym, today=date(2026, 4, 1))['next_term_end'] == date(2026, 4, 30)

    def test_contract_starting_in_future(self):
        result = contract_status(contract(date(2027, 1, 1)), today=date(2026, 11, 1))

        assert result['cancel_by'] == date(2027, 9, 30)
        assert result['cancel_effective'] == date(2027, 12, 31)

    def test_fixed_term_without_renewal_ends_by_itself(self):
        loan = contract(date(2024, 5, 1), min_term=36, renewal=None)

        running = contract_status(loan, today=date(2026, 11, 1))
        assert running['status'] == 'ending'
        assert running['ends_on'] == date(2027, 4, 30)
        assert running['cancel_by'] is None

        assert contract_status(loan, today=date(2027, 5, 1))['status'] == 'ended'

    def test_cancelled_contract_has_no_deadline(self):
        cancelled = contract(date(2024, 1, 1), end_date=date(2026, 12, 31))

        result = contract_status(cancelled, today=date(2026, 11, 1))
        assert result['status'] == 'cancelled'
        assert result['ends_on'] == date(2026, 12, 31)
        assert result['cancel_by'] is None

        assert contract_status(cancelled, today=date(2027, 1, 1))['status'] == 'ended'


class TestYearlyCost:

    @pytest.mark.parametrize('interval,expected', [
        ('monthly', 120.0), ('quarterly', 40.0), ('half_yearly', 20.0), ('yearly', 10.0),
    ])
    def test_yearly_cost(self, interval, expected):
        assert yearly_cost(contract(date(2026, 1, 1), interval=interval)) == expected

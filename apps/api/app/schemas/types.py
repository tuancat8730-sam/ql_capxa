"""Shared field types. Money/percent are Decimal in memory but plain JSON numbers on the wire."""

from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer


def _to_number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


Number = Annotated[Decimal, PlainSerializer(_to_number, return_type=int | float, when_used="json")]
Money = Annotated[Number, Field(ge=0, max_digits=18, decimal_places=0)]
Percent = Annotated[Number, Field(ge=0, le=100, max_digits=5, decimal_places=2)]

"""
Pydantic schemas for transaction API contracts.

This module defines the data transfer objects (DTOs) for transaction operations:
- TransactionType: Enum for transaction types (BUY/SELL)
- TransactionDTO: Buy/sell order representation

All schemas include comprehensive validation for financial data and secure
handling of transaction information.
"""

import re
from datetime import date
from enum import Enum
from typing import Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionType(str, Enum):
    """
    Transaction type enumeration.

    Defines the types of transactions that can be created:
    - BUY: Purchase of securities
    - SELL: Sale of securities
    """

    BUY = "BUY"
    SELL = "SELL"

    @classmethod
    def _missing_(cls, value):
        """Handle case-insensitive enum lookup."""
        if isinstance(value, str):
            for item in cls:
                if item.value.lower() == value.lower():
                    return item
        return super()._missing_(value)


class TransactionDTO(BaseModel):
    """
    Buy/sell order representation.

    Represents a transaction to buy or sell a specific quantity of a security
    on a given trade date.
    """

    model_config = ConfigDict(
        use_enum_values=True, json_encoders={date: lambda dt: dt.isoformat()}
    )

    transaction_type: TransactionType = Field(
        ..., description="Type of transaction (BUY or SELL)"
    )

    security_id: str = Field(
        ...,
        description="24-character alphanumeric security identifier",
        min_length=24,
        max_length=24,
    )

    quantity: int = Field(..., description="Number of shares/units to trade", gt=0)

    trade_date: date = Field(
        ..., description="Date when the transaction should be executed"
    )

    @field_validator('security_id')
    @classmethod
    def validate_security_id(cls, v: str) -> str:
        """Validate security ID format: exactly 24 alphanumeric characters."""
        if not re.match(r'^[A-Za-z0-9]{24}$', v):
            raise ValueError("Security ID must be exactly 24 alphanumeric characters")
        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity_positive(cls, v: int) -> int:
        """Validate quantity is positive."""
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @field_validator('transaction_type', mode='before')
    @classmethod
    def parse_transaction_type(cls, v: Union[str, TransactionType]) -> TransactionType:
        """Parse transaction type, handling case-insensitive strings."""
        if isinstance(v, str):
            try:
                return TransactionType(v.upper())
            except ValueError:
                # Try case-insensitive lookup
                for transaction_type in TransactionType:
                    if transaction_type.value.lower() == v.lower():
                        return transaction_type
                raise ValueError(f"Invalid transaction type: {v}")
        return v

from datetime import date

from pydantic import ValidationError

from src.schemas.transactions import TransactionDTO, TransactionType

# Test with exactly 24 characters but with special characters
test_id = "STOCK123456789012345678_!"  # This should be 24 chars
print(f"Test ID length: {len(test_id)}")

try:
    dto = TransactionDTO(
        transaction_type=TransactionType.BUY,
        security_id=test_id,
        quantity=100,
        trade_date=date(2024, 12, 19),
    )
    print("No error raised")
except ValidationError as e:
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")
    print(f"Error details: {e.errors()}")
except Exception as e:
    print(f"Other error type: {type(e).__name__}")
    print(f"Other error message: {str(e)}")

# DELETE Model API Documentation

## Overview
The DELETE `/api/v1/model/{model_id}` endpoint allows for the deletion of an investment model with optimistic concurrency control to prevent concurrent modification conflicts.

## Endpoint Details

**URL:** `DELETE /api/v1/model/{model_id}`

**Parameters:**
- `model_id` (path parameter): 24-character hexadecimal model identifier
- `version` (query parameter): Expected model version for optimistic locking

**Response:**
- **Success:** HTTP 204 No Content (empty response body)
- **Content-Type:** N/A (no response body)

## Request Example

```http
DELETE /api/v1/model/507f1f77bcf86cd799439011?version=3
```

## Response Examples

### Success Response
```http
HTTP/1.1 204 No Content
```

### Error Responses

#### Model Not Found
```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "detail": "Model 507f1f77bcf86cd799439011 not found"
}
```

#### Version Conflict (Optimistic Locking)
```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{
  "detail": "Model has been modified by another process"
}
```

#### Business Rule Violation
```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{
  "detail": "Cannot delete model with associated portfolios. Remove all portfolios first."
}
```

#### Invalid Model ID Format
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "detail": "Invalid model ID format. Must be 24-character hexadecimal string."
}
```

#### Internal Server Error
```http
HTTP/1.1 500 Internal Server Error
Content-Type: application/json

{
  "detail": "Internal server error"
}
```

## Business Rules

1. **Optimistic Concurrency Control**: The `version` parameter must match the current model version to prevent concurrent modifications.

2. **Portfolio Association Check**: Models with associated portfolios cannot be deleted. All portfolios must be removed from the model before deletion.

3. **Model ID Validation**: The model ID must be a valid 24-character hexadecimal string (MongoDB ObjectId format).

## Error Handling

The endpoint follows the project's standard error handling patterns:

- **400 Bad Request**: Invalid input parameters (malformed model ID, missing version)
- **404 Not Found**: Model does not exist
- **409 Conflict**: Version mismatch (optimistic locking conflict)
- **422 Unprocessable Entity**: Business rule violations (e.g., model has associated portfolios)
- **500 Internal Server Error**: Unexpected server errors

## Usage Notes

1. **Version Requirement**: The version parameter is mandatory and must be obtained from a previous GET request to ensure you're deleting the expected version of the model.

2. **Cascading Considerations**: Before deleting a model, ensure all associated portfolios are removed using the `DELETE /api/v1/model/{model_id}/portfolio` endpoint.

3. **Idempotency**: The operation is idempotent - attempting to delete a non-existent model returns 404, not an error.

4. **Logging**: All deletion attempts are logged with appropriate context for audit and debugging purposes.

## Integration Example

```python
import httpx

async def delete_model(client: httpx.AsyncClient, model_id: str, version: int):
    """Delete a model with proper error handling."""
    try:
        response = await client.delete(
            f"/api/v1/model/{model_id}",
            params={"version": version}
        )
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"Model {model_id} not found")
        elif e.response.status_code == 409:
            print(f"Model {model_id} was modified by another process")
        elif e.response.status_code == 422:
            print(f"Cannot delete model: {e.response.json()['detail']}")
        else:
            print(f"Deletion failed: {e.response.json()['detail']}")
        return False
```

## Security Considerations

- The endpoint validates model ID format to prevent injection attacks
- Optimistic locking prevents race conditions in concurrent environments
- Business rule validation ensures data integrity
- All operations are logged for audit trails

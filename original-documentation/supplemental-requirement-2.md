# Supplemental Requirement 2

Modify the GET model API to support paging.  Add to optional query parameters: offset and limit.  If neither parameter is specified, return all models.  If limit is specified without an offset, assume the offset is 0.  If offset is specified without a limit, return the models from the offset to the end.  If the offset is greater than the number of rows, or if the offset and limit are not non-negative integers, return an appropriate status code and message.

Implement an optional sort_by query parameter which is a comma separated list that may include any of model_id, name, or last_rebalance_date.  Pagination should honor the sorting.  The default is no sorting.


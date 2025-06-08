# Supplemental Requirement 3

This is an enhancement to [Supplemental Requirement 2](supplemental-requirement-2.md).

- In the sort_by query parameter, a field name may be prefixed with a + or a -, for an ascending or descending sort respectively
- If there is no + or - prefix, the default sorting is ascending
- The valid sort values are model_id, +model_id, -model_id, name, +name, -name, last_rebalance_date, +last_rebalance_date, and -last_rebalance_date
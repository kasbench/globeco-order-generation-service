# Supplemental Requirement 4

This is the current RebalanceDTO returned by the rebalancer as described in the "## Rebalancer Requirements" section of [business-requirements.md](business-requirements.md)

- RebalanceDTO: PortfolioId, [TransactionDTO], [DriftDTO]

- TransactionDTO
    | Field Name | Data Type | Description |
    | --- | --- | --- |
    | transactionType| String | 'BUY' or 'SELL'
    | securityId | String | 24 character string
    | quantity | Integer | Positive quantity to BUY or SELL
    | tradeDate | Date | Current date (no time)

- DriftDTO
    | Field Name | Data Type | Description |
    | --- | --- | --- |
    | securityId| String |
    | originalQuantity | Decimal128 | Original value of $u$ |
    | adjustedQuantity | Decimal128 | New value of $u^{'}$
    | target | Decimal128 | Target from the model
    | highDrift | Decimal128 | High drift from the model
    | lowDrift | Decimal128 | Low drift from the model
    | actual | Decimal128 | $(u^{'} \cdot p)/MV$



We are going to make three changes
1. Persist the results of the rebalance back to the MongoDB database.  Instead of just returning the RebalanceDTO, also persist the results back to the databse.
2. Modify the RebalanceDTO to return the database ID for the reblance
3. Implement new APIs to retrieve the rebalancer results stored in the database


## Persist the results of the rebalance back to the MongoDB database

**Collection:** rebalances

### **Rebalance Schema**

| Database Field | API Field | Data Type | Description|
| --- | --- | --- | --- |
|  | rebalanceId | ObjectId | Unique MongoDB assigned primary key |
| modelId | modelId | ObjectId | Required ID of the model that was rebalanced |
| rebalanceDate | rebalanceDate | Date | Date of the rebalance (current date)
| modelName | modelName | String| Name of the model that was rebalanced
| numberOfPortfolios | numberOfPortfolios | Integer| Number of portfolios in the rebalance
| portfolios | portfolios | [Portfolio] | List of portfolios rebalanced.  See below for the Portfolio Schema
| version | version | Int32 | default 1. For optimistic concurrency |
---


### **Portfolio Schema**
| Database Field | API Field | Data Type | Description|
| --- | --- | --- | --- |
| portfolioId | portfolioId | String | Required ID of the portfolio that was rebalanced
| portfolioName | portfolioName | String | Name of the portfolio that was rebalanced
| marketValue | marketValue | Decimal128 | Market Value of the Portfolio |
| positions | positions | [Position] | List of positions in the portfolio.  Positions includes the union of the positions in the portfolio prior to the rebalance and the positions in the portfolio after the rebalance.  See the Position Schema below |
---

### **Position Schema**

| Database Field | API Field | Data Type | Description|
| --- | --- | --- | --- |
| securityId | securityId | String | Required ID of the security that was rebalanced.  A security can appear at most once in the positions list for a portfolio.
| price | price | Decimal128 | Price used for the rebalance |
| originalQuantity | originalQuantity | Decimal128 | Original value of $u$ |
| adjustedQuantity | adjustedQuantity| Decimal128 | New value of $u^{'}$
| originalPositionMarketValue | originalPositionMarketValue | Decimal128 | original quantity times price
| adjustedPositionMarketValue | adjustedPositionMarketValue | Decimal128 | adjusted quantity times price
| target | target | Decimal128 | Target from the model
| highDrift | highDrift | Decimal128 | High drift from the model
| lowDrift | lowDrift | Decimal128 | Low drift from the model
| actual | actual | Decimal128 | $(u^{'} \cdot p)/MV$
| actualDrift | actualDrift | Decimal128 | 1 - (actual/target)
| transactionType| transactionType | String | 'BUY' or 'SELL'
| tradeQuantity | tradeQuantity | Integer | Positive quantity to BUY or SELL
| tradeDate | tradeDate | Date | Current date (no time)
---

See [business-requirements.md](business-requirements.md) for instructions on how to value each field.  Most of the fields are the same as the RebalanceDTO, just structured differently.


## Modify the RebalanceDTO

There is only two changes to RebalanceDTO: 
- We are returning the portfolio name (portfolioName)
- We are returning the id of the rebalance record in the rebalances collection (rebalanceId)

- RebalanceDTO: PortfolioId, **portfolioName**, **rebalanceId**, [TransactionDTO], [DriftDTO]

- TransactionDTO **Unchanged**
    | Field Name | Data Type | Description |
    | --- | --- | --- |
    | transactionType| String | 'BUY' or 'SELL'
    | securityId | String | 24 character string
    | quantity | Integer | Positive quantity to BUY or SELL
    | tradeDate | Date | Current date (no time)

- DriftDTO **Unchanged**
    | Field Name | Data Type | Description |
    | --- | --- | --- |
    | securityId| String |
    | originalQuantity | Decimal128 | Original value of $u$ |
    | adjustedQuantity | Decimal128 | New value of $u^{'}$
    | target | Decimal128 | Target from the model
    | highDrift | Decimal128 | High drift from the model
    | lowDrift | Decimal128 | Low drift from the model
    | actual | Decimal128 | $(u^{'} \cdot p)/MV$

## New APIs

| Verb | URI | Request DTO | Response DTO | Explanation |
| --- | --- | --- | --- | --- |
| GET | rebalances | - | List of Rebalance Schema as a DTO | Get all rebalances.  Implement paging with query parameters offset and limit.
| GET | rebalance/{id}  | - | Rebalance Schema as DTO |  Get a specific rebalance
| POST | rebalances/portfolios | {"portfolios":[]} | List of Rebalance Schema as a DTO | Pass a list of portfolios in the Request DTO, as shown, and receive the rebalances for the portfolios.  Implement paging with query parameters offset and limit |
| DELETE | rebalance/{id} | Delete the specified rebalance record.  Field version passed as a query parameter.
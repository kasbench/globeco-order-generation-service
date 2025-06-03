# The GlobeCo Order Generation Service

## Overview

- The order generation service is used to create orders to buy and sell securities for multiple portfolios at a time.
- It exposes a REST API
- The API will be called by the web portals.
- The Order Generation Service depends on the following other services
    - The **Portfolio Accounting Service** (globeco-portfolio-accounting-service) for account balances
    - The **Portfolio Service** (globeco-portfolio-service) for portfolios
    - The **Real-Time Pricing Service** (globeco-pricing-service) for prices
    - The **Security Service** (globeco-security-service) for security types and descriptions
    - The **Porfolio Optimization Service** (globeco-portfolio-optimization-service) for  
    - The **Order Service** (globeco-order-service) to send generated orders


- This service has the following primary functions
    - Maintain investment models.  An investment model defines a list of securities with a target percentage and allowable drift.  A model represents an ideal portfolio.  Models are used to analyze and rebalance portfolios.
    - Maintain the relationship between investment models and portfolios.  Portfolios are stored in the Portfolio Service.
    - Perform the following bulk ordering functions.  Following each operation, send the results to the Order Service.
        - Send a specified portfolio to the portfolio optimization service for optimization. This will be done in a second phase after the Portfolio Optimization Service is developed.
        - Send all portfolios belonging to a particular model to the portfolio optimization service for optimization.  This will be done in a second phase after the Portfolio Optimization Service is developed.
        - Rebalance a specified portfolio. See [Rebalancer Requirements](#rebalancer-requirements).
        - Rebalance all portfolios for a specified model. See [Rebalancer Requirements](#rebalancer-requirements).
        - Buy or sell a "slice" of a particular security to to model target for a given model.  See [Slice Requirements](#slice-requirements).  Slice will be in phase 2.
        - Increase or decrease the weighting of a particular security to a given percentage for a given model.  Do not change the model. See [Slice Requirements](#slice-requirements).  Slice will be in phase 2.
    


## Model Requirements

### Data Model

Collection: models


#### **Model**
| Database Field | API Field | Data Type | Description|
| --- | --- | --- | --- |
| _id | modelId | ObjectId | Unique MongoDB assigned primary key |
| name | name | String | Required model name |
| positions | positions | [Position] | Required list of positions.  See below for Position schema |
| portfolios | portfolios | [String] | List of positions subscribed to this model.  Portfolio IDs are 24 character strings.
| lastRebalanceDate | lastRebalanceDate | Date | Date and time of the last rebalance |
| version | version | Int32 | default 1. For optimistic concurrency |
---

#### **Position**

| Database Field | API Field | Data Type | Description|
| --- | --- | --- | --- |
| securityId | securityId | String | Required 24 character Security ID.
| target | target | Decimal128 | Target position as a decimal percentage of the portfolio.  The value must be between 0 and 0.95 |
| highDrift | highDrift | Decimal128 | Allowable drift above target as a percentage of market value.  Value must be between 0 and 1.
| lowDrift | lowDrift | Decimal128 | Allowable drift below target as a percentage of market value.  Value must be between 0 and 1.

#### Validations:
- Position targets must be 0 or a multiple of 0.005.
- Models may have no more than 100 positions with targets greater than 0.
- A security must be unique in the positions for a model.  If a list of positions contains two positions for the same security, throw an error.
- Positions with targets of 0 should be automatically deleted upon saving to the database.
- Within any given model, the sum of the targets of all its positions must not exceed 0.95.  This enforces a requirement that all models must leave at least 5% (0.05) in cash.  The percentage that is not allocated to securities will be held in cash.
- The versions field is used to enforce optimistic concurrency.




### DTOs

- ModelDTO: _id, name, positions, portfolios, lastRebalanceDate, version

- ModelPUTDTO: name, positions, portfolios, lastRebalanceDate, version

- ModelPostDTO: name, positions, portfolios

- ModelPositionDTO: security_id, target, highDrift, lowDrift

- ModelPortfolioDTO: [portfolioId]

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


### APIs

Prefix: api/v1/


| Verb | URI | Request DTO | Response DTO | Explanation |
| --- | --- | --- | --- | --- |
| GET | models | - | ModelDTO | Get all models
| GET | model/{modelId} | - | ModelDTO | Get model by ID
| POST | models | ModelPostDTO | ModelDTO | Post a new model
| PUT | model/{modelId} | ModelPutDTO | ModelDTO | Update a model
| POST | model/{modelId}/position/ | ModelPostDTO | ModelDTO | Adds a position in a model.  There must not be another position in the model with the same security.  The total of all targets in the model may not exceed 0.95.
| PUT | model/{modelId}/position | ModelPositionDTO | ModelDTO | Updates a model position.  The security must already exist in the model.  The target, highDrift, and lowDrift are updated to the value in the DTO.  The total of all targets in the model may not exceed 0.95
| DELETE | model/{modelId}/position | ModelPositionDTO | ModelDTO | The position in the payload is deleted as long as the values in the database exactly match the values in the DTO.
| POST | model/{modelId}/portfolio | ModelPortfolioDTO | ModelDTO | The portfolios in the payload are appending to the list of portfolios in the database for the model.  Duplicates are silently ignored.
| DELETE | model/{modelId}/portfolio | ModelPortfolioDTO | ModelDTO | The portfolios in the payload are deleted from the portfolios in the database for the model.  Missing portfolios are silently ignored.
| POST | model/{modelId}/rebalance | - | [RebalanceDTO] | Triggers a rebalance for all portfolios in the specified model |
| POST | portfolio/{portfolioID}/rebalance | - | RebalanceDTO | Triggers a rebalance for the specified portfolioId |



## Rebalancer Requirements

Rebalancing the portfolio is a non-linear optimization problem.  Let $N$ be the number of security positions in a model, let $s_i$ be the security and $u_i$ be the the number of units of security position $i$, for all $i \in \{1, 2, \cdots, N\}$.  Let $p_i$ be the price of each unit of position $i$.  And let $w_i$, $l_i$, and $h_i$, be the target weight, low drift, and high drift, respectively.

The market value, $MV$ of the portfolio is expressed as.

$$
\begin{equation}
MV = Cash +\sum_{i=1}^N u_i \cdot p_i
\end{equation}
$$

Portfolio drift, $PD$ is defined as

$$
\begin{equation}
PD = \sum_{i=1}^N |(MV \cdot t_i) - (u_i \cdot p_i)|
\end{equation}
$$

The objective of the optimization problem is to find the values of $u_1, u_2, \cdots, u_n$ that  minimize PD subject to the following constraints:

- MV is a constant.  It cannot change.
- $p_1, p_2, \cdots , p_n$ are constants.  They cannot change.
- $\forall i, u_i \in \mathbb{Z}$ (All values of u are integers)
- $\forall i, u_i \ge 0$ (All values of u are non-negative)
- $\forall i, u_i \cdot p_i \ge MV \cdot (w_i - l_i)$
- $\forall i, u_i \cdot p_i \le MV \cdot (w_i + h_i)$

### Processing Steps
For each portfolio to be rebalanced:

1. Call the /balance endpoint of the Portfolio Accounting Service to get the current positions in the portfolio.  These are the current values of $u$ for each security in the portfolio.
2. Get the target, lower drift, and upper drift for each position in the model.  These are the values of $t$, $l$, and $h$, respectively.
3. Create a combined list of positions from step 1 and 2.  For any security in step 1 that is not also in step 2, the values of $t$, $l$, and $h$ are 0.  These values of $t$, $l$, and $h$ are constants.
4. Call the pricing service to get the price for all securities in the combined list from step 3.  These are your values of $p$.  These values of $p$ are a constant.
5. Calculate MV according to equation 2.  This value is a constant.  Cash is the obtained from the position record without a securityId (null securityId).  Assume that the price is 1, so total cash is the value of the quantity returned.
6. Solve the non-linear optimization problem by minimizing equation 2.  If there are multiple solutions, pick one at random.  
7. The solution in step 6 will provide new values of $u$.  Let's call these new values $u_i^{'}$ and the original values $u_i$.  Calculate $\Delta_i = u_i^{'} - u_i$
8. For each $i$, create a TransactionDTO.  If $\Delta_i$ is greater than 0, the transactionType is BUY; if less than 0, it is SELL.  If $\Delta_i$ is 0, skip it without creating a TransactionDTO.  The securityId is the security of $s_i$, the quantity is the absolute value of $\Delta_i$.  The tradeDate is the current systems date.
9. For each $i$, create a driftDTO. The securityId is the securityId of $s_i$.  The original quantity is the original value of $u_i$.  The adjusted quantity is $u_i^{'}$.  The target, highDrift, and lowDrift come from the associated model for position $s_i$.  The field actual is calculated as $(u^{'} \cdot p)/MV$ and rounded to 4 decimal places.
10. Create a RebalanceDTO with the portfolioId, the list of TransactionDTO, and the list of DriftDTO.

**Note**: Rebalances may be parallelized up to the number of available threads, unless configured differently.  It should be possible to change configuration easily.  

**Note**: In this version of the service, Orders are not sent directly to the Order Service.  They will be returned to the API caller (generally a UI) which will decide what to do.



## Slice Requirements

The slice requirements will be implemented in a second phase.


## External Services

### Portfolio Accounting Service
- Host: globeco-portfolio-accounting-service
- Port: 8087
- OpenAPI Schema: [Portfolio Accounting Service OpenAPI Schema](portfolio-accounting-service-openapi.yaml)
- Sample Balance DTO:
    ```yaml
    {
        "id": 2,
        "portfolioId": "683b6d88a29ee10e8b499643",
        "quantityLong": "3366336",
        "quantityShort": "0",
        "lastUpdated": "2025-06-01T15:06:41Z",
        "version": 2
    }
    ```    

### Portfolio Service
- Host: globeco-portfolio-service
- Port: 8000
- OpenAPI Schema: [Portfolio Service OpenAPI Schema](portfolio-service-openapi.yaml)
- Sample Portfolio DTO:
    ```yaml
     {
        "portfolioId": "683b6d88a29ee10e8b499643",
        "name": "Portfolio 1",
        "dateCreated": "2025-05-31T20:58:48.833000",
        "version": 1
    }
    ```
### Real-Time Pricing Service
- Host: globeco-pricing-service
- Port: 8083
- OpenAPI Schema: [Pricing Service OpenAPI Schema](pricing-service-openapi.yaml)
- Sample Price DTO:
    ```yaml
    {
        "id": 1,
        "ticker": "A",
        "date": "2014-12-12",
        "open": 40.33,
        "close": 40.33,
        "high": 40.33,
        "low": 40.33,
        "volume": 0
    }
    ```

### Security Service
- Host: globeco-security-service
- Port: 8000
- Open API Schema: [Security Service OpenAPI Schema](security-service-openapi.yaml)
- Sample Security DTO:
    ```yaml
    {
        "ticker": "A",
        "description": "AGILENT TECHNOLOGIES, INC.",
        "securityTypeId": "683b6b9620f302c879a5fef3",
        "version": 1,
        "securityId": "683b6b9620f302c879a5fef4",
        "securityType": {
        "securityTypeId": "683b6b9620f302c879a5fef3",
        "abbreviation": "CS",
        "description": "Common Stock"
    }
    ```

### Portfolio Optimization Service
- Host: globeco-portfolio-optimization-service
- Port: TBD
- Open API Schema: TBD
- This service will be implemented in Phase 2 of this project.


### Order Service
- Host: globeco-order-service
- Port: 8081
- Open API Schema: [Order Service OpenAPI Schema](order-service-openapi.yaml)
- Sample POST DTO
    ```json
    {
        "blotterId": 1,
        "statusId": 1,
        "portfolioId": "683b6d88a29ee10e8b499643",
        "orderTypeId": 1,
        "securityId": "683b6b9620f302c879a5fef4",
        "quantity": 1000,
        "limitPrice": 32.50,
        "tradeOrderId": null,
        "orderTimestamp": "2025-06-02T14:40:54.658Z",
        "version": 1
    }
    ```
- Sample Response DTO:
    ```json
    {
        "id": 1,
        "blotter": {
            "id": 1,
            "name": "Default",
            "version": 1
        },
        "status": {
            "id": 1,
            "abbreviation": "NEW",
            "description": "New",
            "version": 1
        },
        "portfolioId": "683b6d88a29ee10e8b499643",
        "orderType": {
            "id": 1,
            "abbreviation": "BUY",
            "description": "Buy",
            "version": 1
        },
        "securityId": "683b6b9620f302c879a5fef4",
        "quantity": 1000,
        "limitPrice": 32.5,
        "tradeOrderId": null,
        "orderTimestamp": "2025-06-02T14:40:54.658Z",
        "version": 1
    }

    ```

## Error Handling

1. If the solver fails to find a solution or is still processing after 30 seconds, return an HTTP 422 status code with the message that "no feasible solution exists."  The 30 second timeout must be easily configuarable.

2. For all external services, retry 3 times.  The timeout and number of retries must be easily configurable.  

3. The Portfolio Accounting and Pricing Services are required for rebalancing.  If either service is unavailable even after retries, return an appropriate error and error message.  If a service is unavailable for one rebalance it is likely unavailable for all, so terminate after the first failed rebalance.



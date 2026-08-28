# General rule pack: order-to-cash leakage (UK mid-market)

Read this before touching `modules/reconcile/` or `modules/scoring/`.
Every rule below is implemented over the canonical model and priced from
the contract price book. A rule never guesses a price; the price book is
the single source of pounds.

## How pricing works

Each exception carries:

- `rule_id`: which rule fired
- `record_refs`: the canonical ids that triggered it (minimum two)
- `formula`: a stored human-readable arithmetic string, for example
  `2 units x 412.50 GBP (KESTREL-CON-001, ACME-STD-BRACKET)`
- `amount_minor`: integer pence, computed in `scoring` only

The price book (`price_book_entry`) maps contract + sku/service_code to a
unit price in pence. Late-delivery penalty amounts live on the contract row
(`late_delivery_penalty_minor`).

## Rules

### R01 delivered_not_invoiced

A delivery line with no matching invoice line for the same customer, sku
and quantity or less, within `invoice_window_days` (default 21) of the
delivery date. Price: delivered units x unit price. This is the classic
leak: work done, money never asked for.

### R02 invoiced_not_delivered

An invoice line with no delivery covering the quantity. Exposure, not a
completed leak: the customer may dispute, refund, or churn. Priced at
invoiced units x unit price and flagged as exposure. Delivering after
invoicing resolves it on the next run.

### R03 quantity_mismatch

Invoice line quantity differs from the matched delivery line quantity.
Price: the difference x unit price, signed by direction (over-delivery
underbilled, over-billed refund risk). The planted 100 vs 96 case lives
here.

### R04 rate_mismatch

Invoice line unit price differs from the contracted price for that
contract and sku. Price: quantity x (invoiced price - contracted price).
Every unit sold at the wrong rate is margin leaking silently.

### R05 duplicate_invoice

Two invoices for the same customer with the same external reference or the
same (sku, quantity, amount) within `duplicate_window_days` (default 14).
Price: the duplicated amount. Paid duplicates are cash out the door;
unpaid ones are a process smell.

### R06 service_not_invoiced

A service event (consultancy, installation hours, haulage surcharge) with
no invoice line referencing its code within `invoice_window_days`. Price:
units x service rate. Service-heavy mid-market businesses are the worst
affected; this is where the near-10 percent studies bite.

### R07 late_delivery_credit

A delivery later than the promised date on the order, where the contract
carries a penalty clause (a price book row of kind `penalty`). Price: the
clause amount. This leak is owed TO the customer; catching it first is a
trust play, because the alternative is the customer finding it.

## Statuses and the loop

open, assigned, resolved, accepted_risk. Recovery is recorded against the
exception with an amount and evidence note. Accepted risk requires a
reason string. The weekly digest reads only this store.

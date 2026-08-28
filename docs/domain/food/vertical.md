# Food vertical pack (first wedge)

A rule pack layered on top of the general order-to-cash pack. Read the
general pack first: the pricing mechanism, statuses and loop are identical.
What differs is what the records mean and which leaks only exist in food.

## Why food is the flagship vertical

- Margin pressure is severe and rising: 43 percent of UK food and drink
  businesses reported cost increases above 10 percent, with labour the
  biggest driver. Finance leaders are actively hunting recoverable revenue.
- Food operations produce exactly the kind of event records that reconcile
  badly with finance: batch yields, quality rejections, shelf-life
  write-offs. The gaps are large and recurring.
- Prior work (a chilled-food QC and traceability system) provides real
  domain depth: batch-code conventions, shelf-life clocks, retailer
  chargeback behaviour. The general engine needs no changes to absorb it.

## Vertical rules (additive to R01-R07)

### F01 rejected_batch_billed

A quality hold or rejection record for a batch, where the corresponding
finished-goods invoice still shipped at full quantity. Price: affected
units x unit price. A rejected batch that reaches a customer becomes a
chargeback plus a goodwill credit plus a replacement run; catching it
before dispatch is the whole value.

### F02 yield_shortfall_unbilled

Production planned N units from a batch, yield recorded M < N, and the
invoice was raised for N from stock movements that do not support it.
Priced as an exposure like R02: the variance is a costing correction, not
always a recovery.

### F03 shelf_life_writeoff

Stock aged past its shelf-life clock and written off while orders were
open that could have consumed it. Price: written-off units x unit price.
This is the leak that makes production planning and sales visibility a
finance conversation.

## Data expectations

The food fixture pack (`data/fixtures/food/`) adds batch, quality_hold and
stock_movement CSVs to the generic set. Batch codes follow the plant
convention of a production date and line marker inside the code; the
general engine never parses them, only the vertical pack does, in its own
service layer.

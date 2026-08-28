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

A quality hold that was never released, where stock from that batch moved
out (shipped) on or after the hold date. Price: shipped units x contracted
unit price. A rejected batch that reaches a customer becomes a chargeback
plus a goodwill credit plus a replacement run; catching it before dispatch
is the whole value.

### F02 yield_shortfall_unbilled

A batch whose yield fell short of plan, where invoiced units of that sku
for that customer exceed what was actually produced. Priced as an
exposure: the excess units x contracted unit price. The variance is a
costing correction, not always a recovery.

### F03 shelf_life_writeoff

Stock written off. Price: written-off units x contracted unit price.
Checking open demand before disposal is a refinement, not a gate; the
pounds lost are real either way. This is the leak that makes production
planning and sales visibility a finance conversation.

## Golden numbers (fixture pack, as tested)

The food fixture set produces the 7 general exceptions plus:

- F01: 182 units x GBP 265.00 = GBP 48,230.00 (batch B-2201 shipped after hold H-3301)
- F02: 103 units x GBP 265.00 = GBP 27,295.00 (285 invoiced vs 182 produced)
- F03: 18 units x GBP 265.00 = GBP 4,770.00 (movement M-4402)

Total at risk across both packs: GBP 95,405.00 across 10 exceptions.

## Data expectations

The food fixture pack (`data/fixtures/food/`) adds batch, quality_hold and
stock_movement CSVs to the generic set. Batch codes follow the plant
convention of a production date and line marker inside the code; the
general engine never parses them, only the vertical pack does, in its own
service layer.

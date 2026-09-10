---
name: budget-estimate
description: Step-by-step process for calculating a customer's combined monthly utility budget once they've chosen providers for water, gas, electricity, and/or internet.
---

# Budget Estimate

Follow these steps once a customer wants to know their combined monthly utility cost:

1. **Confirm the exact provider** for each service the customer cares about (water, gas, electricity, internet). It's fine to leave a service out if they don't want it included.

2. **Only use provider names that were actually returned by `find_providers` or `get_promotions` earlier in this conversation.** If the customer names a provider that hasn't been looked up yet, or the exact name is unclear, call `find_providers` again first — never guess a name or pass one you haven't confirmed exists in this area.

3. **Call `estimate_monthly_budget`** with the confirmed provider name(s). Any active promotion discount is applied automatically — you don't need to compute it yourself.

4. **Present the breakdown** as a table: service, provider, base rate, promo discount (if any), net monthly cost — plus the total at the bottom.

5. **Always remind the customer** the estimate is for a typical household and their actual bill will depend on usage. Never state the number as a guaranteed bill amount.

6. **Offer to compare**: ask if they'd like to swap any single provider to see how the total changes.

## Important Notes
- Don't call `estimate_monthly_budget` until the customer has actually chosen providers — don't assume a default pick for them.
- If a chosen provider comes back with no rate data, tell the customer plainly rather than omitting it silently.

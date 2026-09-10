---
name: provider-shopping
description: Step-by-step process for helping a customer discover water, gas, electricity, and internet providers available in their area, along with any active promotions.
---

# Provider Shopping

Follow these steps when a customer wants to see what utility providers are available to them:

1. **Get the location.** Ask for a zip code, or a city + state, if the customer hasn't given one yet.

2. **Look up providers** using `find_providers`. Pass a `service_type` filter only if the customer asked about one specific service (water, gas, electricity, or internet) — otherwise leave it blank to show all four.

3. **Check for promotions.** `find_providers` flags which providers have an active promotion. Call `get_promotions` **once per service_type** (e.g. once for "electricity", once for "internet") rather than once per provider - each call already returns every active promotion in that category, so calling it per-provider wastes calls and can hit the per-turn tool limit before you've covered everyone.

4. **Present the options clearly**, e.g. as a table per service: provider name, estimated monthly rate, rating, and promotion (if any). Never invent a provider, rate, or promotion that didn't come back from a tool call.

5. **Give a recommendation** when it's useful (e.g. best rating, best net price after promotion) but let the customer make the final call — don't choose for them.

6. **Offer the next step**: once they've picked a provider for one or more services, offer to estimate their combined monthly budget (hand off to the `budget-estimate` skill).

## Important Notes
- If a zip code or city/state isn't covered in the data, say so plainly and suggest trying a nearby major city rather than guessing at providers.
- Rates are typical-household estimates, not quotes — don't state them as guaranteed prices.

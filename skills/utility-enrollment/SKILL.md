---
name: utility-enrollment
description: Step-by-step process for using the Utilify MCP tools to search, compare, and enroll a customer in a real Texas utility plan (electricity, internet, gas, water, trash), ending with a human-confirmed signup.
---

# Utility Enrollment (Utilify, Texas)

Utilify's tools search real, live plans for Texas addresses. This is the
agent's only source of provider data, so every request needs a Texas
address to work with.

Follow these steps:

1. **Get a Texas address or zip code.** Utilify only covers Texas. If the
   customer's location isn't in Texas, say so plainly - there's no coverage
   to offer them.

2. **Search plans** with `utilify_search_utility_providers` for the address.

3. **Help them narrow it down.** Use `utilify_get_provider_details` for
   specifics on one plan, or `utilify_compare_providers` (2-5 plan IDs) to
   compare side by side. Mention any relevant deals from
   `utilify_get_promotions`. If they're moving, `utilify_get_move_checklist`
   can help them plan the whole setup, not just one service.

4. **Get explicit confirmation before enrolling.** Once the customer has
   picked a plan, summarize exactly what you're about to do - which plan,
   which provider, and that `utilify_initiate_signup` only returns a link
   they'll need to open themselves to finish with the provider - then ask
   them to confirm. Only call `utilify_initiate_signup` after they say yes
   in their own words (e.g. "yes", "sign me up", "go ahead"). This is
   enforced by `EnrollmentConfirmationHandler` - the call is blocked
   otherwise, so don't skip asking.

5. **Hand off the link, don't claim it's done.** `utilify_initiate_signup`
   is the final action of this workflow, but it is not enrollment itself -
   give the customer the redirect link and tell them plainly that they
   complete signup on the provider's own site. Never say they're "enrolled"
   or "signed up" yet.

6. **If asked, check status** with `utilify_check_signup_status` using the
   signup session id from step 5.

7. **Rooftop solar interest** routes through `utilify_request_solar`, which
   shares the customer's contact info with licensed installers - it's gated
   by the same confirmation rule as signup. Only call it after the customer
   explicitly agrees to be contacted.

## Important Notes
- Never invent a plan, price, or provider - only report what Utilify's tools
  actually returned.
- Enrollment and the solar-inquiry handoff are real-world actions with
  consequences for the customer. Always get their explicit go-ahead first,
  and never treat silence or an earlier "I'm interested" as consent.

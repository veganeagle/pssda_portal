# Launch checklist (owner to confirm before opsci.ca goes public)

Not served by the app. Items that can't be settled from the code alone.

## Contact
- [ ] Confirm support@kdsay.com is monitored and is the address to publish (Contact, Privacy pages).

## Privacy page — "Website information" section
Currently states only what the code guarantees: no cookies, no analytics/ads,
no third-party requests (fonts self-hosted), rate-limiter IPs held in memory <= 1 hour.
Still to settle at deploy time, then add to the page:
- [ ] Web server access logs: on/off, IP truncation, retention period (Caddy/gunicorn config).
- [ ] Hosting location (Hetzner region) and who has server access.
- [ ] How long contact emails are kept, and who can read the mailbox.

## Owner review
- [ ] About, About the data, Terms copy — launch drafts, not legal review.
- [ ] Indexing scope: tabs only vs. also sector/employer/position pages (Stage 3).

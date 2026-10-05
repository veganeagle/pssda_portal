# Launch checklist (owner to confirm)

Not served by the app. Items that can't be settled from the code alone.

## Contact
- [ ] Confirm support@kdsay.com is monitored and is the address to publish (Contact, Privacy pages).
- [ ] How long contact emails are kept, and who can read the mailbox (Privacy page doesn't state this yet).

## Settled at deploy (2026-10-04)
- [x] Access logs: none (no Caddy `log` directive, gunicorn access log off). Privacy page says so.
- [x] Hosting: Hetzner, Falkenstein, Germany. Privacy page says so.
- [x] Server access: root SSH by key only, password login disabled.
- [x] Indexing: home, the four tabs, sector pages, employer pages and text pages; everything else noindex (web_app/seo.py).

## Owner review
- [ ] About, About the data, Terms copy — launch drafts, not legal review.

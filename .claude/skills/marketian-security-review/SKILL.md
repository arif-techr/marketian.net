---
name: marketian-security-review
description: Use when reviewing a Marketian change or a whole site for security - sign-in and admin rights, tenant isolation, secrets, uploads, open redirects, webhooks, rate limits - or when asked "is this safe".
---

# Security review for Marketian code

Review the diff (`git diff main...`, or the files named), then the code it calls. Report each finding
as: file:line, what an attacker does, what happens, the fix. Rank by impact. Say what you checked and
found clean, too. Prove a finding with a test where you can.

## 1. Who is signed in, and what may they do
- Every view with user or organisation data: `@login_required` (or DRF permission) **and** an
  ownership/tenant filter. A missing filter = one customer sees another's data.
- Tracking: all workspace data goes through `workspaces/access.py` (`for_workspace`,
  `get_for_workspace_or_404`, `WorkspaceScopedMixin`, `role_required`); someone else's object gives
  404, never 403. SMS: organisation (`tenant`) + RBAC permission from the contract. Links/metadata:
  filter by `request.user`.
- Rights granted from an email (`ADMIN_EMAILS`, WA's allow list, invitations) must require
  `email_verified`. Accounts lets anyone sign up with any address (verification is optional).
- Staff/admin endpoints check the permission, not just "signed in".
- IDs in URLs: guessable integers are fine only behind an ownership check.

## 2. Input and output
- No raw SQL with string formatting; ORM or parameters only.
- Templates: no `|safe` / `mark_safe` on user input. Bio pages and link titles are user content.
- Redirects: `next`/return URLs go through `url_has_allowed_host_and_scheme` (products) or
  `AccountAdapter.is_safe_url` (accounts). Short links redirect anywhere by design, so keep the
  preview page (`/<slug>+`) and the per-day limit (`LINKS_PER_DAY`).
- Uploads: size limit (Caddy `request_body` + Django), type checked by content (Pillow), stored under
  `/app/media`, served with no execution. Check the filename can't escape the folder.
- SSRF: anything that fetches a user-given URL (metadata, webhooks, tracking destinations) must
  refuse private/internal addresses (see the `ipaddress` checks in tracking).

## 3. Secrets and config
- No secret in git (`git ls-files | grep -E "\.env$|\.pem|sqlite3"` is empty), logs, error messages
  or API answers. Secrets stored in the database are encrypted (tracking: AES-GCM helpers).
- The production guard refuses placeholder `SECRET_KEY`s when `DEBUG=False`. New secrets get added to
  that guard and to `.env.example` as `change-me`.
- `python manage.py check --deploy` clean with production settings.

## 4. Machine-to-machine
- Inbound webhooks / provider callbacks: verify the signature (constant-time compare) or re-validate
  with the gateway, before acting. Replays: timestamps or idempotency keys.
- Outbound webhooks: signed, with timeouts and retries; never follow redirects to internal hosts.
- API keys: shown once, stored hashed (with the pepper in SMS), scoped; compare in constant time.
- Rate limits on sign-in, sign-up, sends, and public endpoints.

## 5. Infrastructure
- Only `proxy` publishes ports. Databases and Redis on internal networks only.
- WA: `ALLOW_SIGNUP=false`, paced sending, daily limits (abuse = banned numbers).
- Tracking: Caddy on-demand TLS uses the `ask` endpoint so certificates are only issued for
  registered domains.

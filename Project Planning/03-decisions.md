# Decisions

Why things are the way they are. Newest first. Format: **Decision** (date, if known), then the reason.

- **WA Broadcaster owners sign in with the Marketian account. Team members and the admin keep username + password.** (2026-11) One login across products, and the broadcaster never sees owner passwords. With `ALLOW_SIGNUP=false`, only people the admin added (matched by verified email) can get in, because the tool can send WhatsApp messages from the server.
- **The WA Broadcaster keeps its own PostgreSQL + Redis instead of using the shared database.** It needs Redis for Celery, and its gateway sessions and data are heavy and sensitive. Its database and Redis sit on an internal-only network (`wa-data`).
- **The WhatsApp connection is unofficial (Baileys / Evolution API).** It's cheap and needs no Meta approval, but it breaks WhatsApp's terms and numbers can be banned. Mitigations: paced sending (8+ seconds between messages), daily limits, and rotating across several sender numbers. Test with a number you can afford to lose.
- **One VPS, one repo, one Docker Compose project.** Simple to run for a small team. `docker compose up -d` starts everything, and each site still deploys on its own.
- **Only Caddy is public. Sites never publish ports.** Smaller attack surface, and HTTPS certificates are automatic.
- **The SaaS products share one PostgreSQL server, with one database and login per product.** Cheaper than one server per product, and no product can read another's data.
- **Central accounts site over OpenID Connect.** Sign in once at accounts.marketian.net and every product trusts it. New products appear on the account page automatically.
- **Wildcard DNS (`*.marketian.net`).** A new product needs no DNS change.
- **htmx instead of a JS build step on the Django sites.** Fast page loads with a single vendored script file. The WA Broadcaster is the exception: it uses React, because its dashboard is very interactive.

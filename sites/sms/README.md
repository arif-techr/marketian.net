# Marketian SMS (sms.marketian.net)

Bulk SMS for Bangladesh: campaigns (including dynamic per-recipient SMS), contacts and groups,
templates, sender-ID approval, a Bangla-aware composer with live segment and cost preview,
a prepaid wallet with VAT invoices, a REST API with scoped keys and signed webhooks, and an
operator admin console. Sends through the Automas gateway.

**Status: being rebuilt, not live.** This site isn't in the root `docker-compose.yml` yet, so
`scripts/deploy.sh` doesn't start it. Plan and task list: [Project Planning/08-sms-plan.md](../../Project%20Planning/08-sms-plan.md).

## Layout

```
sites/sms/
├── web/        Next.js panel (from hivesms-lab / "SMSFlow BD"). Stays; gets the Marketian brand
│               and Marketian sign-in, and talks to the API below over /api/v1
├── api/        Django + DRF backend: being built. Answers the same /api/v1 contract as laravel/
├── laravel/    The original Laravel API: the reference for api/ (its tests are the acceptance
│               tests). Removed once api/ passes them
└── docs/       The original product, architecture, design system and API reference docs
```

## Where it's going

| | Now (laravel/) | Target |
|---|---|---|
| Backend | Laravel 12, PHP 8.3 | Django + DRF, Celery |
| Database | MariaDB | PostgreSQL on the shared server (`scripts/create-db.sh sms`) |
| Sign-in | Own email/password, Google | Marketian account (OpenID Connect) |
| Name | SMSFlow BD | Marketian SMS |
| Served by | its own Caddy | the shared proxy: `sms.marketian.net → sms-web:3000` |

The original docs in `docs/` describe the current Laravel/MariaDB version; the API reference
(`docs/11-laravel-api-reference.md`) is the contract the Django API must keep.

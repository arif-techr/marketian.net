---
name: marketian-signin
description: Use when touching anything about sign-in, sign-up, accounts.marketian.net, OpenID Connect, register_product, ADMIN_EMAILS, admin pages, email verification or "can't log in / can't create an account" problems in the Marketian repo.
---

# Marketian account and sign-in

## How it works
- **accounts.marketian.net** (`sites/accounts`) is the only place with passwords: django-allauth
  (email + password, optional GitHub) plus an OpenID Connect provider (django-oauth-toolkit) at `/o/`.
- **Products** (links, metadata, tracking, the portfolio's admin, WA owners, SMS) are allauth
  `openid_connect` clients with `provider_id: "marketian"`, PKCE, `SOCIALACCOUNT_ONLY = True`. They
  never see a password. Login URL on a product: `/accounts/oidc/marketian/login/`.
- **ID token / userinfo claims** come from `sites/accounts/portal/oidc.py`: `email`,
  `email_verified` (the primary `EmailAddress.verified`), `name`, `preferred_username`, `picture`.
  On the product, allauth stores them in `sociallogin.account.extra_data["userinfo"]` (and `["id_token"]`).
- **Registering a product:** `docker compose exec accounts python manage.py register_product <name> https://<name>.marketian.net`
  prints `MARKETIAN_CLIENT_ID` / `MARKETIAN_CLIENT_SECRET` for the product's `.env`. The redirect URI is
  `https://<name>.marketian.net/accounts/oidc/marketian/login/callback/`.
- **Sign-up and verification:** accounts' `EMAIL_VERIFICATION` (`.env`, default `optional`) controls
  whether the email link must be clicked. Set it to `mandatory` only once email actually sends,
  or nobody can sign up (this happened, 18 Nov 2026). Mail errors are logged, not raised
  (`portal/adapter.py`).

## Admin pages (`/admin/`)
- No admin password. `dashboard/admin_signin.py` (`core/admin_signin.py` in the portfolio) makes a
  user staff + superuser at each Marketian sign-in **only when the email is in `ADMIN_EMAILS` and
  `email_verified` is true**. Never drop the verified check: anyone can sign up on accounts with any
  address.
- The portfolio additionally refuses sign-up for anyone not in `ADMIN_EMAILS` (`SignupOnlyForAdmins`).
- The copies in links, metadata and tracking are identical: change all of them together and update
  each site's `AdminSignInTests`.
- An admin locked out because their email isn't verified: tick "Verified" for the address at
  accounts.marketian.net/admin/ → Email addresses (local superuser there), or click the email link.
- WA is the exception: owners use the Marketian account, team members and the admin keep
  username/password, and `ALLOW_SIGNUP=false` admits only people the admin added (matched by
  verified email).

## Rules
- Never add a separate password login to a product.
- Anything that grants rights from an email address must also require `email_verified`.
- Keep `is_safe_url` in `portal/adapter.py` limited to `https://*.{PRODUCTS_DOMAIN}` (http only when
  cookies aren't secure, i.e. local).
- Never log or store tokens (`SOCIALACCOUNT_STORE_TOKENS = False`).

## Debugging a sign-in failure (in this order)
1. Does the product's `.env` have `ACCOUNTS_URL`, `MARKETIAN_CLIENT_ID`, `MARKETIAN_CLIENT_SECRET`?
2. Is the product registered, with the exact callback URI? (accounts admin → Applications)
3. `curl https://accounts.marketian.net/o/.well-known/openid-configuration` answers 200.
4. `docker compose logs accounts <product>` around the attempt: redirect mismatch, invalid client,
   PKCE, clock skew, SMTP errors at sign-up.
5. Sign-up stuck: is `EMAIL_VERIFICATION=mandatory` while email doesn't send?

## Tests to copy
`sites/accounts/portal/tests.py` (`SignUpTests`, claims) and the products' `AdminSignInTests`
(the `sign_in(email, verified=True)` helper sends `user_logged_in` with fake claims).

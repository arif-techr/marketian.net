# Marketian SMS: API contract

Every endpoint the Django API (`sites/sms/api`) must answer exactly as the Laravel reference (`../laravel`) does: same method, path, auth, permission, request and response.
Generated on 2026-11-17 from Laravel's own route table (`php artisan route:list --json`). The machine-readable copy is [contract.json](contract.json); its `done` turns true as each endpoint passes its ported tests.
Response bodies and error codes: [../../docs/11-laravel-api-reference.md](../../docs/11-laravel-api-reference.md). Every JSON response uses the `{success, data|error, meta.requestId}` envelope, except provider callbacks and file downloads.

**248 endpoints:** 133 session, 84 staff, 20 public, 7 api_key, 4 signature.

| Auth | Meaning |
|---|---|
| public | no sign-in (rate-limited) |
| session | signed-in panel user (`Authorization: Bearer <session>`) |
| staff | session + platform permission (admin console) |
| api_key | customer's server (`Authorization: Bearer sfk_live_…`) with a key scope |
| signature | provider callbacks and payment returns, checked by signature or gateway re-validation |

Flags: `idempotent` honours `Idempotency-Key`; `feature X` needs feature switch X on; `verified.email` needs a confirmed address; `tenant` needs an active organisation.

## admin/abuse-reports (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/abuse-reports` | staff | admin:abuse:manage | — | admin_write_per_user | AdminPlatformController@abuseReports |
| PUT | `/v1/admin/abuse-reports/{id}` | staff | admin:abuse:manage | — | admin_write_per_user | AdminPlatformController@updateAbuse |

## admin/api-logs (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/api-logs` | staff | admin:messages:read | — | admin_write_per_user | AdminPlatformController@apiLogs |

## admin/audit-logs (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/audit-logs` | staff | admin:audit:read | — | admin_write_per_user | AdminPlatformController@auditLogs |

## admin/badges (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/badges` | staff | admin:access | — | admin_write_per_user | AdminPlatformController@badges |

## admin/blocklist (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/blocklist` | staff | admin:abuse:manage | — | admin_write_per_user | AdminSettingsController@blocklist |
| POST | `/v1/admin/blocklist` | staff | admin:abuse:manage | — | admin_write_per_user | AdminSettingsController@addBlocklist |
| DELETE | `/v1/admin/blocklist/{id}` | staff | admin:abuse:manage | — | admin_write_per_user | AdminSettingsController@removeBlocklist |

## admin/campaigns (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/campaigns` | staff | admin:campaigns:review | — | admin_write_per_user | AdminReviewController@campaigns |
| POST | `/v1/admin/campaigns/{id}/review` | staff | admin:campaigns:review | — | admin_write_per_user | AdminReviewController@reviewCampaign |

## admin/customers (9)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/customers` | staff | admin:customers:read | — | admin_write_per_user | AdminCustomerController@index |
| GET | `/v1/admin/customers/{id}` | staff | admin:customers:read | — | admin_write_per_user | AdminCustomerController@show |
| PUT | `/v1/admin/customers/{id}/controls` | staff | admin:customers:manage | — | admin_write_per_user | AdminCustomerController@updateControls |
| GET | `/v1/admin/customers/{id}/pricing` | staff | admin:customers:read | — | admin_write_per_user | AdminCustomerPricingController@show |
| PUT | `/v1/admin/customers/{id}/pricing` | staff | admin:pricing:customer | — | admin_write_per_user | AdminCustomerPricingController@update |
| POST | `/v1/admin/customers/{id}/pricing/reset` | staff | admin:pricing:customer | — | admin_write_per_user | AdminCustomerPricingController@reset |
| POST | `/v1/admin/customers/{id}/status` | staff | admin:customers:manage | — | admin_write_per_user | AdminCustomerController@status |
| GET | `/v1/admin/customers/{id}/usage` | staff | admin:customers:read | — | admin_write_per_user | AdminUsageController@show |
| POST | `/v1/admin/customers/{id}/wallet-adjustments` | staff | admin:wallet:adjust | — | admin_write_per_user | AdminFinanceController@adjustWallet |

## admin/dashboard (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/dashboard` | staff | admin:access | — | admin_write_per_user | AdminFinanceController@dashboard |

## admin/exports (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/exports/{kind}` | staff | admin:reports:export | — | admin_write_per_user | AdminExportController@export |

## admin/finance (6)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/finance/margins` | staff | admin:finance:read | — | admin_write_per_user | AdminFinanceController@margins |
| GET | `/v1/admin/finance/provider-balance` | staff | admin:finance:read | — | admin_write_per_user | AdminFinanceController@providerBalance |
| GET | `/v1/admin/finance/provider-costs` | staff | admin:finance:read | — | admin_write_per_user | AdminFinanceController@providerCosts |
| PUT | `/v1/admin/finance/provider-costs` | staff | admin:costs:manage | — | admin_write_per_user | AdminFinanceController@saveProviderCosts |
| GET | `/v1/admin/finance/summary` | staff | admin:finance:read | — | admin_write_per_user | AdminFinanceController@summary |
| GET | `/v1/admin/finance/transactions` | staff | admin:finance:read | — | admin_write_per_user | AdminFinanceController@transactions |

## admin/leads (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/leads` | staff | admin:customers:read | — | admin_write_per_user | AdminPlatformController@leads |
| PUT | `/v1/admin/leads/{id}` | staff | admin:customers:read | — | admin_write_per_user | AdminPlatformController@updateLead |

## admin/messages (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/messages` | staff | admin:messages:read | — | admin_write_per_user | AdminPlatformController@messages |
| GET | `/v1/admin/messages/unconfirmed` | staff | admin:messages:read | — | admin_write_per_user | AdminOperationsController@unconfirmed |
| POST | `/v1/admin/messages/{id}/resolve` | staff | admin:messages:resolve | — | admin_write_per_user | AdminOperationsController@resolve |

## admin/overview (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/overview` | staff | admin:access | — | admin_write_per_user | AdminPlatformController@overview |

## admin/payment-methods (7)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/payment-methods` | staff | admin:settings:manage | feature manual_topups | admin_write_per_user | AdminManualPaymentController@methods |
| POST | `/v1/admin/payment-methods` | staff | admin:settings:manage | feature manual_topups | admin_write_per_user | AdminManualPaymentController@storeMethod |
| POST | `/v1/admin/payment-methods/reorder` | staff | admin:settings:manage | feature manual_topups | admin_write_per_user | AdminManualPaymentController@reorder |
| DELETE | `/v1/admin/payment-methods/{id}` | staff | admin:settings:manage | feature manual_topups | admin_write_per_user | AdminManualPaymentController@destroyMethod |
| PUT | `/v1/admin/payment-methods/{id}` | staff | admin:settings:manage | feature manual_topups | admin_write_per_user | AdminManualPaymentController@updateMethod |
| GET | `/v1/admin/payment-methods/{id}/qr` | staff | admin:settings:manage | feature manual_topups | admin_write_per_user | AdminManualPaymentController@qr |
| POST | `/v1/admin/payment-methods/{id}/qr` | staff | admin:settings:manage | feature manual_topups | admin_write_per_user | AdminManualPaymentController@uploadQr |

## admin/payments (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/payments` | staff | admin:billing:read | — | admin_write_per_user | AdminReviewController@payments |
| POST | `/v1/admin/payments/{id}/refund` | staff | admin:payments:refund | — | admin_write_per_user | AdminFinanceController@refund |
| POST | `/v1/admin/payments/{id}/review` | staff | admin:billing:manage | — | admin_write_per_user | AdminReviewController@reviewPayment |

## admin/pricing (6)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/pricing/packages` | staff | admin:pricing:manage | — | admin_write_per_user | AdminSettingsController@packages |
| POST | `/v1/admin/pricing/packages` | staff | admin:pricing:manage | — | admin_write_per_user | AdminSettingsController@storePackage |
| PUT | `/v1/admin/pricing/packages/{id}` | staff | admin:pricing:manage | — | admin_write_per_user | AdminSettingsController@updatePackage |
| GET | `/v1/admin/pricing/plans` | staff | admin:pricing:manage | — | admin_write_per_user | AdminSettingsController@plans |
| POST | `/v1/admin/pricing/plans` | staff | admin:pricing:manage | — | admin_write_per_user | AdminSettingsController@storePlan |
| PUT | `/v1/admin/pricing/plans/{id}` | staff | admin:pricing:manage | — | admin_write_per_user | AdminSettingsController@updatePlan |

## admin/sender-catalog (5)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/sender-catalog` | staff | admin:sender_catalog:manage | feature sender_catalog | admin_write_per_user | AdminOperationsController@catalog |
| POST | `/v1/admin/sender-catalog` | staff | admin:sender_catalog:manage | feature sender_catalog | admin_write_per_user | AdminOperationsController@addCatalog |
| POST | `/v1/admin/sender-catalog/sync` | staff | admin:sender_catalog:manage | feature sender_catalog | admin_write_per_user | AdminOperationsController@syncCatalog |
| PUT | `/v1/admin/sender-catalog/{id}` | staff | admin:sender_catalog:manage | feature sender_catalog | admin_write_per_user | AdminOperationsController@updateCatalog |
| PUT | `/v1/admin/sender-catalog/{id}/assignments` | staff | admin:sender_catalog:manage | feature sender_catalog | admin_write_per_user | AdminOperationsController@assignCatalog |

## admin/sender-ids (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/sender-ids` | staff | admin:sender_ids:review | — | admin_write_per_user | AdminReviewController@senderIds |
| GET | `/v1/admin/sender-ids/{id}/documents/{index}` | staff | admin:sender_ids:review | — | admin_write_per_user | AdminReviewController@senderIdDocument |
| POST | `/v1/admin/sender-ids/{id}/review` | staff | admin:sender_ids:review | — | admin_write_per_user | AdminReviewController@reviewSenderId |

## admin/settings (6)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/settings` | staff | admin:settings:manage | — | admin_write_per_user | AdminSettingsController@settings |
| GET | `/v1/admin/settings/billing-policy` | staff | admin:pricing:manage | — | admin_write_per_user | AdminSettingsController@billingPolicy |
| PUT | `/v1/admin/settings/billing-policy` | staff | admin:pricing:manage | — | admin_write_per_user | AdminSettingsController@updateSettings |
| GET | `/v1/admin/settings/campaign-processing` | staff | admin:settings:manage | — | admin_write_per_user | AdminOperationsController@processingSettings |
| PUT | `/v1/admin/settings/campaign-processing` | staff | admin:settings:manage | — | admin_write_per_user | AdminOperationsController@updateProcessingSettings |
| PUT | `/v1/admin/settings/{section}` | staff | admin:settings:manage | — | admin_write_per_user | AdminSettingsController@updateSettings |

## admin/staff (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| POST | `/v1/admin/staff` | staff | admin:users:manage | — | admin_write_per_user | AdminStaffController@invite |
| GET | `/v1/admin/staff/history` | staff | admin:users:manage | — | admin_write_per_user | AdminStaffController@history |
| GET | `/v1/admin/staff/permissions` | staff | admin:users:manage | — | admin_write_per_user | AdminStaffController@permissions |

## admin/stats (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/stats` | staff | admin:access | — | admin_write_per_user | AdminPlatformController@stats |

## admin/support (4)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/support/tickets` | staff | admin:support | — | admin_write_per_user | AdminSupportController@index |
| GET | `/v1/admin/support/tickets/{id}` | staff | admin:support | — | admin_write_per_user | AdminSupportController@show |
| POST | `/v1/admin/support/tickets/{id}/messages` | staff | admin:support | — | admin_write_per_user | AdminSupportController@reply |
| PUT | `/v1/admin/support/tickets/{id}/status` | staff | admin:support | — | admin_write_per_user | AdminSupportController@status |

## admin/system (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/system/health` | staff | admin:health:read | — | admin_write_per_user | AdminFinanceController@health |

## admin/topup-requests (7)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/topup-requests` | staff | admin:topups:review | feature manual_topups | admin_write_per_user | AdminManualPaymentController@index |
| GET | `/v1/admin/topup-requests/{id}` | staff | admin:topups:review | feature manual_topups | admin_write_per_user | AdminManualPaymentController@show |
| POST | `/v1/admin/topup-requests/{id}/approve` | staff | admin:topups:approve | feature manual_topups | admin_write_per_user | AdminManualPaymentController@approve |
| POST | `/v1/admin/topup-requests/{id}/notes` | staff | admin:topups:review | feature manual_topups | admin_write_per_user | AdminManualPaymentController@note |
| GET | `/v1/admin/topup-requests/{id}/proof` | staff | admin:topups:review | feature manual_topups | admin_write_per_user | AdminManualPaymentController@proof |
| POST | `/v1/admin/topup-requests/{id}/reject` | staff | admin:topups:approve | feature manual_topups | admin_write_per_user | AdminManualPaymentController@reject |
| POST | `/v1/admin/topup-requests/{id}/under-review` | staff | admin:topups:review | feature manual_topups | admin_write_per_user | AdminManualPaymentController@underReview |

## admin/usage (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/usage` | staff | admin:customers:read | — | admin_write_per_user | AdminUsageController@index |

## admin/users (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/users` | staff | admin:users:manage | — | admin_write_per_user | AdminPlatformController@users |
| PUT | `/v1/admin/users/{id}/access` | staff | admin:users:manage | — | admin_write_per_user | AdminStaffController@updateAccess |
| POST | `/v1/admin/users/{id}/password-reset` | staff | admin:customers:manage | — | admin_write_per_user | AdminStaffController@sendPasswordReset |

## admin/wallets (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/admin/wallets` | staff | admin:billing:read | — | admin_write_per_user | AdminCustomerController@wallets |

## app/api-keys (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/api-keys` | session | api_keys:read | — | dashboard_per_user | ApiKeyController@index |
| POST | `/v1/app/api-keys` | session | api_keys:manage | — | dashboard_per_user | ApiKeyController@store |
| DELETE | `/v1/app/api-keys/{id}` | session | api_keys:manage | — | dashboard_per_user | ApiKeyController@destroy |

## app/api-logs (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/api-logs` | session | api_keys:read | — | dashboard_per_user | ApiKeyController@logs |

## app/campaigns (18)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/campaigns` | session | campaigns:read | — | dashboard_per_user | CampaignController@index |
| POST | `/v1/app/campaigns` | session | campaigns:write | — | dashboard_per_user | CampaignController@store |
| POST | `/v1/app/campaigns/estimate` | session | campaigns:write,sms:send | verified.email, idempotent | dashboard_per_user, dashboard_send_per_user | CampaignController@estimate |
| POST | `/v1/app/campaigns/submit` | session | campaigns:write,sms:send | verified.email, idempotent | dashboard_per_user, dashboard_send_per_user | CampaignController@submit |
| DELETE | `/v1/app/campaigns/{id}` | session | campaigns:write | — | dashboard_per_user | CampaignController@destroy |
| GET | `/v1/app/campaigns/{id}` | session | campaigns:read | — | dashboard_per_user | CampaignController@show |
| PUT | `/v1/app/campaigns/{id}` | session | campaigns:write | — | dashboard_per_user | CampaignController@update |
| POST | `/v1/app/campaigns/{id}/cancel` | session | campaigns:write | — | dashboard_per_user | CampaignController@cancel |
| POST | `/v1/app/campaigns/{id}/duplicate` | session | campaigns:write | — | dashboard_per_user | CampaignController@duplicate |
| GET | `/v1/app/campaigns/{id}/export` | session | reports:export | — | dashboard_per_user | CampaignController@export |
| GET | `/v1/app/campaigns/{id}/messages` | session | campaigns:read | — | dashboard_per_user | CampaignController@messages |
| POST | `/v1/app/campaigns/{id}/pause` | session | campaigns:write | — | dashboard_per_user | CampaignController@pause |
| GET | `/v1/app/campaigns/{id}/progress` | session | campaigns:read | — | dashboard_per_user | CampaignController@progress |
| POST | `/v1/app/campaigns/{id}/resume` | session | campaigns:write | — | dashboard_per_user | CampaignController@resume |
| POST | `/v1/app/campaigns/{id}/retry` | session | campaigns:write,sms:send | verified.email, idempotent | dashboard_per_user, dashboard_send_per_user | CampaignController@retry |
| POST | `/v1/app/campaigns/{id}/schedule` | session | campaigns:write,sms:send | verified.email, idempotent | dashboard_per_user, dashboard_send_per_user | CampaignController@schedule |
| POST | `/v1/app/campaigns/{id}/send` | session | campaigns:write,sms:send | verified.email, idempotent | dashboard_per_user, dashboard_send_per_user | CampaignController@send |
| GET | `/v1/app/campaigns/{id}/stats` | session | campaigns:read | — | dashboard_per_user | CampaignController@stats |

## app/contact-groups (8)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/contact-groups` | session | contacts:read | — | dashboard_per_user | ContactGroupController@index |
| POST | `/v1/app/contact-groups` | session | contacts:write | — | dashboard_per_user | ContactGroupController@store |
| DELETE | `/v1/app/contact-groups/{id}` | session | contacts:write | — | dashboard_per_user | ContactGroupController@destroy |
| GET | `/v1/app/contact-groups/{id}` | session | contacts:read | — | dashboard_per_user | ContactGroupController@show |
| PUT | `/v1/app/contact-groups/{id}` | session | contacts:write | — | dashboard_per_user | ContactGroupController@update |
| DELETE | `/v1/app/contact-groups/{id}/contacts` | session | contacts:write | — | dashboard_per_user | ContactGroupController@detach |
| GET | `/v1/app/contact-groups/{id}/contacts` | session | contacts:read | — | dashboard_per_user | ContactGroupController@contacts |
| POST | `/v1/app/contact-groups/{id}/contacts` | session | contacts:write | — | dashboard_per_user | ContactGroupController@attach |

## app/contacts (10)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/contacts` | session | contacts:read | — | dashboard_per_user | ContactController@index |
| POST | `/v1/app/contacts` | session | contacts:write | — | dashboard_per_user | ContactController@store |
| POST | `/v1/app/contacts/bulk` | session | contacts:write | — | dashboard_per_user | ContactController@bulk |
| GET | `/v1/app/contacts/export` | session | contacts:export | — | dashboard_per_user | ContactExportController (invokable) |
| POST | `/v1/app/contacts/import` | session | contacts:write | — | dashboard_per_user | ContactImportController@store |
| GET | `/v1/app/contacts/imports/{importId}` | session | contacts:read | — | dashboard_per_user | ContactImportController@show |
| GET | `/v1/app/contacts/tags` | session | contacts:read | — | dashboard_per_user | ContactController@tags |
| DELETE | `/v1/app/contacts/{id}` | session | contacts:write | — | dashboard_per_user | ContactController@destroy |
| GET | `/v1/app/contacts/{id}` | session | contacts:read | — | dashboard_per_user | ContactController@show |
| PUT | `/v1/app/contacts/{id}` | session | contacts:write | — | dashboard_per_user | ContactController@update |

## app/dashboard (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/dashboard` | session | dashboard:read | — | dashboard_per_user | DashboardController (invokable) |

## app/dynamic-sms (6)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| POST | `/v1/app/dynamic-sms/estimate` | session | campaigns:write,sms:send | feature dynamic_sms, verified.email, idempotent | dashboard_per_user, dashboard_send_per_user | DynamicSmsController@estimate |
| POST | `/v1/app/dynamic-sms/preview` | session | campaigns:write,sms:send | feature dynamic_sms | dashboard_per_user, dashboard_send_per_user | DynamicSmsController@preview |
| POST | `/v1/app/dynamic-sms/submit` | session | campaigns:write,sms:send | feature dynamic_sms, verified.email, idempotent | dashboard_per_user, dashboard_send_per_user | DynamicSmsController@submit |
| GET | `/v1/app/dynamic-sms/template` | session | campaigns:read | feature dynamic_sms | dashboard_per_user | DynamicSmsController@template |
| POST | `/v1/app/dynamic-sms/uploads` | session | campaigns:write,sms:send | feature dynamic_sms | dashboard_per_user, dashboard_send_per_user | DynamicSmsController@upload |
| GET | `/v1/app/dynamic-sms/uploads/{id}` | session | campaigns:read | feature dynamic_sms | dashboard_per_user | DynamicSmsController@show |

## app/messages (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/messages` | session | reports:read | — | dashboard_per_user | ReportController@messages |
| GET | `/v1/app/messages/{id}` | session | reports:read | — | dashboard_per_user | ReportController@message |

## app/notifications (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/notifications` | session | — | tenant | dashboard_per_user | ProfileController@notifications |
| POST | `/v1/app/notifications/read` | session | — | tenant | dashboard_per_user | ProfileController@markNotificationsRead |

## app/organization (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/organization` | session | — | tenant | dashboard_per_user | ProfileController@organization |
| PUT | `/v1/app/organization` | session | settings:manage | — | dashboard_per_user | ProfileController@updateOrganization |
| POST | `/v1/app/organization/leave` | session | — | tenant | dashboard_per_user | ProfileController@leaveOrganization |

## app/payment-methods (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/payment-methods` | session | billing:read | feature manual_topups | dashboard_per_user | ManualTopUpController@methods |
| GET | `/v1/app/payment-methods/{id}/qr` | session | billing:read | feature manual_topups | dashboard_per_user | ManualTopUpController@qr |

## app/payments (8)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/payments` | session | billing:read | — | dashboard_per_user | PaymentController@index |
| POST | `/v1/app/payments` | session | billing:manage | idempotent | dashboard_per_user | PaymentController@store |
| GET | `/v1/app/payments/methods` | session | billing:read | — | dashboard_per_user | PaymentController@methods |
| POST | `/v1/app/payments/preview` | session | billing:read | — | dashboard_per_user | PaymentController@preview |
| GET | `/v1/app/payments/{id}` | session | billing:read | — | dashboard_per_user | PaymentController@show |
| POST | `/v1/app/payments/{id}/cancel` | session | billing:manage | — | dashboard_per_user | PaymentController@cancel |
| POST | `/v1/app/payments/{id}/mock-complete` | session | billing:manage | — | dashboard_per_user | PaymentController@mockComplete |
| POST | `/v1/app/payments/{id}/reference` | session | billing:manage | — | dashboard_per_user | PaymentController@submitReference |

## app/reports (6)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/reports/campaigns` | session | reports:read | — | dashboard_per_user | ReportController@campaigns |
| GET | `/v1/app/reports/delivery` | session | reports:read | — | dashboard_per_user | ReportController@delivery |
| GET | `/v1/app/reports/export` | session | reports:export | — | dashboard_per_user | ReportController@export |
| GET | `/v1/app/reports/filters` | session | reports:read | — | dashboard_per_user | ReportController@filterOptions |
| GET | `/v1/app/reports/messages` | session | reports:read | — | dashboard_per_user | ReportController@messages |
| GET | `/v1/app/reports/usage` | session | billing:read | — | dashboard_per_user | ReportController@usage |

## app/sender-ids (7)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/sender-ids` | session | sender_ids:read | — | dashboard_per_user | SenderIdController@index |
| POST | `/v1/app/sender-ids` | session | sender_ids:manage | — | dashboard_per_user | SenderIdController@store |
| GET | `/v1/app/sender-ids/approved` | session | sender_ids:read | — | dashboard_per_user | SenderIdController@approved |
| DELETE | `/v1/app/sender-ids/{id}` | session | sender_ids:manage | — | dashboard_per_user | SenderIdController@destroy |
| GET | `/v1/app/sender-ids/{id}` | session | sender_ids:read | — | dashboard_per_user | SenderIdController@show |
| PUT | `/v1/app/sender-ids/{id}` | session | sender_ids:manage | — | dashboard_per_user | SenderIdController@update |
| GET | `/v1/app/sender-ids/{id}/documents/{index}` | session | sender_ids:read | — | dashboard_per_user | SenderIdController@document |

## app/sms (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/sms/composer` | session | campaigns:write | — | dashboard_per_user | CampaignController@composer |
| POST | `/v1/app/sms/segments` | session | campaigns:write | — | dashboard_per_user | CampaignController@segments |

## app/support (5)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/support/tickets` | session | support:read | — | dashboard_per_user | SupportController@index |
| POST | `/v1/app/support/tickets` | session | support:write | — | dashboard_per_user | SupportController@store |
| GET | `/v1/app/support/tickets/{id}` | session | support:read | — | dashboard_per_user | SupportController@show |
| POST | `/v1/app/support/tickets/{id}/close` | session | support:write | — | dashboard_per_user | SupportController@close |
| POST | `/v1/app/support/tickets/{id}/messages` | session | support:write | — | dashboard_per_user | SupportController@reply |

## app/suppression (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/suppression` | session | contacts:read | — | dashboard_per_user | SuppressionController@index |
| POST | `/v1/app/suppression` | session | contacts:write | — | dashboard_per_user | SuppressionController@store |
| DELETE | `/v1/app/suppression/{id}` | session | contacts:write | — | dashboard_per_user | SuppressionController@destroy |

## app/team (6)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/team` | session | team:read | — | dashboard_per_user | TeamController@index |
| POST | `/v1/app/team/invitations` | session | team:manage | — | dashboard_per_user | TeamController@invite |
| DELETE | `/v1/app/team/invitations/{id}` | session | team:manage | — | dashboard_per_user | TeamController@revokeInvitation |
| PUT | `/v1/app/team/members/{memberId}/role` | session | team:manage | — | dashboard_per_user | TeamController@changeRole |
| POST | `/v1/app/team/members/{memberId}/status` | session | team:manage | — | dashboard_per_user | TeamController@setStatus |
| PUT | `/v1/app/team/roles/{role}/permissions` | session | team:manage | — | dashboard_per_user | TeamController@updateRolePermissions |

## app/templates (5)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/templates` | session | templates:read | — | dashboard_per_user | TemplateController@index |
| POST | `/v1/app/templates` | session | templates:write | — | dashboard_per_user | TemplateController@store |
| DELETE | `/v1/app/templates/{id}` | session | templates:write | — | dashboard_per_user | TemplateController@destroy |
| GET | `/v1/app/templates/{id}` | session | templates:read | — | dashboard_per_user | TemplateController@show |
| PUT | `/v1/app/templates/{id}` | session | templates:write | — | dashboard_per_user | TemplateController@update |

## app/topup-requests (5)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/topup-requests` | session | billing:read | feature manual_topups | dashboard_per_user | ManualTopUpController@index |
| POST | `/v1/app/topup-requests` | session | billing:manage | feature manual_topups, idempotent | dashboard_per_user, dashboard_send_per_user | ManualTopUpController@store |
| GET | `/v1/app/topup-requests/{id}` | session | billing:read | feature manual_topups | dashboard_per_user | ManualTopUpController@show |
| POST | `/v1/app/topup-requests/{id}/cancel` | session | billing:manage | feature manual_topups | dashboard_per_user, dashboard_send_per_user | ManualTopUpController@cancel |
| GET | `/v1/app/topup-requests/{id}/proof` | session | billing:read | feature manual_topups | dashboard_per_user | ManualTopUpController@proof |

## app/transactions (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/transactions/export` | session | billing:read | — | dashboard_per_user | WalletController@exportTransactions |

## app/wallet (7)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/wallet` | session | billing:read | — | dashboard_per_user | WalletController@show |
| GET | `/v1/app/wallet/invoices` | session | billing:read | — | dashboard_per_user | WalletController@invoices |
| GET | `/v1/app/wallet/invoices/{id}` | session | billing:read | — | dashboard_per_user | WalletController@invoice |
| PUT | `/v1/app/wallet/threshold` | session | billing:manage | — | dashboard_per_user | WalletController@threshold |
| GET | `/v1/app/wallet/transactions` | session | billing:read | — | dashboard_per_user | WalletController@transactions |
| GET | `/v1/app/wallet/transactions/export` | session | billing:read | — | dashboard_per_user | WalletController@exportTransactions |
| GET | `/v1/app/wallet/transactions/{id}` | session | billing:read | — | dashboard_per_user | WalletController@transaction |

## app/webhooks (5)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/app/webhooks` | session | api_keys:read | — | dashboard_per_user | ApiKeyController@webhooks |
| POST | `/v1/app/webhooks` | session | api_keys:manage | — | dashboard_per_user | ApiKeyController@storeWebhook |
| DELETE | `/v1/app/webhooks/{id}` | session | api_keys:manage | — | dashboard_per_user | ApiKeyController@destroyWebhook |
| PUT | `/v1/app/webhooks/{id}` | session | api_keys:manage | — | dashboard_per_user | ApiKeyController@updateWebhook |
| POST | `/v1/app/webhooks/{id}/test` | session | api_keys:manage | — | dashboard_per_user | ApiKeyController@testWebhook |

## auth (21)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| POST | `/v1/auth/email/resend` | session | — | — | otp_per_user | AuthController@resendVerification |
| POST | `/v1/auth/email/verify` | public | — | — | password_reset_per_ip | AuthController@verifyEmail |
| POST | `/v1/auth/forgot-password` | public | — | — | — | AuthController@forgotPassword |
| POST | `/v1/auth/google` | public | — | — | — | GoogleAuthController@signIn |
| POST | `/v1/auth/invitations/accept` | session | — | — | — | AuthController@acceptInvitation |
| POST | `/v1/auth/invitations/signup` | public | — | — | register_per_ip | AuthController@invitationSignup |
| GET | `/v1/auth/invitations/{token}` | public | — | — | public_form_per_ip | AuthController@invitation |
| POST | `/v1/auth/login` | public | — | — | — | AuthController@login |
| POST | `/v1/auth/logout` | session | — | — | — | AuthController@logout |
| GET | `/v1/auth/me` | session | — | — | — | AuthController@me |
| POST | `/v1/auth/organizations` | session | — | — | — | AuthController@createOrganization |
| POST | `/v1/auth/password/forgot` | public | — | — | — | AuthController@forgotPassword |
| POST | `/v1/auth/password/reset` | public | — | — | password_reset_per_ip | AuthController@resetPassword |
| POST | `/v1/auth/phone/otp` | session | — | — | — | AuthController@sendOtp |
| POST | `/v1/auth/phone/verify` | session | — | — | otp_per_user | AuthController@verifyOtp |
| GET | `/v1/auth/providers` | public | — | — | — | GoogleAuthController@providers |
| POST | `/v1/auth/register` | public | — | — | — | AuthController@register |
| POST | `/v1/auth/resend-verification` | session | — | — | otp_per_user | AuthController@resendVerification |
| POST | `/v1/auth/reset-password` | public | — | — | password_reset_per_ip | AuthController@resetPassword |
| POST | `/v1/auth/switch-organization` | session | — | — | — | AuthController@switchOrganization |
| POST | `/v1/auth/verify-email` | public | — | — | password_reset_per_ip | AuthController@verifyEmail |

## balance (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/balance` | api_key | balance:read | — | api_per_key | PublicApiController@balance |

## health (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/health` | public | — | — | — | HealthController (invokable) |

## internal (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/internal/ready` | public | — | — | — | HealthController@ready |
| GET, POST | `/v1/internal/worker/tick` | public | — | — | — | WorkerController (invokable) |

## messages (2)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/messages` | api_key | messages:read | — | api_per_key | PublicApiController@messages |
| GET | `/v1/messages/{id}` | api_key | messages:read | — | api_per_key | PublicApiController@message |

## payments (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET, POST | `/v1/payments/{provider}/return` | signature | — | — | webhook_per_ip | PaymentWebhookController@return |

## profile (8)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/profile` | session | — | — | dashboard_per_user | ProfileController@show |
| PUT | `/v1/profile` | session | — | — | dashboard_per_user | ProfileController@update |
| PUT | `/v1/profile/locale` | session | — | — | dashboard_per_user | ProfileController@locale |
| GET | `/v1/profile/notification-preferences` | session | — | — | dashboard_per_user | ProfileController@notificationPreferences |
| PUT | `/v1/profile/notification-preferences` | session | — | — | dashboard_per_user | ProfileController@saveNotificationPreferences |
| PUT | `/v1/profile/password` | session | — | — | dashboard_per_user | ProfileController@password |
| GET | `/v1/profile/sessions` | session | — | — | dashboard_per_user | ProfileController@sessions |
| DELETE | `/v1/profile/sessions/{id}` | session | — | — | dashboard_per_user | ProfileController@revokeSession |

## public (5)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| POST | `/v1/public/abuse-reports` | public | — | — | — | PublicController@abuse |
| POST | `/v1/public/contact` | public | — | — | — | PublicController@contact |
| GET | `/v1/public/policies` | public | — | — | — | PublicController@policies |
| GET | `/v1/public/pricing` | public | — | — | — | PublicController@pricing |
| GET | `/v1/public/site-content` | public | — | — | — | PublicController@siteContent |

## sender-ids (1)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| GET | `/v1/sender-ids` | api_key | sender_ids:read | — | api_per_key | PublicApiController@senderIds |

## sms (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| POST | `/v1/sms/bulk` | api_key | sms:send | idempotent | api_send_per_key | SmsController@bulk |
| POST | `/v1/sms/estimate` | api_key | sms:send | — | api_per_key | SmsController@estimate |
| POST | `/v1/sms/send` | api_key | sms:send | idempotent | api_send_per_key | SmsController@send |

## webhooks (3)

| Method | Path | Auth | Permission / scope | Flags | Rate limit | Laravel |
|---|---|---|---|---|---|---|
| POST | `/v1/webhooks/payments/{provider}` | signature | — | — | webhook_per_ip | PaymentWebhookController@ipn |
| POST | `/v1/webhooks/sms/{provider}` | signature | — | — | webhook_per_ip | SmsWebhookController@delivery |
| POST | `/v1/webhooks/sms/{provider}/inbound` | signature | — | — | webhook_per_ip | SmsWebhookController@inbound |

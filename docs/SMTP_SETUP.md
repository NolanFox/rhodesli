# Custom SMTP Setup: Resend + Supabase

**Goal**: Replace default "Supabase Auth <noreply@mail.app.supabase.io>" with "Rhodesli <noreply@nolanandrewfox.com>" (or similar) for all auth emails (signup confirmation, password reset, magic link, invite).

**Status**: Research complete, awaiting admin action.

---

## Table of Contents

1. [Why Custom SMTP](#why-custom-smtp)
2. [Provider Recommendation](#provider-recommendation)
3. [Prerequisites](#prerequisites)
4. [Step-by-Step Setup](#step-by-step-setup)
5. [Admin Action Items (All-in-One)](#admin-action-items-all-in-one)
6. [Verification](#verification)
7. [Gotchas and Limitations](#gotchas-and-limitations)
8. [Alternative Providers](#alternative-providers)

---

## Why Custom SMTP

Supabase's built-in email service:
- Sends from `noreply@mail.app.supabase.io` -- looks generic/suspicious to recipients
- Has a hard limit of **4 emails per hour** (not suitable for production)
- Is explicitly "for testing purposes only" per Supabase docs

With custom SMTP via Resend:
- Emails come from your own domain (e.g., `noreply@nolanandrewfox.com`)
- Higher sending limits (100/day on free tier)
- Full delivery tracking (sent, delivered, bounced, spam)
- Professional appearance builds trust with family members receiving invites

---

## Provider Recommendation

**Resend** is the recommended provider. Reasons:

| Criteria | Resend | SendGrid | Mailgun |
|----------|--------|----------|---------|
| Free tier | 3,000/month, 100/day | **No free tier** (removed 2025) | 100/day for first month only |
| Domains (free) | 1 domain | N/A | 1 domain |
| Supabase integration | Native one-click integration | Manual only | Manual only |
| Developer experience | Excellent (modern API, clear docs) | Dated | Good |
| SMTP support | Yes | Yes | Yes |
| Price if scaling | $20/mo for 50K emails | $20/mo for 50K | $35/mo for 50K |

For Rhodesli's use case (invite-only family app, maybe 5-20 auth emails/month), the Resend free tier is more than sufficient.

---

## Prerequisites

Before starting, you need:

1. **A Resend account** -- Sign up at https://resend.com (free, requires email verification)
2. **DNS access to nolanandrewfox.com** -- Likely via Cloudflare dashboard (since the project already uses Cloudflare)
3. **Supabase personal access token** -- From Supabase Dashboard > Account > Access Tokens (https://supabase.com/dashboard/account/tokens)

---

## Step-by-Step Setup

### Step 1: Create Resend Account

1. Go to https://resend.com and sign up
2. Verify your email address
3. You will land on the Resend dashboard

**This step is manual -- requires web signup.**

### Step 2: Add Domain to Resend

1. In the Resend dashboard, go to **Domains** (left sidebar)
2. Click **Add Domain**
3. Enter: `nolanandrewfox.com`
4. Resend will generate DNS records you need to add

**Alternatively**, you can use a subdomain like `mail.nolanandrewfox.com` to isolate email reputation from your main domain. This is considered best practice but is optional for a low-volume family app.

### Step 3: Add DNS Records to Cloudflare

Resend will show you DNS records that need to be added. The exact values are generated per-domain, but the typical records are:

| # | Type | Name/Host | Value | Purpose |
|---|------|-----------|-------|---------|
| 1 | **MX** | `send.nolanandrewfox.com` | `feedback-smtp.us-east-1.amazonses.com` (priority 10) | Bounce processing |
| 2 | **TXT** | `send.nolanandrewfox.com` | `v=spf1 include:amazonses.com ~all` | SPF -- authorizes Resend to send on your behalf |
| 3 | **TXT** | `resend._domainkey.nolanandrewfox.com` | `(long DKIM public key -- Resend generates this)` | DKIM -- email signing/authentication |

**Important notes:**
- The exact record values will be shown in your Resend dashboard after adding the domain -- use those, not the examples above
- Add all records in the Cloudflare DNS dashboard (DNS > Records > Add Record)
- If using Cloudflare proxy (orange cloud), set these DNS records to **DNS only** (grey cloud) -- email records should NOT be proxied
- Propagation can take up to 24 hours, but usually completes within minutes on Cloudflare

### Step 4: Verify Domain in Resend

1. After adding DNS records, go back to the Resend dashboard
2. Click on your domain
3. Click **Verify DNS Records**
4. Wait for all records to show "Verified" (green checkmark)

Status meanings:
- `not_started` -- Haven't clicked Verify yet
- `pending` -- Resend is checking (may take up to 72 hours)
- `verified` -- Ready to send
- `failed` -- DNS records not detected after 72 hours (re-check your records)

### Step 5: Get SMTP Credentials from Resend

1. In Resend dashboard, go to **API Keys** (left sidebar)
2. Click **Create API Key**
3. Name it something like `supabase-rhodesli-smtp`
4. Set permission to **Sending access** (not full access)
5. Copy the API key (starts with `re_...`) -- you will only see it once

The SMTP credentials are:

| Setting | Value |
|---------|-------|
| **Host** | `smtp.resend.com` |
| **Port** | `465` (SSL) or `587` (TLS) |
| **Username** | `resend` |
| **Password** | Your API key (`re_...`) |

### Step 6: Configure Supabase SMTP via Management API

**Option A: Native Integration (Easier)**

1. In the Resend dashboard, go to **Integrations** > **Supabase**
2. Click **Connect to Supabase**
3. Authorize Resend to access your Supabase project
4. Select the domain and set sender name/email
5. Resend automatically configures SMTP in your Supabase project

This is the simplest path -- Resend handles the SMTP configuration for you.

**Option B: Manual via Management API (If you prefer explicit control)**

Use this curl command (replace placeholders):

```bash
# Set your credentials
export SUPABASE_ACCESS_TOKEN="your-personal-access-token"
export PROJECT_REF="fvynibivlphxwfowzkjl"
export RESEND_API_KEY="re_your_api_key_here"

# Configure SMTP
curl -X PATCH "https://api.supabase.com/v1/projects/$PROJECT_REF/config/auth" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "smtp_admin_email": "noreply@nolanandrewfox.com",
    "smtp_host": "smtp.resend.com",
    "smtp_port": 465,
    "smtp_user": "resend",
    "smtp_pass": "'"$RESEND_API_KEY"'",
    "smtp_sender_name": "Rhodesli"
  }'
```

**Option C: Manual via Supabase Dashboard (No CLI needed)**

1. Go to your Supabase project dashboard
2. Navigate to **Project Settings** > **Authentication**
3. Scroll down to **SMTP Settings**
4. Toggle **Enable Custom SMTP** to ON
5. Fill in:
   - Sender email: `noreply@nolanandrewfox.com`
   - Sender name: `Rhodesli`
   - Host: `smtp.resend.com`
   - Port: `465`
   - Username: `resend`
   - Password: (your Resend API key)
6. Save

### Step 7: Increase Rate Limit (Recommended)

After enabling custom SMTP, Supabase defaults to a rate limit of 30 emails/hour. For a family app this is fine, but you may also want to adjust the per-user email frequency.

Via Management API:

```bash
curl -X PATCH "https://api.supabase.com/v1/projects/$PROJECT_REF/config/auth" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "smtp_max_frequency": 60
  }'
```

The `smtp_max_frequency` value is in seconds -- it controls the minimum time between emails to the same user for the same action. Default is 60 seconds (1 minute). For a family app, this default is fine.

You can also adjust in the Supabase dashboard under **Authentication** > **Rate Limits**.

---

## Admin Action Items (All-in-One)

Here is everything the admin needs to do, consolidated into a single checklist:

### Credentials Needed

- [ ] **Resend API key** -- Create account at https://resend.com, generate API key with "Sending access" permission
- [ ] **Supabase personal access token** -- From https://supabase.com/dashboard/account/tokens (only needed for Option B / Management API approach)

### Manual Steps (in order)

1. [ ] **Create Resend account** at https://resend.com
2. [ ] **Add domain** `nolanandrewfox.com` in Resend dashboard > Domains
3. [ ] **Copy the DNS records** Resend generates (will be 2-3 records)
4. [ ] **Add DNS records in Cloudflare** (DNS > Records > Add Record for each one; set to DNS-only/grey cloud)
5. [ ] **Verify domain** in Resend dashboard (click Verify DNS Records, wait for green checkmarks)
6. [ ] **Create API key** in Resend dashboard > API Keys (name: `supabase-rhodesli-smtp`, permission: Sending access)
7. [ ] **Configure Supabase SMTP** -- Use Option A (native integration), Option B (curl), or Option C (dashboard) from Step 6 above

### Estimated Time

- 10-15 minutes of active work
- Up to 24 hours for DNS propagation (usually minutes on Cloudflare)

---

## Verification

After setup, verify that emails are sending correctly:

### Quick Test: Trigger a Password Reset

```bash
# This will send a password reset email via your custom SMTP
curl -X POST "https://fvynibivlphxwfowzkjl.supabase.co/auth/v1/recover" \
  -H "apikey: YOUR_SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email": "your-test-email@example.com"}'
```

Or simply:
1. Go to the Rhodesli app
2. Click "Sign In"
3. Use the "Forgot Password" flow with a known email address
4. Check the inbox -- the email should come from `Rhodesli <noreply@nolanandrewfox.com>`

### Verify in Resend Dashboard

1. Go to Resend dashboard > **Logs**
2. You should see the email logged with delivery status
3. Status should show "Delivered" (not bounced or failed)

### Verify Current Config (Read-Only Check)

```bash
# Read current auth config to verify SMTP is set
curl -s "https://api.supabase.com/v1/projects/fvynibivlphxwfowzkjl/config/auth" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" | python3 -m json.tool | grep smtp
```

Expected output should show your custom SMTP host, port, and sender name.

---

## Gotchas and Limitations

### Known Issues

1. **Once you enable custom SMTP, you cannot easily revert to Supabase's default SMTP.** If your custom SMTP config has errors, you must fix them -- there is no "go back to default" toggle. Always test credentials before saving.

2. **Supabase imposes a low initial rate limit of 30 emails/hour** when custom SMTP is first enabled. This protects your sender reputation. Adjust via Dashboard > Auth > Rate Limits if needed.

3. **Failed signup attempts count toward rate limits.** Even if the email is not sent (e.g., validation error), it may still count against Supabase's internal rate limiter.

4. **Resend free tier: 100 emails/day, 3,000/month, 1 domain.** More than enough for Rhodesli's family use case, but be aware if running many test signups.

5. **Port 465 vs 587.** Port 465 uses implicit SSL; port 587 uses STARTTLS. Both work with Resend. Supabase docs typically show 587, but either is fine.

6. **DNS records must NOT be Cloudflare-proxied.** Email DNS records (MX, SPF TXT, DKIM TXT) must be set to "DNS only" (grey cloud) in Cloudflare. Proxying email records will break verification and delivery.

### Resend Free Tier Limits

| Limit | Value |
|-------|-------|
| Emails per day | 100 |
| Emails per month | 3,000 |
| Domains | 1 |
| API keys | Unlimited |
| Logs retention | 1 day |
| Suppression list | Yes |
| Custom tracking domain | No (Pro only) |

---

## Alternative Providers

If Resend does not work out, here are alternatives:

### Amazon SES (Best for Cost at Scale)

- **Free tier**: 62,000 emails/month if sending from EC2 (otherwise $0.10 per 1,000 emails)
- **Setup**: More complex (requires AWS account, IAM setup, domain verification)
- **SMTP credentials**: Generated via AWS console
- **Best for**: High volume or if you already have AWS infrastructure

### Postmark

- **Free tier**: 100 emails/month (developer sandbox)
- **Pricing**: $15/month for 10,000 emails
- **Reputation**: Excellent deliverability, strict anti-spam policies
- **Best for**: If deliverability is critical and you want a premium service

### Brevo (formerly Sendinblue)

- **Free tier**: 300 emails/day
- **Setup**: Easy, similar to Resend
- **SMTP credentials**: Available in dashboard
- **Best for**: If you need more daily emails than Resend's 100/day free limit

### MailerSend

- **Free tier**: 500 emails/month (3,000 if you verify a domain)
- **Setup**: Easy, modern API
- **SMTP credentials**: Available
- **Best for**: Alternative to Resend with similar developer experience

### Why Not These?

- **SendGrid**: Removed free tier entirely in 2025. Not recommended.
- **Mailgun**: Free tier only lasts first month, then requires paid plan. Not cost-effective for low volume.
- **Gmail SMTP**: Works but has strict rate limits (500/day), may trigger spam filters for transactional email, and Google may disable the app password at any time.

---

## References

- [Resend: Send emails with Supabase SMTP](https://resend.com/docs/send-with-supabase-smtp)
- [Resend: Configure Supabase to send from your domain](https://resend.com/blog/how-to-configure-supabase-to-send-emails-from-your-domain)
- [Supabase: Custom SMTP docs](https://supabase.com/docs/guides/auth/auth-smtp)
- [Supabase: Rate limits](https://supabase.com/docs/guides/auth/rate-limits)
- [Supabase: Management API reference](https://supabase.com/docs/reference/api/introduction)
- [Resend: Domain verification](https://resend.com/docs/dashboard/domains/introduction)
- [Resend: Pricing](https://resend.com/pricing)
- [Resend: Account quotas and limits](https://resend.com/docs/knowledge-base/account-quotas-and-limits)

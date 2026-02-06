# Email Template Design Guide

All transactional emails must match the Rhodesli app design (dark theme).

**Important**: Email clients (Gmail, Outlook, Apple Mail) strip `<style>` blocks.
All button styling MUST use inline `style=` attributes on the `<a>` element.

## Color Palette

| Element | Color | Hex |
|---------|-------|-----|
| Background | Dark gray | #111827 |
| Card | Gray | #1f2937 |
| Text | Light gray | #f3f4f6 |
| Muted text | Gray | #9ca3af |
| Primary button | Blue | #2563eb |
| Success | Green | #059669 |
| Error | Red | #dc2626 |

## Typography

- Font stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- Headings: White (#ffffff), bold
- Body: Light gray (#9ca3af)

## Sender Name

Configured via Supabase Management API: `MAILER_SECURE_EMAIL_CHANGE_ENABLED` field.
Sender name: **Rhodesli** (set via `mailer_secure_email_change_enabled` or dashboard).

## Template Locations

Configured in **Supabase Dashboard → Authentication → Email Templates**
or via **Supabase Management API** `PATCH /v1/projects/{ref}/config/auth`.

## Templates

### Confirm Signup (Welcome Email)

**Subject**: `Welcome to Rhodesli!`

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #111827; color: #f3f4f6; margin: 0; padding: 20px; }
    .container { max-width: 500px; margin: 0 auto; background-color: #1f2937; border-radius: 12px; padding: 32px; }
    h1 { color: #ffffff; margin-bottom: 16px; }
    p { color: #9ca3af; line-height: 1.6; }
    .footer { margin-top: 32px; font-size: 12px; color: #6b7280; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Welcome to Rhodesli!</h1>
    <p>Thanks for joining the family photo archive. You can now browse photos, help identify family members, and upload your own photos.</p>
    <a href="{{ .SiteURL }}" class="button" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin: 20px 0;">Open Rhodesli</a>
    <div class="footer">
      <p>This email was sent to {{ .Email }}</p>
    </div>
  </div>
</body>
</html>
```

### Password Reset

**Subject**: `Reset your Rhodesli password`

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #111827; color: #f3f4f6; margin: 0; padding: 20px; }
    .container { max-width: 500px; margin: 0 auto; background-color: #1f2937; border-radius: 12px; padding: 32px; }
    h1 { color: #ffffff; margin-bottom: 16px; }
    p { color: #9ca3af; line-height: 1.6; }
    .footer { margin-top: 32px; font-size: 12px; color: #6b7280; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Reset Your Password</h1>
    <p>Someone requested a password reset for your Rhodesli account. If this was you, click the button below:</p>
    <a href="{{ .ConfirmationURL }}" class="button" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin: 20px 0;">Reset Password</a>
    <p style="font-size: 14px;">This link expires in 24 hours.</p>
    <div class="footer">
      <p>If you didn't request this, you can safely ignore this email.</p>
    </div>
  </div>
</body>
</html>
```

### Magic Link

**Subject**: `Your Rhodesli login link`

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #111827; color: #f3f4f6; margin: 0; padding: 20px; }
    .container { max-width: 500px; margin: 0 auto; background-color: #1f2937; border-radius: 12px; padding: 32px; }
    h1 { color: #ffffff; margin-bottom: 16px; }
    p { color: #9ca3af; line-height: 1.6; }
    .footer { margin-top: 32px; font-size: 12px; color: #6b7280; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Your Login Link</h1>
    <p>Click the button below to sign in to Rhodesli:</p>
    <a href="{{ .ConfirmationURL }}" class="button" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin: 20px 0;">Sign In</a>
    <p style="font-size: 14px;">This link expires in 24 hours.</p>
    <div class="footer">
      <p>If you didn't request this, you can safely ignore this email.</p>
    </div>
  </div>
</body>
</html>
```

### Invite

**Subject**: `You're invited to Rhodesli!`

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #111827; color: #f3f4f6; margin: 0; padding: 20px; }
    .container { max-width: 500px; margin: 0 auto; background-color: #1f2937; border-radius: 12px; padding: 32px; }
    h1 { color: #ffffff; margin-bottom: 16px; }
    p { color: #9ca3af; line-height: 1.6; }
    .footer { margin-top: 32px; font-size: 12px; color: #6b7280; }
  </style>
</head>
<body>
  <div class="container">
    <h1>You're Invited!</h1>
    <p>You've been invited to join Rhodesli, a family photo archive. Click below to accept your invitation:</p>
    <a href="{{ .ConfirmationURL }}" class="button" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin: 20px 0;">Accept Invitation</a>
    <div class="footer">
      <p>If you didn't expect this invitation, you can safely ignore this email.</p>
    </div>
  </div>
</body>
</html>
```

## Supabase Management API Commands

To update templates, use the Supabase Management API:

```bash
# Set your token
export SUPABASE_ACCESS_TOKEN="your-token-here"
PROJECT_REF="fvynibivlphxwfowzkjl"

# Update sender name and all templates
curl -X PATCH "https://api.supabase.com/v1/projects/${PROJECT_REF}/config/auth" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mailer_subjects_confirmation": "Welcome to Rhodesli!",
    "mailer_subjects_recovery": "Reset your Rhodesli password",
    "mailer_subjects_magic_link": "Your Rhodesli login link",
    "mailer_subjects_invite": "You are invited to Rhodesli!",
    "mailer_templates_confirmation_content": "<html>...template...</html>",
    "mailer_templates_recovery_content": "<html>...template...</html>",
    "mailer_templates_magic_link_content": "<html>...template...</html>",
    "mailer_templates_invite_content": "<html>...template...</html>"
  }'
```

## When to Update

Update email templates when:
- App color scheme changes
- Logo or branding changes
- New transactional email type needed
- Copy/messaging updates

**Key rule**: Always use inline `style=` on `<a>` buttons. Email clients strip `<style>` blocks.

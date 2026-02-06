# Email Template Design Guide

All transactional emails must match the Rhodesli app design (dark theme).

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

## Template Locations

Configured in **Supabase Dashboard → Authentication → Email Templates**.

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
    .button { display: inline-block; background-color: #2563eb; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin: 20px 0; }
    .footer { margin-top: 32px; font-size: 12px; color: #6b7280; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Welcome to Rhodesli!</h1>
    <p>Thanks for joining the family photo archive. You can now browse photos, help identify family members, and upload your own photos.</p>
    <a href="{{ .SiteURL }}" class="button">Open Rhodesli</a>
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
    .button { display: inline-block; background-color: #2563eb; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin: 20px 0; }
    .footer { margin-top: 32px; font-size: 12px; color: #6b7280; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Reset Your Password</h1>
    <p>Someone requested a password reset for your Rhodesli account. If this was you, click the button below:</p>
    <a href="{{ .ConfirmationURL }}" class="button">Reset Password</a>
    <p style="font-size: 14px;">This link expires in 24 hours.</p>
    <div class="footer">
      <p>If you didn't request this, you can safely ignore this email.</p>
    </div>
  </div>
</body>
</html>
```

## When to Update

Update email templates when:
- App color scheme changes
- Logo or branding changes
- New transactional email type needed
- Copy/messaging updates

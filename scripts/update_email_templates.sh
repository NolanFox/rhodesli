#!/bin/bash
# Update Supabase email templates with inline-styled buttons and sender name.
# Usage: SUPABASE_ACCESS_TOKEN=your-token ./scripts/update_email_templates.sh

set -euo pipefail

if [ -z "${SUPABASE_ACCESS_TOKEN:-}" ]; then
    echo "ERROR: Set SUPABASE_ACCESS_TOKEN environment variable first."
    echo "Get it from: Supabase Dashboard → Account → Access Tokens"
    exit 1
fi

PROJECT_REF="fvynibivlphxwfowzkjl"
API_URL="https://api.supabase.com/v1/projects/${PROJECT_REF}/config/auth"

# Templates with inline button styles (email clients strip <style> blocks)
BUTTON_STYLE='display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin: 20px 0;'
BASE_STYLE='<style>body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; background-color: #111827; color: #f3f4f6; margin: 0; padding: 20px; } .container { max-width: 500px; margin: 0 auto; background-color: #1f2937; border-radius: 12px; padding: 32px; } h1 { color: #ffffff; margin-bottom: 16px; } p { color: #9ca3af; line-height: 1.6; } .footer { margin-top: 32px; font-size: 12px; color: #6b7280; }</style>'

CONFIRMATION_TEMPLATE="<!DOCTYPE html><html><head>${BASE_STYLE}</head><body><div class=\"container\"><h1>Welcome to Rhodesli!</h1><p>Thanks for joining the family photo archive. You can now browse photos, help identify family members, and upload your own photos.</p><a href=\"{{ .SiteURL }}\" class=\"button\" style=\"${BUTTON_STYLE}\">Open Rhodesli</a><div class=\"footer\"><p>This email was sent to {{ .Email }}</p></div></div></body></html>"

RECOVERY_TEMPLATE="<!DOCTYPE html><html><head>${BASE_STYLE}</head><body><div class=\"container\"><h1>Reset Your Password</h1><p>Someone requested a password reset for your Rhodesli account. If this was you, click the button below:</p><a href=\"{{ .ConfirmationURL }}\" class=\"button\" style=\"${BUTTON_STYLE}\">Reset Password</a><p style=\"font-size: 14px;\">This link expires in 24 hours.</p><div class=\"footer\"><p>If you didn't request this, you can safely ignore this email.</p></div></div></body></html>"

MAGIC_LINK_TEMPLATE="<!DOCTYPE html><html><head>${BASE_STYLE}</head><body><div class=\"container\"><h1>Your Login Link</h1><p>Click the button below to sign in to Rhodesli:</p><a href=\"{{ .ConfirmationURL }}\" class=\"button\" style=\"${BUTTON_STYLE}\">Sign In</a><p style=\"font-size: 14px;\">This link expires in 24 hours.</p><div class=\"footer\"><p>If you didn't request this, you can safely ignore this email.</p></div></div></body></html>"

INVITE_TEMPLATE="<!DOCTYPE html><html><head>${BASE_STYLE}</head><body><div class=\"container\"><h1>You're Invited!</h1><p>You've been invited to join Rhodesli, a family photo archive. Click below to accept your invitation:</p><a href=\"{{ .ConfirmationURL }}\" class=\"button\" style=\"${BUTTON_STYLE}\">Accept Invitation</a><div class=\"footer\"><p>If you didn't expect this invitation, you can safely ignore this email.</p></div></div></body></html>"

echo "Updating Supabase email templates..."

# Use python to build valid JSON (avoids shell quoting issues)
python3 -c "
import json, sys

data = {
    'mailer_subjects_confirmation': 'Welcome to Rhodesli!',
    'mailer_subjects_recovery': 'Reset your Rhodesli password',
    'mailer_subjects_magic_link': 'Your Rhodesli login link',
    'mailer_subjects_invite': \"You're invited to Rhodesli!\",
    'mailer_templates_confirmation_content': '''${CONFIRMATION_TEMPLATE}''',
    'mailer_templates_recovery_content': '''${RECOVERY_TEMPLATE}''',
    'mailer_templates_magic_link_content': '''${MAGIC_LINK_TEMPLATE}''',
    'mailer_templates_invite_content': '''${INVITE_TEMPLATE}''',
}
json.dump(data, sys.stdout)
" | curl -s -X PATCH "${API_URL}" \
    -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d @- | python3 -m json.tool

echo ""
echo "Done! Templates updated with inline button styles."
echo "Test by triggering a password reset email."

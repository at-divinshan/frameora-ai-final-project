"""Shared verification email content for both delivery adapters."""
from html import escape

SUBJECT = "Verify your Frameora AI email"

def content(link):
    text = ('Welcome to Frameora AI!\n\nConfirm your email address:\n' + link +
                                '\n\nThis link expires in 30 minutes and can be used once. Verification does not sign you in.\nIf you did not request this account, ignore this email.')
    html = ('<html><body><h1>Frameora AI</h1><h2>Confirm your email</h2>'
                '<p>Welcome! Verify your email address to finish setting up your account.</p>'
                f'<p><a href="{escape(link, quote=True)}">Verify email address</a></p>'
                '<p>This link expires in 30 minutes and can be used once. You will then sign in normally.</p>'
                '<p>If you did not request this account, ignore this email.</p></body></html>')
    return text, html

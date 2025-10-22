# Pan-Finder Frontend

This directory contains the frontend code for the Pan-Finder application, built
with React. It provides the user interface for searching.

## Envrionment Variables

The frontend application uses the following environment variables for
configuration:

- `REACT_APP_ENABLE_TURNSTILE`: Set to `true` to enable Cloudflare Turnstile
  verification. When disabled, users can search without human verification or
  session management. Important: Ensure that the backend is also configured to
  handle requests without Turnstile verification when this is disabled.
- `REACT_APP_TURNSTILE_SITE_KEY`: The site key for Cloudflare Turnstile.

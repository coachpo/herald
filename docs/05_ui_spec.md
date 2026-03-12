# UI Guide

## Stack

- React 19
- React Router SPA
- Vite
- Tailwind CSS v4
- shadcn/ui-style components under `src/components/ui/`

## Persistence And Client State

- Refresh token: `sessionStorage`
- Access token: React state only
- Theme: `localStorage` key `herald_theme`
- API base URL: `VITE_API_URL`

## Route Surface

### Public auth routes

- `/login`
- `/signup`
- `/forgot-password`
- `/reset-password`
- `/verify-email`

### Auth-gated dashboard routes

- `/`
- `/messages`
- `/messages/:id`
- `/channels`
- `/rules`
- `/ingest-endpoints`
- `/account`

## Layout Behavior

- `AuthLayout` wraps auth pages with `AuthProvider`
- `DashboardLayout` wraps dashboard pages with `AuthProvider`, `AuthGate`, and `AppShell`
- `AuthGate` refreshes immediately on mount and redirects unauthenticated users to `/login?next=...`

## Implemented Pages

### Dashboard home

- Quick action cards for endpoints, channels, and rules
- Recent messages table
- Recent failures list
- Getting-started checklist
- Verification warning banner when user email is unverified

### Messages

- Filter controls for search, endpoint, group, priority range, tag, and time range
- Batch delete form for messages older than N days
- Message table with priority badges, tags, group, and delivery summaries

### Message detail

- Displays title, body, priority, tags, group, URL, content type, remote IP, user agent
- JSON views for extras, headers, and query params
- Delivery history list with status badges and provider response data
- Wrap/no-wrap toggle for body view

### Ingest endpoints

- Create endpoint by name
- Show ingest key once at creation time
- Copy ingest URL and curl example
- Revoke and archive actions

### Channels

- Create/edit/delete UI for Bark, ntfy, and MQTT channels
- Type-specific form fields
- Send-test panel per channel with optional title/body

### Rules

- Create UI for rule filters and payload template JSON
- Rule test panel that previews matched rules and rendered payloads
- Rule list with delete action

Current UI gap: backend supports reading/updating rules, but the shipped frontend only exposes create, list, test, and delete flows.

### Account

- Show email and verification state
- Resend verification email action
- Change email form
- Change password form
- Delete account form with password confirmation

## Guardrails

- Create/update/delete flows are blocked in the UI for unverified users
- Regex input is validated client-side in the rules page
- JSON text areas show inline validation errors
- User-entered message content is rendered as text, not HTML

## Current Form Pattern

- Plain `useState` plus manual validation
- No active `react-hook-form` or `zod` usage in shipped pages

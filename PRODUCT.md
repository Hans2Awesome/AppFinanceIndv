# Product

## What it is

Personal finance tracker for Indonesian users. One FastAPI + SQLite backend,
three clients: Expo mobile app, Telegram bot, REST API. This document covers the
mobile app only.

## Who uses it

One person tracking their own money: daily spending, income, investments, and
money lent to or borrowed from people they know. Indonesian language, rupiah,
`Asia/Jakarta` default. Used in short sessions on a phone, often one-handed,
sometimes in a hurry at a checkout counter or after a transfer.

## Core jobs

1. Record a transaction in seconds (quick text input or the manual form).
2. See where the money stands today, this week, this month.
3. Track debts and receivables per person, including installments.
4. Review history so the numbers can be trusted.

## Non-negotiables

- Amounts are the most important data on every screen. They must be readable at
  a glance and never ambiguous about sign or type.
- The app must work on a mid-range Android phone in Expo Go, offline-tolerant
  (shows a clear error and a retry, never a blank screen).
- No fabricated data, no fake charts, no decorative metrics.
- Copy stays in Indonesian, plain and direct.

## Surfaces

`(auth)` login/register · `(tabs)` home, add, reports, settings · `debts` +
debt detail sheet · transaction/debt creation sheets.
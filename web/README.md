# VoiceSaju Web

Next.js 15 (App Router, RSC) frontend for VoiceSaju.

## Stack

- Next.js 15 (App Router, TypeScript strict)
- Tailwind CSS 3
- shadcn/ui (`cn` helper available at `@/lib/utils`)
- Vitest + React Testing Library
- ESLint + Prettier

## Setup

```bash
pnpm install
pnpm dev          # http://localhost:3000
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

## Layout

- `src/app/` — App Router routes (RSC by default)
- `src/components/` — Reusable components (`components/ui` reserved for shadcn primitives)
- `src/lib/` — Utilities (`cn` helper)
- `src/__tests__/` — Component / page tests

# Navigator frontend

A Next.js (App Router) chat UI for the NRCS Conservation Program Navigator. An
advisor describes a client's operation; the app threads the conversation to the
FastAPI backend (`nrcs_navigator.serving.app`) and renders the agent's reply.

## Stack

- Next.js 15 + React 19
- Tailwind CSS v4 (CSS first config in `app/globals.css`)
- Geist + Geist Mono (`geist` package)
- Framer Motion for message and state transitions
- Phosphor icons, react-markdown for the agent's formatted replies

## Local development

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Run the backend separately (`poetry run uvicorn nrcs_navigator.serving.app:app --reload`).
The session id is generated client side and stored in `localStorage`, so a page
refresh continues the same conversation thread on the backend.

## Deploy (Vercel)

- Import this `frontend/` directory as the project root.
- Set `NEXT_PUBLIC_API_URL` to the deployed backend URL.
- Add the Vercel domain to the backend `FRONTEND_ORIGINS` env var so CORS allows it.

## Layout

```
app/
  layout.tsx        Fonts, metadata, global styles
  page.tsx          Static server shell -> <Chat/>
  globals.css       Tailwind import + theme tokens
components/
  Chat.tsx          Client root: session, send/retry, layout
  Rail.tsx          Reference rail (wordmark, programs legend)
  Message.tsx       User / assistant / error bubbles
  Composer.tsx      Auto-growing input
  EmptyState.tsx    Welcome + example prompts
  TypingIndicator.tsx
lib/
  api.ts            sendChat() wrapper
  programs.ts       Program legend + example prompts
  types.ts
```

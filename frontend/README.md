# Seulgy Frontend

React + Vite frontend for Seulgy AI Analyst.

## Design System

Before adding or merging another UI, read [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md).

Key files:

- [src/theme.js](./src/theme.js): shared color and typography tokens for app/DB surfaces.
- [src/components/micro](./src/components/micro): reusable badges, tags, progress, spinner, and small UI atoms.
- [src/components/PipelineScreen.jsx](./src/components/PipelineScreen.jsx): pipeline-specific glass UI tokens and helpers.
- [src/components/Wordmark.jsx](./src/components/Wordmark.jsx): Seulgy brand wordmark (Cabinet Grotesk). Use instead of an image logo.
- [public/favicon.svg](./public/favicon.svg): Seulgy "S" favicon (Cabinet Grotesk). `public/logo-mark.png` is the retired legacy tree mark.

## Development

```bash
npm install
npm run dev
```

Targeted lint for changed files:

```bash
npm.cmd exec eslint -- src/pages/LandingPage.jsx src/pages/DbPage.jsx
```

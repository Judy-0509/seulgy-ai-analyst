# Canopy Frontend

React + Vite frontend for Research Helper.

## Design System

Before adding or merging another UI, read [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md).

Key files:

- [src/theme.js](./src/theme.js): shared color and typography tokens for app/DB surfaces.
- [src/components/micro](./src/components/micro): reusable badges, tags, progress, spinner, and small UI atoms.
- [src/components/PipelineScreen.jsx](./src/components/PipelineScreen.jsx): pipeline-specific glass UI tokens and helpers.
- [public/logo-mark.png](./public/logo-mark.png): Canopy brand mark and favicon source.

## Development

```bash
npm install
npm run dev
```

Targeted lint for changed files:

```bash
npm.cmd exec eslint -- src/pages/LandingPage.jsx src/pages/DbPage.jsx
```

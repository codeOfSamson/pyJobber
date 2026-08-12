# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR.

## Environment setup

Copy `.env.example` to `.env` (`cp .env.example .env`) before running `npm run dev`. `.env` is gitignored — each developer keeps their own local copy.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Linting

`npm run lint` runs `tsc --noEmit` for type checking. (Oxlint was removed from this scaffold — its native binding install fails in this npm environment.)

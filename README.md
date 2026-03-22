# sysctl-list

Static sysctl explorer built from Linux kernel documentation and source metadata.

## Layout

- `tools/extract/`: Python extraction and indexing pipeline.
- `data/generated/`: generated static JSON assets consumed by the site.
- `site/`: Astro static frontend.

## Commands

```bash
npm install --prefix site
npm run sample
npm run build
```

Sample data uses a small tag set for local development. Full extraction:

```bash
npm run extract:sync
npm run extract:all
```

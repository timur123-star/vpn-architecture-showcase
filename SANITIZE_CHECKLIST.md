# Pre-push

```bash
py -3 scripts/sanitize-showcase-final.py
```

Must print: `OK: showcase fully anonymized`

## Publish only this folder

- No parent repo (`.ssh/`, live recon, `run-fr-from-ru.sh` with secrets)
- README: [EN](./README.md) · [RU](./README.ru.md) · [ES](./README.es.md) · [FR](./README.fr.md)
- License: [LICENSE](./LICENSE) (all rights reserved)

## Manual spot-check

```bash
# From repo root — should return no matches in showcase/
rg "193\.168|195\.35|10\.66\.|example|i3enp7gh" vpn-architecture-showcase/
```

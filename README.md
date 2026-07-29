# Feux de forêt en Europe — carte live

Widget SvelteKit qui superpose deux couches satellite sur un fond MapLibre *Positron* :

- **Surfaces brûlées** — polygones Copernicus EMS / EFFIS depuis le 1<sup>er</sup> juillet 2026, dessinés en shapes ;
- **Feux actifs** — détections NASA FIRMS des 48 dernières heures, rendues en heatmap pondérée par la puissance radiative (FRP).

Le widget est conçu pour être embarqué en iframe via **pym.js** (redimensionnement automatique côté parent).

## Démarrage

```bash
npm install
npm run data      # rafraîchit static/data/ (EFFIS + FIRMS)
npm run dev
```

- `http://localhost:5173/` — le widget ;
- `http://localhost:5173/embed.html` — page de test d'intégration iframe + pym.

## Données

Tout passe par `scripts/fetch_fires.py`, qui écrit dans `static/data/` :

| Fichier | Contenu |
|---|---|
| `burned.geojson` | Polygones EFFIS simplifiés (`ha`, `date`, `country`, `place`, `rank`) |
| `active.geojson` | Points FIRMS des dernières 48 h (`frp`, `hours`, `at`) |
| `meta.json` | Bornes temporelles, totaux, classement par pays, dix plus grands incendies |

```bash
npm run data                                   # tout
npm run data:active                            # seulement les feux actifs (rapide)
python3 scripts/fetch_fires.py --hours 24      # fenêtre feux actifs
python3 scripts/fetch_fires.py --since 2026-06-01 --min-ha 5
```

**Sources.** EFFIS est interrogé en WFS 1.1.0 sur la couche `ms:modis.ba.poly` (MODIS 250 m pour les grands
incendies, Sentinel-2 20 m en dessous). FIRMS demande une clé : elle est lue dans `scripts/.env`
(`FIRMS_MAP_KEY=…`, non versionné) ou dans l'environnement.

**Fraîcheur.** EFFIS révise les périmètres pendant plusieurs jours après un incendie, presque toujours à la
hausse : les dernières dates sont provisoires. La date de fin affichée est la plus récente réellement présente
dans les données, pas la date du jour.

## Design system

Les couleurs, la typo et les composants suivent
`/Users/ambroisecarton/Documents/svelte_red_devils/DESIGN_SYSTEM.md`. Tous les tokens sont dans `src/app.css`,
avec un thème clair et un thème sombre automatiques (`prefers-color-scheme`) :

- le fond de carte bascule entre **Positron** (clair) et **Dark Matter** (sombre), sa déclinaison foncée ;
- les couleurs des couches MapLibre sont lues à l'exécution depuis les tokens CSS (`src/lib/theme.ts`), donc un
  changement de thème système reconstruit le style sans rechargement.

## Intégration (pym.js)

Loader officiel, à coller dans l'article :

```html
<div data-pym-src="https://votre-domaine/carte-feux/" data-pym-id="carte-feux"></div>
<script src="https://pym.nprapps.org/pym-loader.v1.js"></script>
```

Le widget est le `pym.Child` (`src/lib/pym.ts`) : il annonce sa hauteur au montage, à chaque changement d'état,
et par polling toutes les 500 ms. `static/pym.v1.min.js` est une copie locale du *Parent*, utilisée uniquement
par la page de test `embed.html`.

## Build

```bash
npm run build     # adapter-static → build/
BASE_PATH=/carte-feux npm run build   # si servi dans un sous-répertoire
npm run preview
```

`ssr = false` + `prerender = true` : le rendu est entièrement client (MapLibre et pym ont besoin du navigateur).

Note MapLibre 6 : le worker est chargé via une URL construite dynamiquement, que ni Vite ni Rolldown ne savent
détecter — la carte reste alors vide (404 sur `maplibre-gl-worker.mjs`). `src/lib/FireMap.svelte` force donc
`maplibregl.config.WORKER_URL` à partir d'un import `?worker&url`, ce qui fait émettre l'asset correctement en
dev comme en build.

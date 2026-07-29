<script lang="ts">
	import { onMount } from 'svelte';
	import * as maplibregl from 'maplibre-gl';
	import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { geoBounds } from 'd3-geo';
	import { cssColor, cssRgb, onThemeChange, prefersLight } from './theme';
	import type { Burned, Meta } from './data';
	import { country, fmt, loadActiveDay, longDate } from './data';
	import { loadGrid, paint, quad, STOPS } from './smoke';

	type Props = {
		meta: Meta;
		burned: Burned;
		activeDates: string[];
		smokeDates: string[];
		showBurned: boolean;
		showActive: boolean;
		showSmoke: boolean;
		day: number;
	};

	let { meta, burned, activeDates, smokeDates, showBurned, showActive, showSmoke, day }: Props = $props();

	const BLANK =
		'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
	const LIMIT: [[number, number], [number, number]] = [
		[-51.081, 32.327],
		[49.367, 65.561]
	];
	const HOME: [[number, number], [number, number], [number, number], [number, number]] = [
		[-12, 62],
		[34, 62],
		[34, 34],
		[-12, 34]
	];

	maplibregl.config.WORKER_URL = workerUrl;

	const POSITRON = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
	const POSITRON_DARK = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

	let container: HTMLDivElement;
	let map: maplibregl.Map | undefined;
	let popup: maplibregl.Popup | undefined;
	let ready = $state(false);

	const home = $derived(meta.bounds);

	function styleUrl() {
		return prefersLight() ? POSITRON : POSITRON_DARK;
	}

	function firstSymbolLayer(m: maplibregl.Map): string | undefined {
		return m.getStyle().layers?.find((l) => l.type === 'symbol')?.id;
	}

	function dayFilter(): maplibregl.FilterSpecification {
		return ['<=', ['get', 'day'], day];
	}

	let painted = '';
	let loaded = '';

	async function drawActive(m: maplibregl.Map) {
		const source = m.getSource('active') as maplibregl.GeoJSONSource | undefined;
		const stamp = activeDates[day];
		if (!source || !stamp || stamp === loaded) return;
		const points = await loadActiveDay(stamp);
		if (activeDates[day] !== stamp) return;
		source.setData(points);
		loaded = stamp;
	}

	async function drawSmoke(m: maplibregl.Map) {
		const source = m.getSource('smoke') as maplibregl.ImageSource | undefined;
		const stamp = smokeDates[day];
		if (!source) return;
		if (!stamp) {
			source.updateImage({ url: BLANK, coordinates: HOME });
			painted = '';
			return;
		}
		const token = `${stamp}|${prefersLight()}`;
		if (token === painted) return;
		const grid = await loadGrid(stamp);
		if (!grid || smokeDates[day] !== stamp) return;
		const colors = STOPS.map(([, name]) => cssRgb(name, [128, 128, 128]));
		source.updateImage({ url: paint(grid, colors).toDataURL(), coordinates: quad(grid.bounds) });
		painted = token;
	}

	function frenchLabels(m: maplibregl.Map) {
		for (const layer of m.getStyle().layers ?? []) {
			if (layer.type !== 'symbol') continue;
			const field = m.getLayoutProperty(layer.id, 'text-field');
			if (field === undefined) continue;
			m.setLayoutProperty(layer.id, 'text-field', [
				'coalesce',
				['get', 'name:fr'],
				['get', 'name_fr'],
				['get', 'name:latin'],
				['get', 'name']
			]);
		}
	}

	function addSmoke(m: maplibregl.Map, before: string | undefined) {
		if (!smokeDates.length || m.getSource('smoke')) return;
		const anchor = m.getLayer('active-heat') ? 'active-heat' : before;
		m.addSource('smoke', { type: 'image', url: BLANK, coordinates: HOME });
		m.addLayer(
			{
				id: 'smoke-raster',
				type: 'raster',
				source: 'smoke',
				layout: { visibility: showSmoke ? 'visible' : 'none' },
				paint: {
					'raster-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.9, 7, 0.7, 11, 0.45],
					'raster-fade-duration': 0,
					'raster-resampling': 'linear'
				}
			},
			anchor
		);
		painted = '';
	}

	function addLayers(m: maplibregl.Map) {
		const before = firstSymbolLayer(m);

		addSmoke(m, before);

		m.addSource('burned', {
			type: 'geojson',
			data: burned,
			tolerance: 0,
			maxzoom: 12,
			attribution: 'Surfaces brûlées&nbsp;: Copernicus EMS / EFFIS'
		});
		m.addSource('active', {
			type: 'geojson',
			data: { type: 'FeatureCollection', features: [] },
			attribution: 'Feux actifs&nbsp;: NASA FIRMS'
		});

		m.addLayer(
			{
				id: 'active-heat',
				type: 'heatmap',
				source: 'active',
				paint: {
					'heatmap-weight': [
						'interpolate',
						['linear'],
						['get', 'frp'],
						0,
						0.08,
						30,
						0.4,
						150,
						0.8,
						400,
						1
					],
					'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 3, 0.5, 6, 1.1, 10, 2.2],
					'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 3, 5, 6, 12, 10, 30],
					'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.8, 7, 0.85, 10, 0.2],
					'heatmap-color': [
						'interpolate',
						['linear'],
						['heatmap-density'],
						0,
						cssColor('--heat-0', 'rgba(0, 0, 0, 0)'),
						0.22,
						cssColor('--heat-1'),
						0.42,
						cssColor('--heat-2'),
						0.64,
						cssColor('--heat-3'),
						0.83,
						cssColor('--heat-4'),
						1,
						cssColor('--heat-5')
					]
				}
			},
			before
		);

		m.addLayer(
			{
				id: 'burned-fill',
				type: 'fill',
				source: 'burned',
				filter: dayFilter(),
				paint: {
					'fill-color': cssColor('--burnt'),
					'fill-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.85, 8, 0.6]
				}
			},
			before
		);
		m.addLayer(
			{
				id: 'burned-line',
				type: 'line',
				source: 'burned',
				filter: dayFilter(),
				paint: {
					'line-color': cssColor('--burnt-line'),
					'line-width': ['interpolate', ['linear'], ['zoom'], 3, 1.1, 7, 0.9, 12, 1.6],
					'line-opacity': 0.85
				}
			},
			before
		);
		m.addLayer(
			{
				id: 'burned-hover',
				type: 'line',
				source: 'burned',
				filter: ['==', ['get', 'rank'], -1],
				paint: { 'line-color': cssColor('--burnt-hover'), 'line-width': 2.4 }
			},
			before
		);

		m.addLayer(
			{
				id: 'active-point',
				type: 'circle',
				source: 'active',
				minzoom: 7,
				paint: {
					'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 1.8, 12, 4.5],
					'circle-color': cssColor('--active-dot'),
					'circle-opacity': ['interpolate', ['linear'], ['zoom'], 7, 0, 9.5, 0.9],
					'circle-stroke-width': 0.5,
					'circle-stroke-color': 'rgba(0, 0, 0, 0.35)'
				}
			},
			before
		);

		applyVisibility(m);
	}

	function applyVisibility(m: maplibregl.Map) {
		const set = (id: string, on: boolean) => {
			if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
		};
		for (const id of ['burned-fill', 'burned-line', 'burned-hover']) set(id, showBurned);
		for (const id of ['active-heat', 'active-point']) set(id, showActive);
		set('smoke-raster', showSmoke);
	}

	function tooltip(props: Record<string, unknown>) {
		const ha = Number(props.ha);
		return `<div class="tip">
			<strong>${props.place}</strong>
			<span class="tip-country">${country(String(props.country))}</span>
			<span class="tip-ha">${fmt(ha)} hectares</span>
			<span class="tip-date">détecté le ${longDate(String(props.date))}</span>
		</div>`;
	}

	function wireInteraction(m: maplibregl.Map) {
		const show = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
			const feature = e.features?.[0];
			if (!feature) return;
			m.getCanvas().style.cursor = 'pointer';
			m.setFilter('burned-hover', ['==', ['get', 'rank'], feature.properties.rank]);
			popup?.setLngLat(e.lngLat).setHTML(tooltip(feature.properties)).addTo(m);
		};
		const hide = () => {
			m.getCanvas().style.cursor = '';
			if (m.getLayer('burned-hover')) m.setFilter('burned-hover', ['==', ['get', 'rank'], -1]);
			popup?.remove();
		};
		m.on('mousemove', 'burned-fill', show);
		m.on('click', 'burned-fill', show);
		m.on('mouseleave', 'burned-fill', hide);
		m.on('movestart', hide);
	}

	function collapseAttribution() {
		container
			.closest('.map-frame')
			?.querySelector('.maplibregl-ctrl-attrib')
			?.classList.remove('maplibregl-compact-show');
	}

	export function zoomTo(rank: number) {
		if (!map) return;
		const feature = burned.features.find((f) => f.properties.rank === rank);
		if (!feature) return;
		const [[west, south], [east, north]] = geoBounds(feature);
		map.fitBounds([west, south, east, north], { padding: 90, maxZoom: 11, duration: 900 });
	}

	export function reset() {
		map?.fitBounds(home, { padding: 14, duration: 700 });
	}

	$effect(() => {
		void showBurned;
		void showActive;
		void showSmoke;
		if (map && ready) applyVisibility(map);
	});

	$effect(() => {
		void day;
		void smokeDates;
		void activeDates;
		if (!map || !ready) return;
		for (const id of ['burned-fill', 'burned-line']) {
			if (map.getLayer(id)) map.setFilter(id, dayFilter());
		}
		addSmoke(map, firstSymbolLayer(map));
		drawSmoke(map);
		drawActive(map);
	});

	onMount(() => {
		map = new maplibregl.Map({
			container,
			style: styleUrl(),
			bounds: home,
			fitBoundsOptions: { padding: 14 },
			maxBounds: LIMIT,
			maxZoom: 13,
			attributionControl: false,
			canvasContextAttributes: { antialias: true }
		});

		const m = map;
		popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, maxWidth: '260px' });

		m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
		m.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left');
		m.addControl(
			new maplibregl.AttributionControl({
				compact: true,
				customAttribution: smokeDates.length ? 'Fumées&nbsp;: CAMS / Copernicus' : undefined
			}),
			'bottom-right'
		);

		m.on('style.load', () => {
			frenchLabels(m);
			addLayers(m);
			collapseAttribution();
			ready = true;
			loaded = '';
			drawSmoke(m);
			drawActive(m);
		});
		m.once('load', () => wireInteraction(m));

		const stopTheme = onThemeChange(() => m.setStyle(styleUrl()));
		const observer = new ResizeObserver(() => m.resize());
		observer.observe(container);

		return () => {
			stopTheme();
			observer.disconnect();
			popup?.remove();
			m.remove();
			map = undefined;
		};
	});
</script>

<div class="map-frame">
	<div class="map" bind:this={container}></div>

	<div class="overlay">
		<div class="legend">
			<div class="legend-row">
				<span class="swatch burnt"></span>
				<span>Surface brûlée depuis le 1<sup>er</sup> juillet</span>
			</div>
			<div class="legend-row">
				<span class="swatch heat"></span>
				<span>Densité des feux actifs ({meta.activeHours}&nbsp;dernières heures)</span>
			</div>
			{#if smokeDates.length}
				<div class="legend-smoke">
					<span class="legend-title">Fumées des feux, transportées par le vent</span>
					<span class="ramp"></span>
					<span class="scale">
						<span>0</span><span>5</span><span>12</span><span>22</span><span>35</span><span>55</span
						><span>80&nbsp;µg/m³</span>
					</span>
					<span class="legend-hint">Particules issues des feux uniquement, au niveau du sol.</span>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.map-frame {
		position: relative;
		width: 100%;
		aspect-ratio: 4 / 3;
		max-height: 680px;
		border: 1px solid var(--map-frame);
		border-radius: 14px;
		overflow: hidden;
		background: var(--surface-2);
	}

	@media (min-width: 720px) {
		.map-frame {
			aspect-ratio: 16 / 10;
		}
	}

	.map {
		position: absolute;
		inset: 0;
	}

	.overlay {
		position: absolute;
		left: 10px;
		top: 10px;
		z-index: 2;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 8px;
		max-width: min(320px, calc(100% - 76px));
	}

	.legend {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 10px 12px;
		border-radius: 10px;
		background: color-mix(in srgb, var(--surface) 88%, transparent);
		border: 1px solid var(--border);
		backdrop-filter: blur(6px);
	}

	.legend-row {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.7rem;
		font-weight: 500;
		line-height: 1.25;
		color: var(--text-secondary);
	}

	.swatch {
		flex: none;
		width: 22px;
		height: 11px;
		border-radius: 3px;
	}

	.swatch.burnt {
		background: var(--burnt);
		border: 1px solid var(--burnt-line);
	}

	.legend-smoke {
		display: flex;
		flex-direction: column;
		gap: 3px;
		margin-top: 2px;
		padding-top: 7px;
		border-top: 1px solid var(--divider);
	}

	.legend-title {
		font-size: 0.7rem;
		font-weight: 500;
		line-height: 1.25;
		color: var(--text-secondary);
	}

	.ramp {
		height: 8px;
		border-radius: 3px;
		background: linear-gradient(
			90deg,
			var(--smoke-0),
			var(--smoke-1),
			var(--smoke-2),
			var(--smoke-3),
			var(--smoke-4),
			var(--smoke-5),
			var(--smoke-6)
		);
	}

	.scale {
		display: flex;
		justify-content: space-between;
		font-size: 0.6rem;
		font-weight: 500;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}

	.legend-hint {
		font-size: 0.6rem;
		font-weight: 500;
		line-height: 1.3;
		text-wrap: pretty;
		color: var(--text-muted);
	}

	.swatch.heat {
		background: linear-gradient(90deg, var(--heat-1), var(--heat-2), var(--heat-3), var(--heat-4), var(--heat-5));
	}

	:global(.maplibregl-popup-content) {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 10px 12px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
	}

	:global(.maplibregl-popup-tip) {
		display: none;
	}

	:global(.tip) {
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-family: var(--font);
	}

	:global(.tip strong) {
		font-size: 0.82rem;
		font-weight: 700;
	}

	:global(.tip-country) {
		font-size: 0.68rem;
		color: var(--text-muted);
	}

	:global(.tip-ha) {
		margin-top: 4px;
		font-size: 0.86rem;
		font-weight: 700;
		color: var(--accent);
	}

	:global(.tip-date) {
		font-size: 0.68rem;
		color: var(--text-muted);
	}

	:global(.maplibregl-ctrl-attrib) {
		font-size: 10px;
		line-height: 1.35;
	}

	:global(.maplibregl-ctrl-attrib.maplibregl-compact-show) {
		max-width: min(calc(100% - 20px), 460px);
	}
</style>

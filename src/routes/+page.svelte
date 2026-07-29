<script lang="ts">
	import { onMount } from 'svelte';
	import FireMap from '$lib/FireMap.svelte';
	import Timeline from '$lib/Timeline.svelte';
	import { initPym, sendHeight } from '$lib/pym';
	import {
		country,
		dateRange,
		dayMonth,
		dayOffset,
		fmt,
		loadAll,
		longDate,
		type Burned,
		type Meta
	} from '$lib/data';

	initPym();

	let meta = $state<Meta | undefined>();
	let burned = $state<Burned | undefined>();
	let failure = $state('');

	let showBurned = $state(true);
	let showActive = $state(true);
	let showSmoke = $state(true);
	let selected = $state(0);
	let dayIndex = $state(0);
	let playing = $state(false);
	let mapRef = $state<{ zoomTo: (rank: number) => void; reset: () => void } | undefined>();

	onMount(async () => {
		try {
			[meta, burned] = await loadAll();
			dayIndex = meta.days - 1;
		} catch (e) {
			failure = e instanceof Error ? e.message : String(e);
		}
	});

	const dates = $derived(meta ? dateRange(meta.since, meta.days) : []);
	const smokeDates = $derived(meta?.smoke?.dates ?? []);
	const activeDates = $derived(meta?.activeDates ?? []);

	const daily = $derived.by(() => {
		const n = meta?.days ?? 0;
		const fires = new Array<number>(n).fill(0);
		const ha = new Array<number>(n).fill(0);
		for (const feature of burned?.features ?? []) {
			const d = feature.properties.day;
			if (d >= 0 && d < n) {
				fires[d] += 1;
				ha[d] += feature.properties.ha;
			}
		}
		return { fires, ha };
	});

	const shown = $derived.by(() => {
		const { fires, ha } = daily;
		if (!fires.length) return { fires: 0, ha: 0 };
		const i = Math.min(Math.max(dayIndex, 0), fires.length - 1);
		let f = 0;
		let h = 0;
		for (let k = 0; k <= i; k++) {
			f += fires[k];
			h += ha[k];
		}
		return { fires: f, ha: Math.round(h) };
	});


	const ranking = $derived((meta?.ranking ?? []).filter((r) => r.ha >= 100).slice(0, 10));
	const top = $derived((meta?.top ?? []).slice(0, 10));

	function focus(rank: number) {
		selected = selected === rank ? 0 : rank;
		if (!selected) {
			mapRef?.reset();
			return;
		}
		const fire = top.find((f) => f.rank === rank);
		if (fire && meta) {
			const d = dayOffset(fire.date, meta.since);
			if (dayIndex < d) {
				playing = false;
				dayIndex = d;
			}
		}
		mapRef?.zoomTo(rank);
	}

	$effect(() => {
		void meta;
		void showBurned;
		void showActive;
		void showSmoke;
		void smokeDates;
		void selected;
		void dayIndex;
		void failure;
		sendHeight();
	});
</script>

<div class="widget">
	<header>
		{#if meta}
			<p class="standfirst">
				Surfaces brûlées du {dayMonth(meta.since)} au {dayMonth(meta.until)}&nbsp;{meta.until.slice(0, 4)} et
				foyers actifs détectés par satellite au cours des {meta.activeHours}&nbsp;dernières heures.
			</p>
		{/if}
	</header>

	{#if failure}
		<p class="note">Les données n'ont pas pu être chargées&nbsp;: {failure}</p>
	{:else if !meta || !burned}
		<p class="loading">Chargement des données satellite…</p>
	{:else}
		<section class="stats">
			<div class="card stat">
				<span class="value">{fmt(meta.totalHa)}</span>
				<span class="label">hectares brûlés</span>
				<span class="hint">soit {fmt(Math.round(meta.totalHa / 100))} km²</span>
			</div>
			<div class="card stat">
				<span class="value">{fmt(meta.fires)}</span>
				<span class="label">incendies cartographiés</span>
				<span class="hint">en {meta.days} jours</span>
			</div>
			<div class="card stat">
				<span class="value">{fmt(meta.active)}</span>
				<span class="label">foyers actifs</span>
				<span class="hint">dernières {meta.activeHours} h</span>
			</div>
		</section>

		<div class="controls">
			<button class="chip" class:on={showBurned} onclick={() => (showBurned = !showBurned)} type="button">
				<span class="dot burnt"></span>Surfaces brûlées
			</button>
			<button class="chip" class:on={showActive} onclick={() => (showActive = !showActive)} type="button">
				<span class="dot heat"></span>Feux actifs
			</button>
			{#if smokeDates.length}
				<button class="chip" class:on={showSmoke} onclick={() => (showSmoke = !showSmoke)} type="button">
					<span class="dot smoke"></span>Fumées
				</button>
			{/if}
		</div>

		<FireMap
			bind:this={mapRef}
			{meta}
			{burned}
			{activeDates}
			{smokeDates}
			{showBurned}
			{showActive}
			{showSmoke}
			day={dayIndex}
		/>

		<Timeline {dates} bind:index={dayIndex} bind:playing fires={shown.fires} ha={shown.ha} />

		<p class="timeline-note">
			Les foyers actifs affichés sont ceux détectés par satellite le jour sélectionné&nbsp;; les surfaces brûlées,
			elles, sont cumulées depuis le {dayMonth(meta.since)}. Le compteur «&nbsp;foyers actifs&nbsp;» en haut de
			page porte, lui, sur les {meta.activeHours}&nbsp;dernières heures.
		</p>

		<section class="panels">
			<div class="panel">
				<h2>Les dix plus grands incendies</h2>
				<p class="panel-hint">Cliquez sur une ligne pour zoomer sur le périmètre brûlé.</p>
				<div class="card-outlined">
					{#each top as fire (fire.rank)}
						<button
							class="row"
							class:active={selected === fire.rank}
							onclick={() => focus(fire.rank)}
							type="button"
						>
							<span class="rank">{fire.rank}</span>
							<span class="who">
								<span class="place">{fire.place}</span>
								<span class="meta">{country(fire.country)} · {longDate(fire.date)}</span>
							</span>
							<span class="amount">
								<span class="ha">{fmt(fire.ha)}<span class="unit"> ha</span></span>
							</span>
						</button>
					{/each}
				</div>
			</div>

			<div class="panel">
				<h2>Par pays</h2>
				<p class="panel-hint">Hectares brûlés depuis le {dayMonth(meta.since)}.</p>
				<div class="card-outlined">
					{#each ranking as entry (entry.code)}
						<div class="row static">
							<span class="who">
								<span class="place">{country(entry.code)}</span>
								<span class="meta">{fmt(entry.fires)} incendies</span>
							</span>
							<span class="amount">
								<span class="ha">{fmt(entry.ha)}<span class="unit"> ha</span></span>
							</span>
						</div>
					{/each}
				</div>
			</div>
		</section>

		<footer>
			<p>
				<strong>Surfaces brûlées</strong> — Copernicus EMS / EFFIS. Chaque périmètre est cartographié par satellite
				(MODIS à 250&nbsp;m pour les grands incendies, Sentinel-2 à 20&nbsp;m en dessous). Les périmètres des
				derniers jours sont provisoires et généralement revus à la hausse.
			</p>
			<p>
				<strong>Feux actifs</strong> — NASA FIRMS, détections VIIRS (375&nbsp;m) et MODIS (1&nbsp;km) des
				{meta.activeHours}&nbsp;dernières heures. La chaleur de la carte indique la densité des foyers, pondérée par
				leur puissance radiative.
			</p>
			{#if smokeDates.length}
				<p>
					<strong>Fumées</strong> — CAMS, prévision d'ensemble européenne (Copernicus&nbsp;/ Météo-France),
					concentration au sol des particules attribuées aux feux de végétation, en µg/m³ sur une grille de
					0,1°, un champ par jour à {meta.smoke?.hour}&nbsp;h&nbsp;UTC. Le modèle isole la part issue des feux,
					distincte de la pollution urbaine et du sable saharien. Pic sur la période&nbsp;: {fmt(
						meta.smoke?.peak ?? 0
					)}&nbsp;µg/m³.
				</p>
			{/if}
			<p class="credit">
				Fond de carte CARTO Positron / OpenStreetMap · Données arrêtées au {longDate(meta.until)} · Mise à jour
				{meta.built.slice(0, 10).split('-').reverse().join('/')}
			</p>
		</footer>
	{/if}
</div>

<style>
	.widget {
		max-width: 1080px;
		margin: 0 auto;
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	:global(body.standalone) .widget {
		min-height: 100dvh;
	}

	header {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.standfirst {
		margin: 0;
		font-size: 0.88rem;
		font-weight: 500;
		line-height: 1.5;
		text-wrap: pretty;
		color: var(--text-secondary);
	}

	.timeline-note {
		margin: -8px 0 0;
		font-size: 0.7rem;
		font-weight: 500;
		line-height: 1.4;
		text-wrap: pretty;
		color: var(--text-muted);
	}

	.loading {
		margin: 0;
		padding: 40px 0;
		text-align: center;
		font-size: 0.82rem;
		color: var(--text-muted);
	}

	.note {
		font-size: 12px;
		line-height: 1.4;
		color: var(--warn-text, #b45309);
		background: var(--warn-bg, #fffbeb);
		border: 1px solid var(--warn-border, #fde68a);
		border-radius: 8px;
		padding: 7px 11px;
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 12px;
	}

	.card {
		background: var(--surface-2);
		border-radius: 18px;
		padding: 20px;
	}

	.stat {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.value {
		font-size: clamp(1.7rem, 5.5vw, 2.4rem);
		font-weight: 700;
		line-height: 1;
		color: var(--accent);
		font-variant-numeric: tabular-nums;
	}

	.label {
		margin-top: 6px;
		font-size: 0.82rem;
		font-weight: 600;
	}

	.hint {
		font-size: 0.7rem;
		font-weight: 500;
		color: var(--text-muted);
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.chip {
		min-height: 38px;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		border: 2px solid var(--accent);
		background: transparent;
		color: var(--accent);
		border-radius: 999px;
		padding: 6px 18px;
		font: 600 13px var(--font);
		cursor: pointer;
		transition: all 0.15s;
	}

	.chip:hover:not(.on) {
		background: var(--accent-soft);
	}

	.chip.on {
		background: var(--accent);
		color: var(--accent-contrast);
	}

	.dot {
		width: 12px;
		height: 12px;
		border-radius: 3px;
		flex: none;
	}

	.dot.burnt {
		background: var(--burnt);
	}

	.dot.heat {
		background: linear-gradient(135deg, var(--heat-2), var(--heat-4));
	}

	.dot.smoke {
		background: linear-gradient(135deg, var(--smoke-2), var(--smoke-4));
	}

	.panels {
		display: grid;
		grid-template-columns: 1fr;
		gap: 18px;
	}

	@media (min-width: 780px) {
		.panels {
			grid-template-columns: 1.25fr 1fr;
		}
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	h2 {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
	}

	.panel-hint {
		margin: 0 0 8px;
		font-size: 0.72rem;
		font-weight: 500;
		color: var(--text-muted);
	}

	.card-outlined {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 14px;
		overflow: hidden;
	}

	.row {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 13px 16px;
		font-size: 0.88rem;
		text-align: left;
		background: transparent;
		border: none;
		color: inherit;
		transition: background 0.15s;
	}

	.row + .row {
		border-top: 1px solid var(--divider);
	}

	button.row {
		cursor: pointer;
	}

	button.row:hover {
		background: var(--surface-hover);
	}

	.row.active {
		background: var(--accent-soft);
	}

	.rank {
		flex: none;
		width: 20px;
		font-size: 0.78rem;
		font-weight: 700;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}

	.who {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.place {
		font-size: 0.8rem;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta {
		font-size: 0.66rem;
		font-weight: 500;
		color: var(--text-muted);
	}

	.amount {
		flex: none;
		display: flex;
		align-items: baseline;
		justify-content: flex-end;
	}

	.ha {
		font-size: 0.8rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.unit {
		margin-left: 3px;
		font-size: 0.66rem;
		font-weight: 500;
		color: var(--text-muted);
	}

	footer {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding-top: 14px;
		border-top: 1px solid var(--divider);
	}

	footer p {
		margin: 0;
		font-size: 0.72rem;
		font-weight: 400;
		line-height: 1.5;
		text-wrap: pretty;
		color: var(--text-secondary);
	}

	footer strong {
		font-weight: 700;
		color: var(--text);
	}

	.credit {
		font-size: 0.64rem !important;
		color: var(--text-muted) !important;
	}
</style>

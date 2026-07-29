<script lang="ts">
	import { fmt, longDate, shortDate } from './data';

	type Props = {
		dates: string[];
		index: number;
		playing: boolean;
		fires: number;
		ha: number;
	};

	let { dates, index = $bindable(), playing = $bindable(), fires, ha }: Props = $props();

	let timer: ReturnType<typeof setInterval> | null = null;

	const last = $derived(Math.max(dates.length - 1, 0));

	function halt() {
		if (timer) clearInterval(timer);
		timer = null;
		playing = false;
	}

	function toggle() {
		if (playing) {
			halt();
			return;
		}
		if (index >= last) index = 0;
		playing = true;
		timer = setInterval(() => {
			if (index >= last) halt();
			else index += 1;
		}, 400);
	}

	$effect(() => () => {
		if (timer) clearInterval(timer);
	});
</script>

<div class="timeline">
	<div class="head">
		<button class="play" onclick={toggle} type="button" aria-label={playing ? 'Pause' : 'Lecture'}>
			<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
				{#if playing}
					<rect x="5" y="3" width="5" height="18" rx="1" />
					<rect x="14" y="3" width="5" height="18" rx="1" />
				{:else}
					<polygon points="6,3 20,12 6,21" />
				{/if}
			</svg>
		</button>

		<span class="date">{dates.length ? longDate(dates[index]) : ''}</span>
		<span class="count">
			{fmt(fires)}&nbsp;incendies déclarés · {fmt(ha)}&nbsp;ha brûlés depuis le début de la période
		</span>
	</div>

	<div class="track">
		<span class="edge">{dates.length ? shortDate(dates[0]) : ''}</span>
		<input
			class="slider"
			style:--steps={Math.max(last, 1)}
			type="range"
			min="0"
			max={last}
			step="1"
			bind:value={index}
			oninput={halt}
			aria-label="Date affichée"
		/>
		<span class="edge">{dates.length ? shortDate(dates[last]) : ''}</span>
	</div>
</div>

<style>
	.timeline {
		display: flex;
		flex-direction: column;
		gap: 10px;
		background: var(--surface-2);
		border-radius: 14px;
		padding: 14px 16px;
	}

	.head {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}

	.play {
		width: 36px;
		height: 36px;
		flex: none;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		border: 2px solid var(--chip-line);
		background: var(--chip-bg);
		color: var(--chip-text);
		cursor: pointer;
		transition: all 0.15s;
	}

	.play:hover {
		border-color: var(--accent);
		background: var(--accent);
		color: var(--accent-contrast);
	}

	.date {
		font-size: 0.95rem;
		font-weight: 700;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
		min-width: 9.5em;
	}

	.count {
		font-size: 0.72rem;
		font-weight: 500;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}

	.track {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.edge {
		font-size: 0.66rem;
		font-weight: 500;
		color: var(--text-muted);
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}

	.slider {
		flex: 1;
		min-width: 0;
		height: 10px;
		appearance: none;
		-webkit-appearance: none;
		background: none;
		outline: none;
		cursor: pointer;
	}

	.slider::-webkit-slider-runnable-track {
		height: 10px;
		border-radius: 999px;
		background:
			repeating-linear-gradient(
					90deg,
					var(--text-muted) 0 1px,
					transparent 1px calc(100% / var(--steps))
				)
				no-repeat center / calc(100% - 15px) 6px,
			linear-gradient(var(--border), var(--border)) no-repeat center / 100% 4px;
	}

	.slider::-moz-range-track {
		height: 10px;
		border-radius: 999px;
		background:
			repeating-linear-gradient(
					90deg,
					var(--text-muted) 0 1px,
					transparent 1px calc(100% / var(--steps))
				)
				no-repeat center / calc(100% - 13px) 6px,
			linear-gradient(var(--border), var(--border)) no-repeat center / 100% 4px;
	}

	.slider::-webkit-slider-thumb {
		appearance: none;
		-webkit-appearance: none;
		width: 15px;
		height: 15px;
		margin-top: -3px;
		border-radius: 50%;
		background: var(--accent);
		border: 2px solid var(--bg);
		cursor: pointer;
	}

	.slider::-moz-range-thumb {
		width: 13px;
		height: 13px;
		border-radius: 50%;
		background: var(--accent);
		border: 2px solid var(--bg);
		cursor: pointer;
	}

	.slider:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 3px;
	}

	@media (max-width: 640px) {
		.head {
			gap: 8px;
		}

		.date {
			font-size: 0.86rem;
			min-width: 0;
		}
	}
</style>

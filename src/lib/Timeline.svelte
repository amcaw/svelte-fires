<script lang="ts">
	import { parisStamp, shortDate } from './data';

	type Props = {
		steps: string[];
		stepsPerDay: number;
		index: number;
		playing: boolean;
	};

	let { steps, stepsPerDay, index = $bindable(), playing = $bindable() }: Props = $props();

	let timer: ReturnType<typeof setInterval> | null = null;

	const last = $derived(Math.max(steps.length - 1, 0));

	const ticks = $derived(
		steps.map((stamp, i) => {
			const opensDay = i % stepsPerDay === 0;
			return {
				stamp,
				day: stamp.slice(0, 10),
				at: last ? (i / last) * 100 : 0,
				major: opensDay,
				labelled: opensDay && (i / stepsPerDay) % 5 === 0
			};
		})
	);

	function label(stamp: string): string {
		return stamp ? parisStamp(stamp) : '';
	}
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
		}, 220);
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

		<span class="date">{label(steps[index])}</span>
	</div>

	<div class="track">
		<input
			class="slider"
			type="range"
			min="0"
			max={last}
			step="1"
			bind:value={index}
			oninput={halt}
			aria-label="Date affichée"
		/>
		<div class="ruler" aria-hidden="true">
			{#each ticks as tick (tick.stamp)}
				<span
					class="tick"
					class:major={tick.major}
					class:labelled={tick.labelled}
					style:left="{tick.at}%"
				>
					{#if tick.labelled}<span class="tick-label">{shortDate(tick.day)}</span>{/if}
				</span>
			{/each}
		</div>
	</div>
</div>

<style>
	.timeline {
		display: flex;
		flex-direction: column;
		gap: 8px;
		background: var(--surface-2);
		border-radius: 14px;
		padding: 14px 16px 10px;
	}

	.head {
		display: flex;
		align-items: center;
		gap: 12px;
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
	}

	.track {
		position: relative;
		padding: 0 7px 18px;
	}

	.ruler {
		position: absolute;
		left: 7px;
		right: 7px;
		top: 14px;
		height: 16px;
		pointer-events: none;
	}

	.tick {
		position: absolute;
		top: 0;
		width: 1px;
		height: 3px;
		margin-left: -0.5px;
		background: var(--divider);
	}

	.tick.major {
		height: 6px;
		background: var(--border-strong);
	}

	.tick.labelled {
		height: 8px;
		background: var(--text-muted);
	}

	.tick-label {
		position: absolute;
		top: 8px;
		left: 0;
		transform: translateX(-50%);
		font-size: 0.6rem;
		font-weight: 500;
		white-space: nowrap;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}

	.slider {
		display: block;
		width: 100%;
		height: 14px;
		appearance: none;
		-webkit-appearance: none;
		background: none;
		outline: none;
		cursor: pointer;
	}

	.slider::-webkit-slider-runnable-track {
		height: 4px;
		border-radius: 999px;
		background: var(--border);
	}

	.slider::-moz-range-track {
		height: 4px;
		border-radius: 999px;
		background: var(--border);
	}

	.slider::-webkit-slider-thumb {
		appearance: none;
		-webkit-appearance: none;
		width: 15px;
		height: 15px;
		margin-top: -5.5px;
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
		.date {
			font-size: 0.86rem;
		}
	}
</style>

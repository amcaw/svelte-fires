import { base } from '$app/paths';

export type SmokeGrid = {
	nx: number;
	ny: number;
	scale?: number;
	bounds: [number, number, number, number];
	values?: number[];
	rle?: number[];
};

function expand(grid: SmokeGrid): number[] {
	if (grid.values) return grid.values;
	const out = new Array<number>(grid.nx * grid.ny);
	const runs = grid.rle ?? [];
	let at = 0;
	for (let i = 0; i < runs.length; i += 2) {
		out.fill(runs[i], at, at + runs[i + 1]);
		at += runs[i + 1];
	}
	grid.values = out;
	return out;
}

export type Quad = [[number, number], [number, number], [number, number], [number, number]];

export const STOPS: [number, string][] = [
	[0, '--smoke-0'],
	[5, '--smoke-1'],
	[12, '--smoke-2'],
	[22, '--smoke-3'],
	[35, '--smoke-4'],
	[55, '--smoke-5'],
	[80, '--smoke-6']
];

const ALPHA: [number, number][] = [
	[0, 0],
	[3, 25],
	[10, 90],
	[20, 160],
	[35, 210],
	[55, 238],
	[80, 252]
];

const cache = new Map<string, Promise<SmokeGrid | undefined>>();

export function loadGrid(stamp: string): Promise<SmokeGrid | undefined> {
	let pending = cache.get(stamp);
	if (!pending) {
		pending = fetch(`${base}/data/smoke/${stamp}.json`)
			.then((r) => (r.ok ? (r.json() as Promise<SmokeGrid>) : undefined))
			.catch(() => undefined);
		cache.set(stamp, pending);
	}
	return pending;
}

function ramp(stops: [number, number[]][], value: number): number[] {
	if (value <= stops[0][0]) return stops[0][1];
	const last = stops[stops.length - 1];
	if (value >= last[0]) return last[1];
	for (let i = 0; i < stops.length - 1; i++) {
		const [a, from] = stops[i];
		const [b, to] = stops[i + 1];
		if (value >= a && value <= b) {
			const t = b === a ? 0 : (value - a) / (b - a);
			return from.map((c, k) => c + (to[k] - c) * t);
		}
	}
	return last[1];
}

const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
const mercLat = (y: number) => ((2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180) / Math.PI;

const LUT_STEPS = 512;
const LUT_MAX = 120;

function lookup(colors: number[][]): Uint8ClampedArray {
	const table = new Uint8ClampedArray(LUT_STEPS * 4);
	const colorStops: [number, number[]][] = STOPS.map(([v], i) => [v, colors[i]]);
	const alphaStops: [number, number[]][] = ALPHA.map(([v, a]) => [v, [a]]);
	for (let i = 0; i < LUT_STEPS; i++) {
		const value = (i / (LUT_STEPS - 1)) * LUT_MAX;
		const [r, g, b] = ramp(colorStops, value);
		table[i * 4] = r;
		table[i * 4 + 1] = g;
		table[i * 4 + 2] = b;
		table[i * 4 + 3] = ramp(alphaStops, value)[0];
	}
	return table;
}

export function paint(grid: SmokeGrid, colors: number[][], upscale = 2): HTMLCanvasElement {
	const [, south, , north] = grid.bounds;
	const width = grid.nx * upscale;
	const height = grid.ny * 2 * upscale;

	const canvas = document.createElement('canvas');
	canvas.width = width;
	canvas.height = height;
	const ctx = canvas.getContext('2d');
	if (!ctx) return canvas;

	const scale = grid.scale ?? 1;
	const values = expand(grid);
	const table = lookup(colors);
	const top = mercY(north);
	const span = mercY(south) - top;
	const image = ctx.createImageData(width, height);
	const data = image.data;
	const { nx, ny } = grid;
	const last = LUT_STEPS - 1;

	for (let j = 0; j < height; j++) {
		const lat = mercLat(top + ((j + 0.5) / height) * span);
		// position fractionnaire dans la grille source, centres de cellules
		const fy = Math.min(ny - 1, Math.max(0, ((north - lat) / (north - south)) * ny - 0.5));
		const y0 = Math.floor(fy);
		const y1 = Math.min(ny - 1, y0 + 1);
		const wy = fy - y0;

		for (let i = 0; i < width; i++) {
			const fx = Math.min(nx - 1, Math.max(0, ((i + 0.5) / upscale) - 0.5));
			const x0 = Math.floor(fx);
			const x1 = Math.min(nx - 1, x0 + 1);
			const wx = fx - x0;

			const a = values[y0 * nx + x0];
			const b = values[y0 * nx + x1];
			const c = values[y1 * nx + x0];
			const d = values[y1 * nx + x1];
			const value = (a + (b - a) * wx + (c + (d - c) * wx - (a + (b - a) * wx)) * wy) / scale;

			const o = (j * width + i) * 4;
			if (value <= 0) {
				data[o + 3] = 0;
				continue;
			}
			const k = Math.min(last, (value / LUT_MAX) * last) << 2;
			data[o] = table[k];
			data[o + 1] = table[k + 1];
			data[o + 2] = table[k + 2];
			data[o + 3] = table[k + 3];
		}
	}

	ctx.putImageData(image, 0, 0);
	return canvas;
}

export function quad(bounds: [number, number, number, number]): Quad {
	const [west, south, east, north] = bounds;
	return [
		[west, north],
		[east, north],
		[east, south],
		[west, south]
	];
}

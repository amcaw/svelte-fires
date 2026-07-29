import { base } from '$app/paths';

export type SmokeGrid = {
	nx: number;
	ny: number;
	scale?: number;
	bounds: [number, number, number, number];
	values: number[];
};

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

export function paint(grid: SmokeGrid, colors: number[][]): HTMLCanvasElement {
	const [, south, , north] = grid.bounds;
	const height = grid.ny * 2;

	const canvas = document.createElement('canvas');
	canvas.width = grid.nx;
	canvas.height = height;
	const ctx = canvas.getContext('2d');
	if (!ctx) return canvas;

	const colorStops: [number, number[]][] = STOPS.map(([v], i) => [v, colors[i]]);
	const alphaStops: [number, number[]][] = ALPHA.map(([v, a]) => [v, [a]]);

	const scale = grid.scale ?? 1;
	const top = mercY(north);
	const span = mercY(south) - top;
	const image = ctx.createImageData(grid.nx, height);

	for (let j = 0; j < height; j++) {
		const lat = mercLat(top + ((j + 0.5) / height) * span);
		const row = Math.min(grid.ny - 1, Math.max(0, Math.floor(((north - lat) / (north - south)) * grid.ny)));
		for (let i = 0; i < grid.nx; i++) {
			const value = grid.values[row * grid.nx + i] / scale;
			const o = (j * grid.nx + i) * 4;
			if (value <= 0) {
				image.data[o + 3] = 0;
				continue;
			}
			const [r, g, b] = ramp(colorStops, value);
			image.data[o] = r;
			image.data[o + 1] = g;
			image.data[o + 2] = b;
			image.data[o + 3] = ramp(alphaStops, value)[0];
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

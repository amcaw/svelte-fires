export function cssColor(name: string, fallback = '#000000'): string {
	if (typeof window === 'undefined') return fallback;
	const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
	return raw || fallback;
}

export function cssRgb(name: string, fallback: [number, number, number] = [0, 0, 0]): number[] {
	if (typeof window === 'undefined') return fallback;
	const ctx = document.createElement('canvas').getContext('2d');
	if (!ctx) return fallback;
	ctx.fillStyle = '#000';
	ctx.fillStyle = cssColor(name, '#000000');
	const hex = ctx.fillStyle.match(/^#([0-9a-f]{6})$/i);
	if (hex) {
		const n = parseInt(hex[1], 16);
		return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
	}
	const rgb = ctx.fillStyle.match(/(\d+)[,\s]+(\d+)[,\s]+(\d+)/);
	return rgb ? [+rgb[1], +rgb[2], +rgb[3]] : fallback;
}

export function prefersLight(): boolean {
	return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: light)').matches;
}

export function onThemeChange(handler: (light: boolean) => void): () => void {
	if (typeof window === 'undefined') return () => {};
	const mq = window.matchMedia('(prefers-color-scheme: light)');
	const listener = (e: MediaQueryListEvent) => handler(e.matches);
	mq.addEventListener('change', listener);
	return () => mq.removeEventListener('change', listener);
}

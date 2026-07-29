import { base } from '$app/paths';
import type { FeatureCollection, MultiPolygon, Point, Polygon } from 'geojson';

export type BurnedProps = {
	ha: number;
	date: string;
	day: number;
	country: string;
	place: string;
	rank: number;
};

export type ActiveProps = {
	frp: number;
	hours: number;
	at: string;
};

export type Burned = FeatureCollection<Polygon | MultiPolygon, BurnedProps>;
export type Active = FeatureCollection<Point, ActiveProps>;
export type SmokeMeta = {
	variable: string;
	unit: string;
	hour: number;
	dates: string[];
	peak: number;
	source: string;
};

export type TopFire = {
	rank: number;
	ha: number;
	place: string;
	country: string;
	date: string;
	at: [number, number];
};

export type Meta = {
	since: string;
	until: string;
	days: number;
	fires: number;
	totalHa: number;
	ranking: { code: string; ha: number; fires: number }[];
	top: TopFire[];
	activeHours: number;
	active: number;
	activeUntil: string;
	activeFrpMax: number;
	bounds: [[number, number], [number, number]];
	sources: { burned: string; active: string; basemap: string };
	smoke?: SmokeMeta;
	activeDates?: string[];
	activeTotal?: number;
	built: string;
};

async function json<T>(name: string): Promise<T> {
	const res = await fetch(`${base}/data/${name}`);
	if (!res.ok) throw new Error(`${name}: ${res.status} ${res.statusText}`);
	return res.json();
}

export function loadAll() {
	return Promise.all([json<Meta>('meta.json'), json<Burned>('burned.geojson')]);
}

const days = new Map<string, Promise<Active>>();

export function loadActiveDay(stamp: string): Promise<Active> {
	let pending = days.get(stamp);
	if (!pending) {
		pending = json<{ points: [number, number, number][] }>(`active/${stamp}.json`)
			.then((raw) => ({
				type: 'FeatureCollection' as const,
				features: raw.points.map(([lon, lat, frp]) => ({
					type: 'Feature' as const,
					geometry: { type: 'Point' as const, coordinates: [lon, lat] },
					properties: { frp, hours: 0, at: stamp }
				}))
			}))
			.catch(() => ({ type: 'FeatureCollection' as const, features: [] }));
		days.set(stamp, pending);
	}
	return pending;
}

export const COUNTRIES: Record<string, string> = {
	ES: 'Espagne',
	PT: 'Portugal',
	FR: 'France',
	IT: 'Italie',
	UA: 'Ukraine',
	EL: 'Grèce',
	GR: 'Grèce',
	TR: 'Turquie',
	UK: 'Royaume-Uni',
	IE: 'Irlande',
	DE: 'Allemagne',
	BG: 'Bulgarie',
	RO: 'Roumanie',
	HR: 'Croatie',
	BA: 'Bosnie-Herzégovine',
	ME: 'Monténégro',
	AL: 'Albanie',
	MK: 'Macédoine du Nord',
	RS: 'Serbie',
	SI: 'Slovénie',
	SK: 'Slovaquie',
	CZ: 'Tchéquie',
	AT: 'Autriche',
	HU: 'Hongrie',
	PL: 'Pologne',
	SE: 'Suède',
	NO: 'Norvège',
	FI: 'Finlande',
	DK: 'Danemark',
	NL: 'Pays-Bas',
	BE: 'Belgique',
	CH: 'Suisse',
	CY: 'Chypre',
	KS: 'Kosovo',
	MD: 'Moldavie',
	BY: 'Biélorussie',
	LT: 'Lituanie',
	LV: 'Lettonie',
	EE: 'Estonie',
	'??': 'Non attribué'
};

const NBSP = ' ';

export function fmt(n: number, digits = 0): string {
	return n.toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits }).replace(/ /g, NBSP);
}

export function country(code: string): string {
	return COUNTRIES[code] ?? code;
}

export function longDate(iso: string): string {
	const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
	return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
}

export function shortDate(iso: string): string {
	const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
	return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

const DAY_MS = 86400000;

export function dateRange(since: string, days: number): string[] {
	const start = Date.parse(`${since}T12:00:00Z`);
	return Array.from({ length: days }, (_, i) => new Date(start + i * DAY_MS).toISOString().slice(0, 10));
}

export function dayOffset(iso: string, since: string): number {
	return Math.round((Date.parse(`${iso.slice(0, 10)}T12:00:00Z`) - Date.parse(`${since}T12:00:00Z`)) / DAY_MS);
}

export function dayMonth(iso: string): string {
	const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
	const day = d.getUTCDate();
	const month = d.toLocaleDateString('fr-FR', { month: 'long', timeZone: 'UTC' });
	return `${day === 1 ? '1er' : day} ${month}`;
}

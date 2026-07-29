import { onMount } from 'svelte';
import pym from 'pym.js';
import type { Child } from 'pym.js';

let pymChild: Child | null = null;

export function initPym() {
	onMount(() => {
		if (typeof window === 'undefined') return;
		pymChild = new pym.Child({ polling: 500 });
		setTimeout(() => pymChild && pymChild.sendHeight(), 50);
	});
}

export function sendHeight() {
	if (pymChild) setTimeout(() => pymChild && pymChild.sendHeight(), 50);
}

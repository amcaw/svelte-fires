declare module 'pym.js' {
	export class Child {
		constructor(config?: { polling?: number; renderCallback?: () => void; id?: string });
		sendHeight(): void;
		sendMessage(type: string, message: string): void;
		remove(): void;
	}
	export class Parent {
		constructor(id: string, url: string, config?: Record<string, unknown>);
		sendMessage(type: string, message: string): void;
		remove(): void;
	}
	const pym: { Child: typeof Child; Parent: typeof Parent };
	export default pym;
}

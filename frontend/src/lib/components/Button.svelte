<script lang="ts">
	import type { HTMLButtonAttributes } from 'svelte/elements';

	type Variant = 'primary' | 'ghost' | 'danger' | 'success' | 'warning';

	let {
		variant = 'primary',
		type = 'button',
		disabled = false,
		children,
		class: className = '',
		...rest
	}: HTMLButtonAttributes & {
		variant?: Variant;
		children?: import('svelte').Snippet;
	} = $props();
</script>

<button class={`btn btn-${variant} ${className}`} {type} {disabled} {...rest}>
	{@render children?.()}
</button>

<style>
	.btn {
		appearance: none;
		border-radius: var(--radius-sm);
		font: inherit;
		font-weight: 700;
		padding: 0.55rem 1rem;
		cursor: pointer;
		border: 1px solid transparent;
		transition:
			background-color 120ms ease,
			box-shadow 120ms ease,
			border-color 120ms ease,
			filter 120ms ease;
	}

	.btn:focus-visible {
		outline: none;
		box-shadow: var(--focus-ring);
	}

	.btn:disabled {
		cursor: not-allowed;
		opacity: 0.65;
		background: #c9c4ba !important;
		border-color: #b7b1a6 !important;
		color: #5c6b63 !important;
		box-shadow: none !important;
		background-image: none !important;
	}

	.btn-primary {
		color: #fff;
		border-color: var(--color-brand-dark);
		background-image: linear-gradient(180deg, var(--color-brand-light), var(--color-brand));
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.28),
			inset 0 -1px 0 rgba(0, 0, 0, 0.18),
			var(--shadow-button);
	}

	.btn-primary:hover:not(:disabled) {
		background-image: linear-gradient(180deg, #3aa572, var(--color-brand));
	}

	.btn-primary:active:not(:disabled) {
		background-image: none;
		background-color: var(--color-brand-dark);
		transform: translateY(1px);
	}

	.btn-ghost {
		color: var(--color-ink);
		background: transparent;
		border-color: var(--color-border);
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.5),
			inset 0 -1px 0 rgba(0, 0, 0, 0.06);
	}

	.btn-ghost:active:not(:disabled) {
		transform: translateY(1px);
	}

	.btn-danger,
	.btn-success,
	.btn-warning {
		color: #1a1404;
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.28),
			inset 0 -1px 0 rgba(0, 0, 0, 0.16),
			var(--shadow-button);
	}

	.btn-danger {
		background: #f3b4ae;
		border-color: var(--color-danger);
	}

	.btn-success {
		background: #b7e0c8;
		border-color: var(--color-success);
	}

	.btn-warning {
		background: #f5d0a8;
		border-color: var(--color-warning);
	}

	.btn-danger:active:not(:disabled),
	.btn-success:active:not(:disabled),
	.btn-warning:active:not(:disabled) {
		transform: translateY(1px);
	}
</style>

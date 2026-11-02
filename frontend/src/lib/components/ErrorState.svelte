<script lang="ts">
	import Button from './Button.svelte';

	let {
		title = 'Couldn’t load this',
		description = 'Check the connection and try again.',
		onRetry
	}: {
		title?: string;
		description?: string;
		onRetry?: () => void;
	} = $props();
</script>

<div class="error-state panel" role="alert">
	<div class="copy">
		<h2>{title}</h2>
		<p class="muted" style="margin: 0">{description}</p>
	</div>
	{#if onRetry}
		<Button type="button" onclick={onRetry}>Try again</Button>
	{/if}
</div>

<style>
	.error-state {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		border-color: color-mix(in srgb, var(--color-danger) 28%, var(--color-border));
		background: linear-gradient(
			180deg,
			color-mix(in srgb, var(--color-danger-soft) 55%, white),
			var(--color-surface-raised)
		);
	}

	.copy {
		display: grid;
		gap: 6px;
		min-width: min(100%, 280px);
	}

	h2 {
		font-size: 1.25rem;
		margin: 0;
	}
</style>

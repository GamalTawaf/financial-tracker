<script lang="ts">
	import { page } from '$app/state';
	import Button from '#lib/components/Button.svelte';

	const status = $derived(page.status);
	const message = $derived(page.error?.message ?? 'Unexpected error');

	const title = $derived(
		status === 404
			? 'This page isn’t in the ledger'
			: status === 403
				? 'You can’t open this'
				: status >= 500
					? 'Something broke on our side'
					: 'Something went wrong'
	);
</script>

<section class="auth-shell">
	<div class="panel stack">
		<p
			class="muted"
			style="margin: 0; font-size: 0.8rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;"
		>
			Error {status}
		</p>
		<h1 style="font-size: clamp(1.75rem, 3vw, 2.25rem)">{title}</h1>
		<p class="page-lede">{message}</p>
		<div class="actions" style="margin-top: 8px">
			<a href="/"><Button type="button">Back home</Button></a>
			<a href="/receipts"><Button variant="ghost" type="button">Receipts</Button></a>
		</div>
	</div>
</section>

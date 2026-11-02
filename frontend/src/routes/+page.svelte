<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import Button from '#lib/components/Button.svelte';
	import { getToken } from '#lib';

	onMount(() => {
		if (getToken()) goto('/receipts');
	});
</script>

<section class="panel hero-grid">
	<div class="hero-copy">
		<h1>Every line you paid for</h1>
		<p class="page-lede">
			Photograph a receipt. Ledger reads the items, applies Ontario HST, and shows where the money
			went — store by store, snack by snack.
		</p>
		<div class="actions">
			<a href="/register"><Button type="button">Start tracking</Button></a>
			<a href="/login"><Button variant="ghost" type="button">Log in</Button></a>
		</div>
	</div>

	<aside class="hero-aside" aria-label="Example ledger lines">
		<p
			class="muted"
			style="margin-bottom: 12px; font-size: 0.8rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;"
		>
			Sample lines
		</p>
		<div class="ledger-sample">
			<div class="row"><span>Whole wheat bread</span><span>$2.99</span></div>
			<div class="row"><span>Potato chips</span><span>$3.49 + tax</span></div>
			<div class="row"><span>2% milk</span><span>$4.99</span></div>
			<div class="row"><span>Receipt total</span><span>$11.92</span></div>
		</div>
	</aside>
</section>

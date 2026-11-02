<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import ErrorState from '#lib/components/ErrorState.svelte';
	import { api, formatMoney, getToken, type CategoryTotal } from '#lib';

	let rows = $state<CategoryTotal[]>([]);
	let error = $state('');
	let loading = $state(true);

	const maxTotal = $derived(Math.max(1, ...rows.map((r) => r.total_cents)));

	async function load() {
		loading = true;
		error = '';
		try {
			if (!getToken()) {
				await goto('/login');
				return;
			}
			const data = await api.categoryStats();
			rows = data.categories;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load categories';
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<section>
	<div class="page-header">
		<div>
			<h1>Categories</h1>
			<p class="page-lede">Where the money clustered. Bars scale to your largest category.</p>
		</div>
	</div>

	{#if loading}
		<p class="muted">Loading categories…</p>
	{:else if error}
		<ErrorState description={error} onRetry={load} />
	{:else if rows.length === 0}
		<div class="panel empty">
			<h2>Nothing categorized yet</h2>
			<p class="muted">Upload a few receipts and the shape of your spend shows up here.</p>
		</div>
	{:else}
		<div class="panel">
			<div class="cat-list">
				{#each rows as row (row.category)}
					<div class="cat-row">
						<div class="cat-meta">
							<span class="cat-name">{row.category}</span>
							<span class="money">{formatMoney(row.total_cents)}</span>
						</div>
						<div class="cat-bar" aria-hidden="true">
							<div class="cat-fill" style={`width: ${(row.total_cents / maxTotal) * 100}%`}></div>
						</div>
						<p class="muted" style="margin: 0; font-size: 0.8rem">
							{row.item_count} item{row.item_count === 1 ? '' : 's'} · tax {formatMoney(
								row.tax_cents
							)}
						</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</section>

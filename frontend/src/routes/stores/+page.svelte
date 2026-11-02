<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import ErrorState from '#lib/components/ErrorState.svelte';
	import { api, getToken, type Store } from '#lib';

	let stores = $state<Store[]>([]);
	let error = $state('');
	let loading = $state(true);

	async function load() {
		loading = true;
		error = '';
		try {
			if (!getToken()) {
				await goto('/login');
				return;
			}
			stores = await api.listStores();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load stores';
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<section>
	<div class="page-header">
		<div>
			<h1>Stores</h1>
			<p class="page-lede">
				One record per name and address. Uploads reuse a match instead of duplicating.
			</p>
		</div>
	</div>

	{#if loading}
		<p class="muted">Loading stores…</p>
	{:else if error}
		<ErrorState description={error} onRetry={load} />
	{:else if stores.length === 0}
		<div class="panel empty">
			<h2>No stores yet</h2>
			<p class="muted">Upload a receipt and the merchant header becomes a store.</p>
		</div>
	{:else}
		<div class="panel">
			<div class="table-wrap">
				<table class="table">
					<thead>
						<tr>
							<th>Name</th>
							<th>Address</th>
							<th>Phone</th>
						</tr>
					</thead>
					<tbody>
						{#each stores as store (store.id)}
							<tr>
								<td>{store.name}</td>
								<td class="muted">{store.address || '—'}</td>
								<td class="muted">{store.phone || '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</section>

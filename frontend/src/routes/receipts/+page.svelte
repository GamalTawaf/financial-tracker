<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Button from '#lib/components/Button.svelte';
	import ErrorState from '#lib/components/ErrorState.svelte';
	import { api, formatMoney, getToken, type Receipt } from '#lib';

	let receipts = $state<Receipt[]>([]);
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
			receipts = await api.listReceipts();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load receipts';
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<section>
	<div class="page-header">
		<div>
			<h1>Receipts</h1>
			<p class="page-lede">Newest first. Flagged rows need a quick fix.</p>
		</div>
		<a href="/upload"><Button type="button">Upload receipt</Button></a>
	</div>

	{#if loading}
		<p class="muted">Loading receipts…</p>
	{:else if error}
		<ErrorState description={error} onRetry={load} />
	{:else if receipts.length === 0}
		<div class="panel empty">
			<h2>No receipts yet</h2>
			<p class="muted">
				Upload a photo from the store run. We’ll parse the lines and sort the tax.
			</p>
			<div class="actions">
				<a href="/upload"><Button type="button">Upload first receipt</Button></a>
			</div>
		</div>
	{:else}
		<div class="panel">
			<div class="table-wrap">
				<table class="table">
					<thead>
						<tr>
							<th>Store</th>
							<th>Date</th>
							<th class="money">Total</th>
							<th>Status</th>
						</tr>
					</thead>
					<tbody>
						{#each receipts as receipt (receipt.id)}
							<tr>
								<td>
									<a href={`/receipts/${receipt.id}`}
										>{receipt.store?.name || receipt.store_name || 'Unknown store'}</a
									>
									{#if receipt.store?.address}
										<div class="muted" style="font-size: 0.85em; margin-top: 2px">
											{receipt.store.address}
										</div>
									{/if}
								</td>
								<td class="muted">{receipt.purchased_at ?? '—'}</td>
								<td class="money">{formatMoney(receipt.total_cents)}</td>
								<td>
									{#if receipt.needs_review}
										<span class="badge">Needs review</span>
									{:else}
										<span class="badge badge-ok">Clear</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</section>

<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import Button from '#lib/components/Button.svelte';
	import ErrorState from '#lib/components/ErrorState.svelte';
	import { api, formatMoney, getToken, type LineItem, type Receipt } from '#lib';

	let receipt = $state<Receipt | null>(null);
	let error = $state('');
	let loading = $state(true);
	let savingId = $state<number | null>(null);
	let deleting = $state(false);
	let reparsing = $state(false);
	let imageUrl = $state<string | null>(null);

	async function load() {
		loading = true;
		error = '';
		if (imageUrl) {
			URL.revokeObjectURL(imageUrl);
			imageUrl = null;
		}
		try {
			if (!getToken()) {
				await goto('/login');
				return;
			}
			const id = Number(page.params.id);
			receipt = await api.getReceipt(id);
			if (receipt.has_image) {
				try {
					imageUrl = await api.fetchReceiptImage(id);
				} catch {
					imageUrl = null;
				}
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load receipt';
		} finally {
			loading = false;
		}
	}

	async function reparse() {
		if (!receipt) return;
		reparsing = true;
		error = '';
		try {
			receipt = await api.reparseReceipt(receipt.id);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Re-parse failed';
		} finally {
			reparsing = false;
		}
	}

	async function saveItem(itemId: number, field: string, value: string) {
		if (!receipt) return;
		savingId = itemId;
		try {
			const body: Record<string, string | number | boolean> = {};
			if (
				field === 'name' ||
				field === 'category' ||
				field === 'tax_status' ||
				field === 'quantity_unit'
			) {
				body[field] = value;
			} else body[field] = Number(value);
			const updated = await api.patchLineItem(itemId, body);
			receipt = {
				...receipt,
				line_items: receipt.line_items.map((item: LineItem) =>
					item.id === itemId ? updated : item
				)
			};
		} catch (err) {
			error = err instanceof Error ? err.message : 'Save failed';
		} finally {
			savingId = null;
		}
	}

	async function removeReceipt() {
		if (!receipt) return;
		if (!confirm('Delete this receipt and its line items? This cannot be undone.')) return;
		deleting = true;
		error = '';
		try {
			await api.deleteReceipt(receipt.id);
			await goto('/receipts');
		} catch (err) {
			error = err instanceof Error ? err.message : 'Delete failed';
		} finally {
			deleting = false;
		}
	}

	onMount(load);
</script>

<section>
	<a class="back-link" href="/receipts">← All receipts</a>

	{#if loading}
		<p class="muted">Loading receipt…</p>
	{:else if error && !receipt}
		<ErrorState description={error} onRetry={load} />
	{:else if receipt}
		<div class="page-header">
			<div>
				<h1>{receipt.store?.name || receipt.store_name || 'Receipt'}</h1>
				<p class="page-lede">
					{receipt.purchased_at ?? 'Unknown date'} · Total {formatMoney(receipt.total_cents)}
					{#if receipt.needs_review}
						· <span class="badge">Needs review</span>
					{/if}
				</p>
				{#if receipt.store?.address || receipt.store?.phone}
					<p class="muted" style="margin-top: 8px">
						{#if receipt.store.address}{receipt.store.address}{/if}
						{#if receipt.store.address && receipt.store.phone} · {/if}
						{#if receipt.store.phone}{receipt.store.phone}{/if}
					</p>
				{/if}
				{#if receipt.review_reasons?.length}
					<p class="muted" style="margin-top: 8px">
						Flags: {receipt.review_reasons.join(', ')}
					</p>
				{/if}
			</div>
			<div class="actions">
				<Button variant="ghost" type="button" onclick={load}>Reload</Button>
				{#if receipt.has_image}
					<Button variant="ghost" type="button" disabled={reparsing} onclick={reparse}>
						{reparsing ? 'Re-parsing…' : 'Re-parse'}
					</Button>
				{/if}
				<Button variant="danger" type="button" disabled={deleting} onclick={removeReceipt}>
					{deleting ? 'Deleting…' : 'Delete'}
				</Button>
			</div>
		</div>
		{#if error}
			<p class="muted" style="margin-bottom: 12px; color: var(--danger, #b42318)">{error}</p>
		{/if}

		{#if imageUrl}
			<figure class="receipt-image panel">
				<img src={imageUrl} alt="Uploaded receipt" />
			</figure>
		{/if}

		<div class="panel">
			<div class="table-wrap">
				<table class="table">
					<thead>
						<tr>
							<th>Item</th>
							<th>Qty</th>
							<th>Unit</th>
							<th class="money">Line</th>
							<th class="money">Tax</th>
							<th>Category</th>
							<th>Tax status</th>
						</tr>
					</thead>
					<tbody>
						{#each receipt.line_items as item (item.id)}
							<tr>
								<td>
									<input
										class="cell-input"
										value={item.name}
										aria-label="Item name"
										onblur={(e) => saveItem(item.id, 'name', e.currentTarget.value)}
									/>
								</td>
								<td>
									<input
										class="cell-input cell-qty"
										type="number"
										step="0.01"
										value={item.quantity}
										aria-label="Quantity"
										onblur={(e) => saveItem(item.id, 'quantity', e.currentTarget.value)}
									/>
								</td>
								<td>
									<select
										class="cell-input"
										value={item.quantity_unit || 'ea'}
										aria-label="Quantity unit"
										onchange={(e) => saveItem(item.id, 'quantity_unit', e.currentTarget.value)}
									>
										<option value="ea">ea</option>
										<option value="kg">kg</option>
										<option value="lb">lb</option>
										<option value="g">g</option>
										<option value="oz">oz</option>
									</select>
								</td>
								<td class="money">{formatMoney(item.line_total_cents)}</td>
								<td class="money">{formatMoney(item.tax_amount_cents)}</td>
								<td>
									<input
										class="cell-input"
										value={item.category}
										aria-label="Category"
										onblur={(e) => saveItem(item.id, 'category', e.currentTarget.value)}
									/>
								</td>
								<td class="muted status">
									{savingId === item.id ? 'Saving…' : item.tax_status.replace('_', ' ')}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if error}
				<p role="alert" style="color: var(--color-danger); margin: 16px 0 0">{error}</p>
			{/if}
		</div>
	{/if}
</section>

<style>
	.receipt-image {
		margin: 0 0 20px;
		padding: 12px;
		overflow: hidden;
	}

	.receipt-image img {
		display: block;
		width: 100%;
		max-height: 420px;
		object-fit: contain;
		background: #f4f4f2;
	}

	.cell-input {
		width: 100%;
		min-height: 36px;
		border: 1px solid var(--color-border-strong);
		border-radius: var(--radius-sm);
		padding: 6px 10px;
		font: inherit;
		background: #fff;
		caret-color: var(--color-brand);
	}

	.cell-input:focus {
		outline: none;
		box-shadow: var(--focus-ring);
		border-color: var(--color-brand);
	}

	.cell-qty {
		max-width: 88px;
		font-variant-numeric: tabular-nums;
	}

	.status {
		font-size: 0.8rem;
		text-transform: capitalize;
		white-space: nowrap;
	}
</style>

<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import Button from '#lib/components/Button.svelte';
	import ErrorState from '#lib/components/ErrorState.svelte';
	import { api, formatMoney, getToken, type LineItem, type Receipt } from '#lib';

	type ItemDraft = {
		name: string;
		quantity: string;
		quantity_unit: string;
		category: string;
	};

	const CATEGORY_OPTIONS = [
		'fruit',
		'vegetable',
		'snacks',
		'dairy',
		'meat',
		'bakery',
		'beverages',
		'grocery',
		'clothes',
		'gas',
		'household',
		'other'
	] as const;

	let receipt = $state<Receipt | null>(null);
	let error = $state('');
	let loading = $state(true);
	let savingId = $state<number | null>(null);
	let deleting = $state(false);
	let reparsing = $state(false);
	let reviewing = $state(false);
	let imageUrl = $state<string | null>(null);
	let imageContentType = $state('image/jpeg');
	let drafts = $state<Record<number, ItemDraft>>({});

	function draftFor(item: LineItem): ItemDraft {
		return (
			drafts[item.id] ?? {
				name: item.name,
				quantity: String(item.quantity),
				quantity_unit: item.quantity_unit || 'ea',
				category: item.category
			}
		);
	}

	function setDraft(itemId: number, patch: Partial<ItemDraft>) {
		const item = receipt?.line_items.find((row) => row.id === itemId);
		if (!item) return;
		drafts = {
			...drafts,
			[itemId]: { ...draftFor(item), ...patch }
		};
	}

	function isDirty(item: LineItem): boolean {
		const draft = drafts[item.id];
		if (!draft) return false;
		return (
			draft.name !== item.name ||
			draft.quantity !== String(item.quantity) ||
			draft.quantity_unit !== (item.quantity_unit || 'ea') ||
			draft.category !== item.category
		);
	}

	async function load() {
		loading = true;
		error = '';
		drafts = {};
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
					const file = await api.fetchReceiptImage(id);
					imageUrl = file.url;
					imageContentType = file.contentType;
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
			drafts = {};
		} catch (err) {
			error = err instanceof Error ? err.message : 'Re-parse failed';
		} finally {
			reparsing = false;
		}
	}

	async function markReviewed() {
		if (!receipt) return;
		reviewing = true;
		error = '';
		try {
			receipt = await api.patchReceipt(receipt.id, {
				needs_review: false,
				review_reasons: []
			});
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not update review status';
		} finally {
			reviewing = false;
		}
	}

	async function markNeedsReview() {
		if (!receipt) return;
		reviewing = true;
		error = '';
		try {
			receipt = await api.patchReceipt(receipt.id, {
				needs_review: true,
				review_reasons: receipt.review_reasons?.length ? receipt.review_reasons : ['manual']
			});
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not update review status';
		} finally {
			reviewing = false;
		}
	}

	async function saveItem(item: LineItem) {
		if (!receipt) return;
		const draft = draftFor(item);
		const body: Record<string, string | number> = {};
		if (draft.name !== item.name) body.name = draft.name;
		if (draft.quantity !== String(item.quantity)) body.quantity = Number(draft.quantity);
		if (draft.quantity_unit !== (item.quantity_unit || 'ea')) {
			body.quantity_unit = draft.quantity_unit;
		}
		if (draft.category !== item.category) body.category = draft.category;
		if (Object.keys(body).length === 0) return;

		savingId = item.id;
		error = '';
		try {
			const updated = await api.patchLineItem(item.id, body);
			receipt = {
				...receipt,
				line_items: receipt.line_items.map((row: LineItem) => (row.id === item.id ? updated : row))
			};
			const next = { ...drafts };
			delete next[item.id];
			drafts = next;
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
					{:else}
						· <span class="badge badge-ok">Reviewed</span>
					{/if}
				</p>
				{#if receipt.store?.address || receipt.store?.phone}
					<p class="muted" style="margin-top: 8px">
						{#if receipt.store.address}{receipt.store.address}{/if}
						{#if receipt.store.address && receipt.store.phone}
							·
						{/if}
						{#if receipt.store.phone}{receipt.store.phone}{/if}
					</p>
				{/if}
			</div>
			<div class="header-actions">
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

		{#if receipt.needs_review}
			<div class="review-banner panel" role="status">
				<div>
					<strong>Needs review</strong>
					<p class="muted" style="margin: 4px 0 0">
						{#if receipt.review_reasons?.length}
							Flags: {receipt.review_reasons.join(', ')}.
						{:else}
							Parser was unsure about some lines.
						{/if}
						Check the items below, then clear the flag when it looks right.
					</p>
				</div>
				<Button variant="success" type="button" disabled={reviewing} onclick={markReviewed}>
					{reviewing ? 'Saving…' : 'Mark as reviewed'}
				</Button>
			</div>
		{:else}
			<div class="review-clear">
				<Button variant="ghost" type="button" disabled={reviewing} onclick={markNeedsReview}>
					{reviewing ? 'Saving…' : 'Flag for review'}
				</Button>
			</div>
		{/if}

		{#if error}
			<p class="muted" style="margin-bottom: 12px; color: var(--danger, #b42318)">{error}</p>
		{/if}

		{#if imageUrl}
			<figure class="receipt-image panel">
				{#if imageContentType.includes('pdf')}
					<embed src={imageUrl} type="application/pdf" title="Uploaded receipt PDF" />
					<p class="muted" style="margin: 8px 0 0">
						<a href={imageUrl} download="receipt.pdf">Download PDF</a>
					</p>
				{:else}
					<img src={imageUrl} alt="Uploaded receipt" />
				{/if}
			</figure>
		{/if}

		<div class="panel">
			<p class="muted save-hint">
				Edit a row, then press Save. Category changes apply to future uploads.
			</p>
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
							<th></th>
						</tr>
					</thead>
					<tbody>
						{#each receipt.line_items as item (item.id)}
							{@const draft = draftFor(item)}
							{@const dirty = isDirty(item)}
							<tr class:dirty>
								<td>
									<input
										class="cell-input"
										value={draft.name}
										aria-label="Item name"
										oninput={(e) => setDraft(item.id, { name: e.currentTarget.value })}
									/>
								</td>
								<td>
									<input
										class="cell-input cell-qty"
										type="number"
										step="0.01"
										value={draft.quantity}
										aria-label="Quantity"
										oninput={(e) => setDraft(item.id, { quantity: e.currentTarget.value })}
									/>
								</td>
								<td>
									<select
										class="cell-input"
										value={draft.quantity_unit}
										aria-label="Quantity unit"
										onchange={(e) => setDraft(item.id, { quantity_unit: e.currentTarget.value })}
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
									<select
										class="cell-input"
										value={draft.category}
										aria-label="Category"
										onchange={(e) => setDraft(item.id, { category: e.currentTarget.value })}
									>
										{#each CATEGORY_OPTIONS as option}
											<option value={option}>{option}</option>
										{/each}
										{#if !CATEGORY_OPTIONS.includes(draft.category as (typeof CATEGORY_OPTIONS)[number])}
											<option value={draft.category}>{draft.category}</option>
										{/if}
									</select>
								</td>
								<td class="muted status">{item.tax_status.replace('_', ' ')}</td>
								<td class="row-save">
									<Button
										variant={dirty ? 'primary' : 'ghost'}
										type="button"
										disabled={!dirty || savingId === item.id}
										onclick={() => saveItem(item)}
									>
										{savingId === item.id ? 'Saving…' : 'Save'}
									</Button>
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
	.header-actions {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
	}

	.review-banner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-4);
		margin-bottom: 20px;
		border-color: var(--color-warning);
		background: var(--color-warning-soft);
	}

	.review-banner strong {
		display: block;
		color: var(--color-warning);
	}

	.review-clear {
		margin-bottom: 16px;
	}

	.save-hint {
		margin: 0 0 12px;
		font-size: var(--text-sm);
	}

	.receipt-image {
		margin: 0 0 20px;
		padding: 12px;
		overflow: hidden;
	}

	.receipt-image img,
	.receipt-image embed {
		display: block;
		width: 100%;
		min-height: 320px;
		max-height: 520px;
		object-fit: contain;
		background: #f4f4f2;
		border: 0;
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

	.row-save {
		white-space: nowrap;
		text-align: right;
	}

	tr.dirty {
		background: color-mix(in srgb, var(--color-brand) 6%, transparent);
	}
</style>

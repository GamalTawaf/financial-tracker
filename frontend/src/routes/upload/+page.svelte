<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import Button from '#lib/components/Button.svelte';
	import ErrorState from '#lib/components/ErrorState.svelte';
	import { api, getToken } from '#lib';

	let file = $state<File | null>(null);
	let error = $state('');
	let pending = $state(false);

	onMount(() => {
		if (!getToken()) goto('/login');
	});

	async function submit(event: Event) {
		event.preventDefault();
		if (!file) {
			error = 'Choose a receipt image first.';
			return;
		}
		pending = true;
		error = '';
		try {
			const receipt = await api.uploadReceipt(file);
			await goto(`/receipts/${receipt.id}`);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Upload failed';
		} finally {
			pending = false;
		}
	}
</script>

<section style="max-width: 560px">
	<div class="page-header" style="margin-bottom: 24px">
		<div>
			<h1>Upload</h1>
			<p class="page-lede">
				Drop a JPG or PNG. Local OCR reads the lines, categories them, and applies Ontario HST.
			</p>
		</div>
	</div>

	<form class="panel stack" onsubmit={submit}>
		<label class="dropzone" for="file">
			<strong>Choose receipt image</strong>
			<p class="muted" style="margin: 8px auto 0; max-width: 36ch">
				Phone photos work. Keep the whole slip in frame when you can.
			</p>
			<input
				id="file"
				type="file"
				accept="image/jpeg,image/png,image/webp,image/gif"
				onchange={(e) => (file = e.currentTarget.files?.[0] ?? null)}
			/>
			{#if file}
				<p style="margin: 12px 0 0; font-weight: 600">{file.name}</p>
			{/if}
		</label>

		{#if error}
			<ErrorState title="Couldn’t read that file" description={error} />
		{/if}

		<Button type="submit" disabled={pending || !file}>
			{pending ? 'Reading receipt…' : 'Parse receipt'}
		</Button>
	</form>
</section>

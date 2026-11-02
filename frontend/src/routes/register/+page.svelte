<script lang="ts">
	import { goto } from '$app/navigation';
	import Button from '#lib/components/Button.svelte';
	import { api } from '#lib';

	let email = $state('');
	let password = $state('');
	let displayName = $state('');
	let error = $state('');
	let pending = $state(false);

	async function submit(event: Event) {
		event.preventDefault();
		pending = true;
		error = '';
		try {
			await api.register({
				email,
				password,
				display_name: displayName
			});
			await goto('/receipts');
			location.reload();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Registration failed';
		} finally {
			pending = false;
		}
	}
</script>

<section class="auth-shell">
	<div>
		<h1>Create your ledger</h1>
		<p class="page-lede">One account. Every receipt line stays yours.</p>
	</div>
	<div class="panel stack">
		<form class="stack" onsubmit={submit}>
			<div class="field">
				<label for="name">Display name</label>
				<input id="name" bind:value={displayName} autocomplete="name" />
			</div>
			<div class="field">
				<label for="email">Email</label>
				<input id="email" type="email" bind:value={email} required autocomplete="email" />
			</div>
			<div class="field">
				<label for="password">Password</label>
				<input
					id="password"
					type="password"
					bind:value={password}
					required
					minlength="12"
					autocomplete="new-password"
				/>
				<p class="muted" style="margin: 4px 0 0; font-size: 0.85rem">
					At least 12 characters with upper, lower, and a digit.
				</p>
			</div>
			{#if error}
				<p role="alert" style="color: var(--color-danger); margin: 0">{error}</p>
			{/if}
			<Button type="submit" disabled={pending}>{pending ? 'Creating…' : 'Create account'}</Button>
		</form>
		<p class="muted" style="margin: 0">
			Already tracking? <a href="/login">Log in</a>
		</p>
	</div>
</section>

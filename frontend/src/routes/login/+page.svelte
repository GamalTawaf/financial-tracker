<script lang="ts">
	import { goto } from '$app/navigation';
	import Button from '#lib/components/Button.svelte';
	import { api } from '#lib';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let pending = $state(false);

	async function submit(event: Event) {
		event.preventDefault();
		pending = true;
		error = '';
		try {
			await api.login({ email, password });
			await goto('/receipts');
			location.reload();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Login failed';
		} finally {
			pending = false;
		}
	}
</script>

<section class="auth-shell">
	<div>
		<h1>Welcome back</h1>
		<p class="page-lede">Sign in to continue reading receipts into your ledger.</p>
	</div>
	<div class="panel stack">
		<form class="stack" onsubmit={submit}>
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
					autocomplete="current-password"
				/>
			</div>
			{#if error}
				<p role="alert" style="color: var(--color-danger); margin: 0">{error}</p>
			{/if}
			<Button type="submit" disabled={pending}>{pending ? 'Signing in…' : 'Sign in'}</Button>
		</form>
		<p class="muted" style="margin: 0">
			No account? <a href="/register">Create one</a>
		</p>
	</div>
</section>

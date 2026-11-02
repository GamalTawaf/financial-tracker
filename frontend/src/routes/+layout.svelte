<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import Button from '#lib/components/Button.svelte';
	import { api, getToken, setTokens, type User } from '#lib';

	let { children } = $props();
	let user = $state<User | null>(null);
	let booting = $state(true);

	onMount(async () => {
		if (getToken()) {
			try {
				user = await api.me();
			} catch {
				setTokens(null, null);
				user = null;
			}
		}
		booting = false;
	});

	async function logout() {
		await api.logout();
		user = null;
		await goto('/login');
	}

	const path = $derived(page.url.pathname);
</script>

<div class="app-shell">
	<header class="topbar">
		<a class="brand" href={user ? '/receipts' : '/'}>
			<span class="brand-mark" aria-hidden="true"></span>
			Ledger
		</a>
		<nav class="nav" aria-label="Main">
			{#if user}
				<a href="/receipts" aria-current={path.startsWith('/receipts') ? 'page' : undefined}
					>Receipts</a
				>
				<a href="/upload" aria-current={path === '/upload' ? 'page' : undefined}>Upload</a>
				<a href="/stores" aria-current={path === '/stores' ? 'page' : undefined}>Stores</a>
				<a href="/categories" aria-current={path === '/categories' ? 'page' : undefined}
					>Categories</a
				>
				<span class="nav-user">{user.display_name}</span>
				<Button variant="ghost" type="button" onclick={logout}>Log out</Button>
			{:else if !booting}
				<a href="/login" aria-current={path === '/login' ? 'page' : undefined}>Log in</a>
				<a href="/register" aria-current={path === '/register' ? 'page' : undefined}>Register</a>
			{/if}
		</nav>
	</header>

	<main>
		{#if booting}
			<p class="muted">Loading workspace…</p>
		{:else}
			{@render children()}
		{/if}
	</main>
</div>

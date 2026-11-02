/** Empty in local Vite (proxied); set VITE_API_BASE for Docker/production builds. */
const API_BASE = import.meta.env.VITE_API_BASE ?? '';
const browser = typeof window !== 'undefined';

export type User = {
	id: number;
	email: string;
	display_name: string;
	province: string;
};

export type LineItem = {
	id: number;
	name: string;
	quantity: number;
	quantity_unit: string;
	unit_price_cents: number;
	line_total_cents: number;
	category: string;
	tax_status: string;
	tax_amount_cents: number;
	confidence: number;
	needs_review: boolean;
};

export type Store = {
	id: number;
	name: string;
	address: string;
	phone: string;
};

export type Receipt = {
	id: number;
	store_id: number | null;
	store_name: string;
	store: Store | null;
	purchased_at: string | null;
	subtotal_cents: number | null;
	tax_total_cents: number | null;
	total_cents: number | null;
	needs_review: boolean;
	review_reasons: string[];
	has_image: boolean;
	created_at: string;
	line_items: LineItem[];
};

export type CategoryTotal = {
	category: string;
	total_cents: number;
	tax_cents: number;
	item_count: number;
};

const ACCESS_KEY = 'ft_access';
const REFRESH_KEY = 'ft_refresh';

function storage(): Storage | null {
	if (!browser) return null;
	return sessionStorage;
}

export function getToken(): string | null {
	return storage()?.getItem(ACCESS_KEY) ?? null;
}

export function getRefreshToken(): string | null {
	return storage()?.getItem(REFRESH_KEY) ?? null;
}

export function setTokens(access: string | null, refresh: string | null = null) {
	const store = storage();
	if (!store) return;
	if (access) store.setItem(ACCESS_KEY, access);
	else store.removeItem(ACCESS_KEY);
	if (refresh) store.setItem(REFRESH_KEY, refresh);
	else if (refresh === null && access === null) store.removeItem(REFRESH_KEY);
}

/** @deprecated use setTokens */
export function setToken(token: string | null) {
	setTokens(token, token ? getRefreshToken() : null);
}

/** Money is stored/transported as integer cents; divide by 100 only for display. */
export function formatMoney(cents: number | null | undefined): string {
	if (cents == null) return '—';
	return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(cents / 100);
}

/** Convert a decimal dollar string/number from UI input into integer cents. */
export function dollarsToCents(value: string | number): number {
	const n = typeof value === 'number' ? value : Number(value.replace(/[$,\s]/g, ''));
	if (!Number.isFinite(n)) return 0;
	return Math.round(n * 100);
}

async function refreshAccessToken(): Promise<string | null> {
	const refresh = getRefreshToken();
	if (!refresh) return null;
	const response = await fetch(`${API_BASE}/api/auth/refresh`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ refresh_token: refresh })
	});
	if (!response.ok) {
		setTokens(null, null);
		return null;
	}
	const payload = await response.json();
	setTokens(payload.access_token, payload.refresh_token);
	return payload.access_token as string;
}

/** Turn API error payloads into a short UI string; never surface raw JSON or inputs. */
function formatApiError(detail: unknown, fallback: string): string {
	if (typeof detail === 'string' && detail.trim()) return detail;
	if (Array.isArray(detail)) {
		const parts = detail
			.map((item) => {
				if (typeof item === 'string') return item;
				if (item && typeof item === 'object' && 'msg' in item) {
					const loc = Array.isArray((item as { loc?: unknown }).loc)
						? ((item as { loc: unknown[] }).loc as unknown[])
						: [];
					const field = [...loc].reverse().find((p) => p !== 'body' && typeof p === 'string');
					const msg = String((item as { msg: unknown }).msg);
					if (field === 'password') {
						return msg.toLowerCase().includes('at least')
							? 'Password must be at least 12 characters'
							: msg;
					}
					return field ? `${field}: ${msg}` : msg;
				}
				return '';
			})
			.filter(Boolean);
		if (parts.length) return parts.join('; ');
	}
	return fallback || 'Request failed';
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
	const headers = new Headers(init.headers);
	const token = getToken();
	if (token) headers.set('Authorization', `Bearer ${token}`);
	if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
		headers.set('Content-Type', 'application/json');
	}
	const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
	if (response.status === 401 && retry && getRefreshToken()) {
		const next = await refreshAccessToken();
		if (next) return request<T>(path, init, false);
	}
	if (!response.ok) {
		let detail: unknown = response.statusText;
		try {
			const payload = await response.json();
			detail = payload.detail ?? detail;
		} catch {
			/* ignore */
		}
		throw new Error(formatApiError(detail, response.statusText || 'Request failed'));
	}
	if (response.status === 204) return undefined as T;
	return response.json() as Promise<T>;
}

type TokenPayload = {
	access_token: string;
	refresh_token: string;
	expires_in: number;
};

async function authRequest(path: string, body: unknown): Promise<TokenPayload> {
	const payload = await request<TokenPayload>(
		path,
		{
			method: 'POST',
			body: JSON.stringify(body)
		},
		false
	);
	setTokens(payload.access_token, payload.refresh_token);
	return payload;
}

export const api = {
	register: (body: { email: string; password: string; display_name?: string }) =>
		authRequest('/api/auth/register', body),
	login: (body: { email: string; password: string }) => authRequest('/api/auth/login', body),
	logout: async () => {
		const refresh = getRefreshToken();
		if (refresh) {
			try {
				await request(
					'/api/auth/logout',
					{
						method: 'POST',
						body: JSON.stringify({ refresh_token: refresh })
					},
					false
				);
			} catch {
				/* ignore */
			}
		}
		setTokens(null, null);
	},
	me: () => request<User>('/api/auth/me'),
	listReceipts: () => request<Receipt[]>('/api/receipts'),
	getReceipt: (id: number) => request<Receipt>(`/api/receipts/${id}`),
	deleteReceipt: (id: number) => request<void>(`/api/receipts/${id}`, { method: 'DELETE' }),
	reparseReceipt: (id: number) =>
		request<Receipt>(`/api/receipts/${id}/reparse`, { method: 'POST' }),
	receiptImageUrl: (id: number) => `${API_BASE}/api/receipts/${id}/image`,
	/** Fetch receipt image/PDF with Bearer auth; returns object URL + MIME (caller should revoke). */
	fetchReceiptImage: async (id: number): Promise<{ url: string; contentType: string }> => {
		const headers = new Headers();
		const token = getToken();
		if (token) headers.set('Authorization', `Bearer ${token}`);
		let response = await fetch(`${API_BASE}/api/receipts/${id}/image`, { headers });
		if (response.status === 401 && getRefreshToken()) {
			const next = await refreshAccessToken();
			if (next) {
				headers.set('Authorization', `Bearer ${next}`);
				response = await fetch(`${API_BASE}/api/receipts/${id}/image`, { headers });
			}
		}
		if (!response.ok) throw new Error('Image not available');
		const blob = await response.blob();
		return {
			url: URL.createObjectURL(blob),
			contentType: blob.type || response.headers.get('content-type') || 'application/octet-stream'
		};
	},
	listStores: () => request<Store[]>('/api/stores'),
	uploadReceipt: (file: File) => {
		const form = new FormData();
		form.append('file', file);
		return request<Receipt>('/api/receipts/upload', { method: 'POST', body: form });
	},
	patchReceipt: (
		id: number,
		body: Partial<Pick<Receipt, 'store_name' | 'purchased_at' | 'needs_review' | 'review_reasons'>>
	) =>
		request<Receipt>(`/api/receipts/${id}`, {
			method: 'PATCH',
			body: JSON.stringify(body)
		}),
	patchLineItem: (id: number, body: Partial<LineItem>) =>
		request<LineItem>(`/api/receipts/line-items/${id}`, {
			method: 'PATCH',
			body: JSON.stringify(body)
		}),
	categoryStats: () => request<{ categories: CategoryTotal[] }>('/api/stats/by-category')
};

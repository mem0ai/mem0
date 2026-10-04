import type { ZObject, Bundle } from 'zapier-platform-core';

export type { ZObject, Bundle };

/** Mutable outgoing request, as seen by the beforeRequest middleware. */
export interface MutableRequest {
	url?: string;
	headers?: Record<string, string>;
	[key: string]: unknown;
}

/** Response as seen by the afterResponse middleware. */
export interface ZResponse {
	status: number;
	data?: Record<string, unknown> | unknown[] | null;
	content?: string;
	[key: string]: unknown;
}

/** Async add response from POST /v3/memories/add/. */
export interface AddResponse {
	event_id?: string;
	status?: string;
	error?: string;
	message?: string;
	results?: unknown[];
	[key: string]: unknown;
}

/** GET /v1/event/{id}/ response. */
export interface EventResponse {
	status?: string;
	error?: string;
	message?: string;
	[key: string]: unknown;
}

/** A stored memory object returned by search / list. */
export interface Memory {
	id?: string;
	memory?: string;
	[key: string]: unknown;
}

/**
 * Abstract backend interface and factory.
 */

import type { Mem0Config } from "../config.js";
import { PlatformBackend } from "./platform.js";

export interface AddOptions {
	userId?: string;
	agentId?: string;
	appId?: string;
	runId?: string;
	metadata?: Record<string, unknown>;
	immutable?: boolean;
	infer?: boolean;
	expires?: string;
	categories?: string[];
}

export interface SearchOptions {
	userId?: string;
	agentId?: string;
	appId?: string;
	runId?: string;
	topK?: number;
	threshold?: number;
	rerank?: boolean;
	keyword?: boolean;
	filters?: Record<string, unknown>;
	fields?: string[];
}

export interface ListOptions {
	userId?: string;
	agentId?: string;
	appId?: string;
	runId?: string;
	page?: number;
	pageSize?: number;
	category?: string;
	after?: string;
	before?: string;
}

export interface DeleteOptions {
	all?: boolean;
	userId?: string;
	agentId?: string;
	appId?: string;
	runId?: string;
}

export interface EntityIds {
	userId?: string;
	agentId?: string;
	appId?: string;
	runId?: string;
}

export interface Backend {
	add(
		content?: string,
		messages?: Record<string, unknown>[],
		opts?: AddOptions,
	): Promise<Record<string, unknown>>;

	search(
		query: string,
		opts?: SearchOptions,
	): Promise<Record<string, unknown>[]>;

	get(memoryId: string): Promise<Record<string, unknown>>;

	listMemories(opts?: ListOptions): Promise<Record<string, unknown>[]>;

	update(
		memoryId: string,
		content?: string,
		metadata?: Record<string, unknown>,
	): Promise<Record<string, unknown>>;

	delete(
		memoryId?: string,
		opts?: DeleteOptions,
	): Promise<Record<string, unknown>>;

	deleteEntities(opts: EntityIds): Promise<Record<string, unknown>>;

	ping(): Promise<Record<string, unknown>>;

	status(opts?: { userId?: string; agentId?: string }): Promise<
		Record<string, unknown>
	>;

	entities(entityType: string): Promise<Record<string, unknown>[]>;

	listEvents(): Promise<Record<string, unknown>[]>;

	getEvent(eventId: string): Promise<Record<string, unknown>>;
}

export class AuthError extends Error {
	constructor(
		message = "Authentication failed. Your API key may be invalid or expired.",
	) {
		super(message);
		this.name = "AuthError";
	}
}

export class NotFoundError extends Error {
	constructor(path: string) {
		super(`Resource not found: ${path}`);
		this.name = "NotFoundError";
	}
}

export class APIError extends Error {
	constructor(path: string, detail: string) {
		super(`Bad request to ${path}: ${detail}`);
		this.name = "APIError";
	}
}

export function getBackend(config: Mem0Config): Backend {
	return new PlatformBackend(config.platform);
}

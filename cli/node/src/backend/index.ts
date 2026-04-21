/**
 * Backend factory re-export.
 */

export { getBackend } from "./base.js";
export type {
	Backend,
	AddOptions,
	SearchOptions,
	ListOptions,
	DeleteOptions,
	EntityIds,
} from "./base.js";
export { AuthError, NotFoundError, APIError } from "./base.js";

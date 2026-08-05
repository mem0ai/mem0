import { createHash } from 'crypto';

// Anonymous usage telemetry via PostHog, mirroring the Mem0 CLI / plugins.
// Fire-and-forget: never awaited, never throws, so it can neither slow down
// nor break an action. Opt out with MEM0_TELEMETRY=false.
const POSTHOG_API_KEY = 'phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX';
const POSTHOG_HOST = 'https://us.i.posthog.com/i/v0/e/';

export function captureEvent(
	event: string,
	apiKey: string | undefined,
	properties: Record<string, unknown> = {},
): void {
	if (process.env.MEM0_TELEMETRY === 'false') return;
	try {
		// Hash the API key so events are attributable to one account without
		// ever transmitting the key itself.
		const distinctId = apiKey ? createHash('md5').update(apiKey).digest('hex') : 'zapier-anon';
		const payload = {
			api_key: POSTHOG_API_KEY,
			event,
			distinct_id: distinctId,
			properties: {
				source: 'ZAPIER',
				$process_person_profile: false,
				...properties,
			},
		};
		void fetch(POSTHOG_HOST, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload),
		}).catch(() => {
			/* swallow — telemetry must never surface to the user */
		});
	} catch {
		/* swallow — telemetry must never break the action */
	}
}

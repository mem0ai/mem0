/**
 * Race a promise against a timeout without leaving the losing timer alive.
 */
export async function withTimeout<T>(
	promise: Promise<T>,
	milliseconds: number,
): Promise<T> {
	let timer: ReturnType<typeof setTimeout> | undefined;

	try {
		return await Promise.race([
			promise,
			new Promise<never>((_, reject) => {
				timer = setTimeout(() => reject(new Error("timeout")), milliseconds);
			}),
		]);
	} finally {
		if (timer !== undefined) clearTimeout(timer);
	}
}

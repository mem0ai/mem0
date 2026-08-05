/** Jest config lives here (not in package.json) so the published package.json
 * stays minimal for the n8n verification scanner. This file is dev-only; it is
 * not shipped (see the `files` field in package.json). */
module.exports = {
	testEnvironment: 'node',
	testMatch: ['**/test/**/*.test.ts'],
	transform: {
		'^.+\\.tsx?$': ['ts-jest', {}],
	},
};

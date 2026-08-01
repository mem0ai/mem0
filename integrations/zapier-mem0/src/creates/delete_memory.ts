import type { ZObject, Bundle } from '../types';

const perform = async (z: ZObject, bundle: Bundle) => {
	// Trailing slash required (Django APPEND_SLASH); id encoded so a stray slash can't mistarget the path.
	const response = await z.request({
		url: `/v1/memories/${encodeURIComponent(String(bundle.inputData.memory_id))}/`,
		method: 'DELETE',
	});
	return response.data || { message: 'Deleted', memory_id: bundle.inputData.memory_id };
};

export default {
	key: 'delete_memory',
	noun: 'Memory',
	display: {
		label: 'Delete Memory',
		description: 'Delete a single memory by its ID.',
	},
	operation: {
		perform,
		inputFields: [{ key: 'memory_id', label: 'Memory ID', type: 'string', required: true }],
		sample: { message: 'Memory deleted successfully' },
	},
};

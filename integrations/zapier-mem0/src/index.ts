import { version as platformVersion } from 'zapier-platform-core';
import authentication from './authentication';
import { includeApiKey, handleBadResponses } from './middleware';
import addMemory from './creates/add_memory';
import deleteMemory from './creates/delete_memory';
import searchMemories from './searches/search_memories';
import getMemories from './searches/get_memories';
import pkg from '../package.json';

const app = {
	version: pkg.version,
	platformVersion,

	authentication,

	beforeRequest: [includeApiKey],
	afterResponse: [handleBadResponses],

	creates: {
		[addMemory.key]: addMemory,
		[deleteMemory.key]: deleteMemory,
	},

	searches: {
		[searchMemories.key]: searchMemories,
		[getMemories.key]: getMemories,
	},

	resources: {},
	triggers: {},
};

export = app;

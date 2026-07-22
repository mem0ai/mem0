import authentication from './authentication';
import { includeApiKey, handleBadResponses } from './middleware';
import addMemory from './creates/add_memory';
import deleteMemory from './creates/delete_memory';
import searchMemories from './searches/search_memories';
import getMemories from './searches/get_memories';

// Read version at runtime from the package manifest (one directory up from dist/).
const { version } = require('../package.json');
const platformVersion = require('zapier-platform-core').version;

const app = {
	version,
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

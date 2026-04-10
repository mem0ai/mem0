import { combineReducers } from 'redux';
import { layoutReducer } from './reducers/layoutReducer';
import { memoryReducer } from './reducers/memoryReducer';
import { settingsReducer } from './reducers/settingsReducer';
import { statsReducer } from './reducers/statsReducer';
import { filterReducer } from './reducers/filterReducer';

const rootReducer = combineReducers({
    layout: layoutReducer,
    memory: memoryReducer,
    settings: settingsReducer,
    stats: statsReducer,
    filter: filterReducer,
})

export default rootReducer;

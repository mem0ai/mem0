import { combineReducers } from "redux";
import { layoutReducer } from "./reducers/layoutReducer";
import { statsReducer } from "./reducers/statsReducer";

const rootReducer = combineReducers({
  layout: layoutReducer,
  stats: statsReducer,
});

export default rootReducer;

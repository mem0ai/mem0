import { combineReducers } from "redux";
import { layoutReducer } from "./reducers/layoutReducer";

const rootReducer = combineReducers({
  layout: layoutReducer,
});

export default rootReducer;

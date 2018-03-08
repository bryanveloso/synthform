import * as actions from 'actions/whammy';

const initialState = {
  isFetching: false,
  error: '',
  cheers: {},
  events: []
};

const whammy = (state = initialState, action) => {
  switch (action.type) {
    case actions.WHAMMY_FETCH.REQUEST:
      return {
        ...state,
        isFetching: true
      };
    case actions.WHAMMY_FETCH.FAILURE:
      return {
        ...state,
        isFetching: false,
        error: action.error
      };
    case actions.WHAMMY_FETCH.SUCCESS:
      return {
        ...state,
        isFetching: false,
        cheers: action.payload.cheers,
        events: action.payload.events
      };
    default:
      return state;
  }
};

export default whammy;

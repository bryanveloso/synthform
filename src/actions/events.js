import { action, createRequestTypes } from './utils';

export const EVENT_FETCH = createRequestTypes('EVENT_FETCH');
export const EVENT_NOTIFIER_ADD = 'EVENT_NOTIFIER_ADD';
export const EVENT_NOTIFIER_DELETE = 'EVENT_NOTIFIER_DELETE';

export const eventFetch = {
  request: debugMode => action(EVENT_FETCH.REQUEST, { debugMode }),
  success: (payload, lastUpdated) =>
    action(EVENT_FETCH.SUCCESS, { payload, lastUpdated }),
  failure: error => action(EVENT_FETCH.FAILURE, { error })
};

export const eventNotifier = {
  add: event => action(EVENT_NOTIFIER_ADD, { event }),
  delete: () => action(EVENT_NOTIFIER_DELETE)
};

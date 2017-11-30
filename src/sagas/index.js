import { all, spawn } from 'redux-saga/effects';

import emoteSagas from './emotes';
import eventSagas from './events';
import messageSagas from './messages';
import songSagas from './songs';
import subathonSagas from './subathon';
import subscriptionSagas from './subscriptions';
import uptimeSagas from './uptime';

export default function* rootSaga() {
  yield all([
    spawn(emoteSagas),
    spawn(eventSagas),
    spawn(messageSagas),
    spawn(songSagas),
    spawn(subathonSagas),
    spawn(subscriptionSagas),
    spawn(uptimeSagas)
  ]);
}

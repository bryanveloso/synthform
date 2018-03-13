import { createSelector } from 'reselect';

export const getFetchState = state => {
  const isFetching = [
    state.events.isFetching,
    state.subscriptions.isFetchingLatestSubscriber,
    state.subscriptions.isFetchingSubPoints
  ];
  return isFetching.every(Boolean);
};

export const getTotalEmoteCounts = state => state.emotes.emotes;

export const getNotifierPool = state => state.events.notifierPool;
export const getEventList = state => state.events.events;
export const getShouldNotify = state => state.events.notificationsActive;

export const getMessages = state => state.messages.messages;

export const getLatestSubscription = state => state.subscriptions.latest;
export const getSubPoints = state => state.subscriptions.subPoints;

export const getStreamStartTime = state => state.uptime.startTime;

export const getCurrentSong = state => state.songs.currentSong;
export const getQueueSize = state => state.songs.queueSize;

export const getSubathon = state => state.subathon.payload;
export const getSubathonState = state => state.subathon.isActive;

export const getCurrentChristmasBroadcaster = state => state.christmas.current;
export const getNextChristmasBroadcaster = state => state.christmas.next;

export const getWhammyCheers = state => state.whammy.cheers;
export const getWhammyEvents = state => state.whammy.events;
export const getWhammyNotifierPool = state => state.whammy.notifierPool;

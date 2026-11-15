// null means explicitly unlimited; missing/invalid limits fail closed.
export const limitLabel = limit => limit === null ? 'Unlimited' : Number.isInteger(limit) && limit >= 0 ? limit : 'Unavailable';
export const belowLimit = (count, limit) => Number.isInteger(count) && count >= 0 &&
  (limit === null || (Number.isInteger(limit) && limit >= 0 && count < limit));

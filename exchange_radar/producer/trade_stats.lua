-- One bounded batch, with a cumulative snapshot for every accepted trade.
local trades = cjson.decode(ARGV[1])
local ttl = tonumber(ARGV[2])
local now = ARGV[3]
local cached = redis.call('GET', KEYS[3])
if cached then
    cached = cjson.decode(cached)
    if cached.token == ARGV[4] then
        return cjson.encode(cached.snapshots)
    end
end
local results, initialized, prices, heartbeats = {}, {}, {}, {}

local function not_newer(id, previous)
    return #id < #previous or (#id == #previous and id <= previous)
end

for i, trade in ipairs(trades) do
    local day = KEYS[trade.day]
    local seen = KEYS[trade.seen]
    local identity = trade.exchange .. ':' .. trade.symbol
    local previous = trade.id and redis.call('HGET', seen, identity)

    if previous and not_newer(trade.id, previous) then
        results[i] = false
    else
        local metadata = day .. ':' .. trade.coin
        if not initialized[metadata] then
            redis.call('HSETNX', day, trade.coin .. '_PRICE', trade.price)
            redis.call('HSETNX', day, trade.coin .. '_CURRENCY', trade.currency)
            redis.call('HSETNX', day, trade.coin .. '_EXCHANGES', trade.exchanges)
            redis.call('EXPIRE', day, ttl, 'NX')
            initialized[metadata] = true
        end

        local own = trade.seller and 'SELL' or 'BUY'
        local other = trade.seller and 'BUY' or 'SELL'
        local volume = redis.call('HINCRBYFLOAT', day, trade.coin .. '_VOLUME', trade.quantity)
        local own_volume = redis.call('HINCRBYFLOAT', day, trade.coin .. '_VOLUME_' .. own .. '_ORDERS', trade.quantity)
        local other_volume = redis.call('HGET', day, trade.coin .. '_VOLUME_' .. other .. '_ORDERS')
        local own_count = redis.call('HINCRBY', day, trade.coin .. '_NUMBER_' .. own .. '_ORDERS', 1)
        local other_count = redis.call('HGET', day, trade.coin .. '_NUMBER_' .. other .. '_ORDERS')
        if trade.seller then
            results[i] = {volume, other_volume or cjson.null, own_volume, other_count or cjson.null, own_count}
        else
            results[i] = {volume, own_volume, other_volume or cjson.null, own_count, other_count or cjson.null}
        end

        if trade.id then
            redis.call('HSET', seen, identity, trade.id)
            redis.call('EXPIRE', seen, ttl, 'NX')
        end
        prices[trade.coin .. '_PRICE'] = trade.price
        prices[trade.coin .. '_CURRENCY'] = trade.currency
        heartbeats[trade.exchange] = now
    end
end

for field, value in pairs(prices) do
    redis.call('HSET', KEYS[1], field, value)
end
for exchange, timestamp in pairs(heartbeats) do
    redis.call('HSET', KEYS[2], exchange, timestamp)
end
-- Keep just the latest response per worker to recover an ambiguous timeout.
redis.call('SET', KEYS[3], cjson.encode({token = ARGV[4], snapshots = results}), 'EX', 3600)
return cjson.encode(results)

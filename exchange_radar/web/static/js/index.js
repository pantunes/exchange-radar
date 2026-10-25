let tradeRowLimit = null;
let historyRequest = null;
let historyLiveRows = [];
let historyLoadedLimit = 0;

function trimTradeRows() {
    const messages = document.getElementById('messages');
    const limit = tradeRowLimit === null ? max_rows : tradeRowLimit;
    while (messages.children.length > limit) {
        messages.lastElementChild.remove();
    }
}

function fitTradeFeed() {
    const feed = document.getElementById('trade-feed');
    const messages = document.getElementById('messages');
    if (!feed || !messages) {
        return;
    }

    const feedRect = feed.getBoundingClientRect();
    const panel = feed.closest('section');
    const bottomPadding = panel.getBoundingClientRect().bottom - feedRect.bottom;
    const bottomMargin = parseFloat(getComputedStyle(panel.parentElement).paddingBottom);
    const headerHeight = messages.getBoundingClientRect().top - feedRect.top - feed.clientTop;
    const maxHeight = Math.max(headerHeight,
        window.innerHeight - feedRect.top - window.scrollY - bottomPadding - bottomMargin);
    feed.style.maxHeight = `${maxHeight}px`;

    const style = getComputedStyle(feed);
    const scrollbarHeight = feed.offsetHeight - feed.clientHeight - feed.clientTop * 2;
    // Use the height cap so a sparse feed can grow as new trades arrive.
    const availableHeight = maxHeight - headerHeight - parseFloat(style.paddingBottom) - scrollbarHeight;
    const rowHeight = messages.firstElementChild?.getBoundingClientRect().height || parseFloat(style.lineHeight);
    const rowsThatFit = Math.floor(availableHeight / rowHeight);
    const previousLimit = tradeRowLimit;
    tradeRowLimit = Math.max(0, rowsThatFit);
    if (saved_history) {
        tradeRowLimit = Math.min(max_rows, tradeRowLimit);
    }
    historyLoadedLimit = Math.min(historyLoadedLimit, tradeRowLimit);
    trimTradeRows();
    if (previousLimit !== null && tradeRowLimit > previousLimit && historyLoadedLimit > 0) {
        retrieveTradeHistory();
    }
}

function setupTradeFeed() {
    fitTradeFeed();
    const feed = document.getElementById('trade-feed');
    if (feed) {
        new ResizeObserver(fitTradeFeed).observe(feed);
        // A content-sized feed may not resize when the viewport grows.
        window.addEventListener('resize', fitTradeFeed);
        document.fonts.ready.then(fitTradeFeed);
    }
}

function addRow(obj) {
    if (historyRequest) {
        historyLiveRows.push(obj);
    }
    const messages = document.getElementById('messages');
    messages.prepend(createElement(obj));
    trimTradeRows();
}

function retrieveData() {
    $.get(http_stats_url).done(function (response) {
        setVolume(response);
        setVolumeTrades(response);
        setNumberTrades(response);
    })
    retrieveTradeHistory();
}

function retrieveTradeHistory() {
    if (!saved_history) {
        $.get(http_trades_url).done(function (response) {
            for (const obj of response.r) {
                addRow(obj);
            }
        });
        return;
    }
    const limit = Math.max(1, tradeRowLimit === null ? max_rows : tradeRowLimit);
    if (historyRequest || limit <= historyLoadedLimit) {
        return;
    }
    historyLiveRows = [];
    historyRequest = $.get(http_trades_url, {limit}).done(function (response) {
        // Preserve trades arriving during the request, without repeating those
        // already included in the saved snapshot. Count identical rows separately.
        const rows = response.r.slice();
        const occurrences = new Map();
        for (const obj of rows) {
            occurrences.set(obj.message, (occurrences.get(obj.message) || 0) + 1);
        }
        for (const obj of historyLiveRows) {
            const count = occurrences.get(obj.message) || 0;
            if (count > 0) {
                occurrences.set(obj.message, count - 1);
            } else {
                rows.push(obj);
            }
        }
        historyLoadedLimit = Math.min(limit, tradeRowLimit);
        historyLiveRows = [];
        historyRequest = null;
        rows.sort((a, b) => a.trade_time_ts - b.trade_time_ts);
        document.getElementById('messages').replaceChildren();
        for (const obj of rows) {
            addRow(obj);
        }
    }).always(function () {
        historyRequest = null;
        historyLiveRows = [];
        // The screen may have grown while the previous request was in flight.
        if (historyLoadedLimit === limit && tradeRowLimit > limit) {
            retrieveTradeHistory();
        }
    });
}

function createElement(obj) {
    const span = document.createElement("span");

    if (obj.is_seller === false) {
        span.className = "order_buy";
    } else {
        span.className = "order_sell";
    }

    span.innerHTML = ` ${obj.message} `;
    return span
}

function setVolume(obj) {
    const volume = obj.volume.toLocaleString('en-US', {
        minimumFractionDigits: 8,
        maximumFractionDigits: 8
    });
    $(`#${obj.trade_symbol}_volume`).text(volume);

    if (obj.hasOwnProperty('price')) {
        const volume_in_currency = (obj.volume * obj.price).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        $(`#${obj.trade_symbol}_volume_in_currency`).text(volume_in_currency);
        $(`#${obj.trade_symbol}_currency`).text(obj.currency);
    }
}

function setVolumeTrades(obj) {
    const volume_trades_buys = obj.volume_trades[0].toLocaleString('en-US', {
        minimumFractionDigits: 8,
        maximumFractionDigits: 8
    });
    $(`#${obj.trade_symbol}_volume_trades_buy_orders`).text(volume_trades_buys);

    const volume_trades_sells = obj.volume_trades[1].toLocaleString('en-US', {
        minimumFractionDigits: 8,
        maximumFractionDigits: 8
    });
    $(`#${obj.trade_symbol}_volume_trades_sell_orders`).text(volume_trades_sells);
}

function setNumberTrades(obj) {
    $(`#${obj.trade_symbol}_number_trades_buy_orders`).text(obj.number_trades[0].toLocaleString('en-US'));
    $(`#${obj.trade_symbol}_number_trades_sell_orders`).text(obj.number_trades[1].toLocaleString('en-US'));
}

function formatPage() {
    const subURL = new URL(http_trades_url).pathname.replace(/^\/api\/feed/, "");
    $("a").each(function () {
        const link = $(this).attr('href');
        if (link === subURL) {
            $(this).addClass('active');
        }
    });
}

function getStatus() {
    $.get(http_status_url).done(function (response) {
        for (const [key, value] of Object.entries(response["exchanges"])) {
            $(`#${key}`)
                .toggleClass('status-up', value === true)
                .toggleClass('status-down', value !== true);
        }
    })
}

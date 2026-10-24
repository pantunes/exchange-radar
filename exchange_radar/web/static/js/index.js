let tradeRowLimit = null;

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

    const style = getComputedStyle(feed);
    const headerHeight = messages.getBoundingClientRect().top - feed.getBoundingClientRect().top - feed.clientTop;
    const availableHeight = feed.clientHeight - headerHeight - parseFloat(style.paddingBottom);
    const rowsThatFit = Math.floor(availableHeight / parseFloat(style.lineHeight));
    tradeRowLimit = Math.max(0, Math.min(max_rows, rowsThatFit));
    trimTradeRows();
}

function setupTradeFeed() {
    fitTradeFeed();
    const feed = document.getElementById('trade-feed');
    if (feed) {
        new ResizeObserver(fitTradeFeed).observe(feed);
    }
}

function addRow(obj) {
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
    $.get(http_trades_url).done(function (response) {
        for (const obj of response.r) {
            addRow(obj);
        }
    })
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
        minimumFractionDigits: 4,
        maximumFractionDigits: 8
    });
    $(`#${obj.trade_symbol}_volume`).text(volume);

    if (obj.hasOwnProperty('price')) {
        const volume_in_currency = (obj.volume * obj.price).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        $(`#${obj.trade_symbol}_volume_in_currency`).text(`${volume_in_currency} ${obj.currency}`);
    }
}

function setVolumeTrades(obj) {
    const volume_trades_buys = obj.volume_trades[0].toLocaleString('en-US', {
        minimumFractionDigits: 4,
        maximumFractionDigits: 8
    });
    $(`#${obj.trade_symbol}_volume_trades_buy_orders`).text(volume_trades_buys);

    const volume_trades_sells = obj.volume_trades[1].toLocaleString('en-US', {
        minimumFractionDigits: 4,
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
            $(this).css({'font-weight': 'bold', 'font-size': '1.2em'});
        }
    });
}

function getStatus() {
    $.get(http_status_url).done(function (response) {
        for (const [key, value] of Object.entries(response["exchanges"])) {
            let class_on_off = "2px solid #c76565";
            if (value === true) {
                class_on_off = "2px solid #367a59";
            }
            $(`#${key}`).css('border', class_on_off)
        }
    })
}

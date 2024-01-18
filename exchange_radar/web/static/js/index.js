function createElement(obj) {
    const span = document.createElement("span");

    if (obj.is_seller === false) {
        span.className = "order_buy";
    } else {
        span.className = "order_sell";
    }

    span.innerHTML = ` ${obj.message} \n`;
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

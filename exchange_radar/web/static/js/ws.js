function setupAndStartWS() {
    const ws = new WebSocket(websocket_url);

    ws.onopen = (event) => {
        console.log("onopen")
    };

    ws.onclose = (event) => {
        console.log("onclose")
    };

    ws.onmessage = function (event) {
        const obj = JSON.parse(event.data);
        setPageTitle(obj);
        addRow(obj);
        setVolume(obj);
        setVolumeTrades(obj);
        setNumberTrades(obj);
    }

    ws.onclose = function(e) {
        console.log("Socket is closed. Reconnect will be attempted in 1 second.", e.reason);
        setTimeout(function() {
            setupAndStartWS()
        }, 1000);
    };

    ws.onerror = function(err) {
        console.error("Socket encountered error: ", err.message, "Closing socket");
        ws.close();
    };
}

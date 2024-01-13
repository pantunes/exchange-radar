from __future__ import annotations

import json

import websockets


class WSKrakenOutMsg:
    def __init__(self, payload: str | dict) -> None:
        self.payload = payload if type(payload) is str else json.dumps(payload)


class WSKrakenInMsg:
    def __init__(self, payload: str) -> None:
        self.payload = json.loads(payload)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(payload={self.payload})"


class WSKrakenClient:
    def __init__(
        self,
        uri: str = "wss://ws.kraken.com",
        auth_uri: str = "wss://ws-auth.kraken.com",
        open_auth_socket: bool = True,
    ) -> None:
        self.uri = uri
        self.auth_uri = auth_uri
        self.open_auth_socket = open_auth_socket

    async def send(self, msg: WSKrakenOutMsg) -> None:
        await self._raw_send(msg.payload)

    async def _raw_send(self, *args, **kwargs) -> None:
        await self.websocket.send(*args, **kwargs)

    async def auth_send(self, msg: WSKrakenOutMsg) -> None:
        await self._raw_auth_send(msg.payload)

    async def _raw_auth_send(self, *args, **kwargs) -> None:
        await self.auth_websocket.send(*args, **kwargs)

    async def recv(self) -> WSKrakenInMsg:
        return WSKrakenInMsg(await self._raw_recv())

    async def _raw_recv(self) -> str | bytes:
        return await self.websocket.recv()

    async def auth_recv(self) -> WSKrakenInMsg:
        return WSKrakenInMsg(await self._raw_auth_recv())

    async def _raw_auth_recv(self) -> str | bytes:
        return await self.auth_websocket.recv()

    async def __aenter__(self) -> WSKrakenClient:
        self.websocket: websockets.WebSocketClientProtocol = await websockets.connect(self.uri)
        if self.open_auth_socket:
            print(
                "You are also opening an authenticated socket. At least one "
                "private message should be subscribed to keep the authenticated "
                "client connection open."
            )
            self.auth_websocket: websockets.WebSocketClientProtocol = await websockets.connect(self.auth_uri)
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb) -> None:
        await self.websocket.close()

    async def ping(self) -> None:
        await self.send(WSKrakenOutMsg({"event": "ping"}))

    async def subscribe_custom(self, payload) -> None:
        assert payload["event"] == "subscribe"
        await self.send(WSKrakenOutMsg(payload))

    async def unsubscribe_custom(self, payload) -> None:
        assert payload["event"] == "unsubscribe"
        await self.send(WSKrakenOutMsg(payload))

    def _gen_raw_subscription_payload(
        self,
        event: str,
        sub_name: str,
        reqid: int = None,
        pair: list[str] = None,
        sub_depth: int = None,
        sub_interval: int = None,
        sub_ratecounter: int = None,
        sub_snapshot: bool = None,
        sub_token: str = None,
    ) -> dict:
        _locals = locals()
        del _locals["self"]
        payload = {k: v for (k, v) in _locals.items() if not k.startswith("sub") and v is not None}
        payload["subscription"] = {k[4:]: v for (k, v) in _locals.items() if k.startswith("sub") and v is not None}
        return payload

    def _gen_raw_subscribe_payload(self, **kwargs) -> dict:
        return self._gen_raw_subscription_payload(event="subscribe", **kwargs)

    def _gen_raw_unsubscribe_payload(self, **kwargs) -> dict:
        return self._gen_raw_subscription_payload(event="unsubscribe", **kwargs)

    async def subscribe_ticker(self, pair: list[str], **kwargs) -> None:
        await self.send(WSKrakenOutMsg(self._gen_raw_subscribe_payload(sub_name="ticker", pair=pair, **kwargs)))

    async def unsubscribe_ticker(self, pair: list[str], **kwargs) -> None:
        await self.send(WSKrakenOutMsg(self._gen_raw_unsubscribe_payload(sub_name="ticker", pair=pair, **kwargs)))

    async def subscribe_trade(self, pair: list[str], **kwargs) -> None:
        await self.send(WSKrakenOutMsg(self._gen_raw_subscribe_payload(sub_name="trade", pair=pair, **kwargs)))

    async def unsubscribe_trade(self, pair: list[str], **kwargs) -> None:
        await self.send(WSKrakenOutMsg(self._gen_raw_unsubscribe_payload(sub_name="trade", pair=pair, **kwargs)))

    async def subscribe_ohlc(self, pair: list[str], interval: int) -> None:
        await self.send(
            WSKrakenOutMsg(self._gen_raw_subscribe_payload(sub_name="ohlc", pair=pair, sub_interval=interval))
        )

    async def unsubscribe_ohlc(self, pair: list[str], interval: int) -> None:
        await self.send(
            WSKrakenOutMsg(self._gen_raw_unsubscribe_payload(sub_name="ohlc", pair=pair, sub_interval=interval))
        )

    async def subscribe_own_trades(self, token: str, snapshot: bool = True, **kwargs) -> None:
        await self.auth_send(
            WSKrakenOutMsg(
                self._gen_raw_subscribe_payload(
                    sub_name="ownTrades",
                    sub_token=token,
                    sub_snapshot=snapshot,
                    **kwargs,
                )
            )
        )

    async def unsubscribe_own_trades(self, token: str, **kwargs) -> None:
        await self.auth_send(
            WSKrakenOutMsg(self._gen_raw_unsubscribe_payload(sub_name="ownTrades", sub_token=token, **kwargs))
        )

    async def subscribe_open_orders(self, token: str, ratecounter: bool = False, **kwargs) -> None:
        await self.auth_send(
            WSKrakenOutMsg(
                self._gen_raw_subscribe_payload(
                    sub_name="openOrders",
                    sub_token=token,
                    sub_ratecounter=ratecounter,
                    **kwargs,
                )
            )
        )

    async def unsubscribe_open_orders(self, token: str, ratecounter: bool = False, **kwargs) -> None:
        await self.auth_send(
            WSKrakenOutMsg(
                self._gen_raw_unsubscribe_payload(
                    sub_name="openOrders",
                    sub_token=token,
                    sub_ratecounter=ratecounter,
                    **kwargs,
                )
            )
        )

    async def add_order(
        self,
        token: str,
        ordertype: str,
        type: str,
        pair: str,
        volume: str,
        price: str = None,
        price2: str = None,
        leverage: int = None,
        oflags: str = None,
        starttm: str = None,
        expiretm: str = None,
        deadline: str = None,
        userref: str = None,
        validate: str = None,
        close_ordertype: str = None,
        close_price: str = None,
        close_price2: str = None,
        timeinforce: str = None,
        reqid: int = None,
    ) -> None:
        _locals = locals()
        del _locals["self"]

        def rename_key(k):
            key_to_new = {
                "close_ordertype": "close[ordertype]",
                "close_price": "close[price]",
                "close_price2": "close[price2]",
            }
            return key_to_new.get(k, k)

        payload = {rename_key(k): v for (k, v) in _locals.items() if v is not None}
        payload["event"] = "addOrder"
        await self.auth_send(WSKrakenOutMsg(payload))

    async def cancel_order(self, token: str, txid: list[str]):
        await self.auth_send(WSKrakenOutMsg(dict(event="cancelOrder", token=token, txid=txid)))

# web / frontend
ab -n 10000 "http://127.0.0.1:9000/BTC"

ab -n 10000 -c 50 "http://127.0.0.1:9000/BTC"

ab -n 10000 -c 50 -k "http://127.0.0.1:9000/BTC"

# web / backend
ab -n 10000 -c 50 -p $1 -T application/json http://127.0.0.1:9000/api/feed/BTC

ab -n 10000 -c 50 -p $1 -T application/json http://127.0.0.1:9000/api/feed/BTC/whales

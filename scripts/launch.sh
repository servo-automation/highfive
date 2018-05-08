#!/usr/bin/bash

echo 'Launching reftest screenshots thing...'
docker run --name screenshots -p 5000:5000 -d screenshots

echo 'Launching highfive...'

# Set env variables here

docker run --name highfive -v ~/highfive.pem:/highfive.pem:ro -v ~/json_dumps:/dumps \
    -e PEM_KEY="/highfive.pem" -e SECRET="$SECRET" \
    -e ID=$ID -e DUMP_PATH="/dumps" -e IMGUR_CLIENT_ID=$CLIENT_ID \
    -e SCREENSHOTS_IP="http://$SHOTS_IP:$SHOTS_PORT" \
    -p 8000:8000 -d highfive

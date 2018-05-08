#!/usr/bin/bash

echo 'Removing existing containers...'
docker rm -f $(docker ps -a -q)

if [ ! -z "$CLEAN" ]; then
    echho 'Pulling and rebuilding image...'
    cd ~/highfive
    git pull origin master
    docker build -t highfive .

    cd ~/reftest-screenshots
    git pull origin master
    docker build -t screenshots .
fi

echo 'Removing unused images...'
docker rmi $(docker images | grep "<none>" | awk '{print $3}')

cd ~
./launch.sh

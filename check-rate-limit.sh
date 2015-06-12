#!/bin/sh

while true; 
do 
    curl -i -H "Authorization: token $1" https://api.github.com/rate_limit 2>/dev/null > rate; 
    cat rate | grep "X-RateLimit-Remaining:";  
    date -d @$(cat rate | grep "X-RateLimit-Reset:" | awk '{ print $2 }');
    rm rate;
    sleep 5; 
done


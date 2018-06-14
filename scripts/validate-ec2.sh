#!/bin/bash

export BOTPID=`ps aux | grep 'sakuraibot.py' | grep -v grep | awk '{print($2)}'`
if [ -n "$BOTPID" ]; then
  echo "Running correctly."
else
  echo "ERROR: Script stopped."
  echo "=== Nohup: ==="
  tail -n 25 /home/ec2-user/SakuraiBot-Ultimate/nohup.out
  echo "=== Bot log: ==="
  tail -n 25 /home/ec2-user/SakuraiBot-Ultimate/logs/sakuraibot.log
  exit 1
fi

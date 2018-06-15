#!/bin/bash

pkill -f sakuraibot.py

cd /home/ec2-user/SakuraiBot-Ultimate/src
nohup python3 sakuraibot.py > /home/ec2-user/SakuraiBot-Ultimate/nohup.out 2>&1 &
disown

#!/bin/bash

pkill -f bot_manager.py

cd /home/ec2-user/SakuraiBot-Ultimate/src
nohup python3 sakuraibot.py --test > /home/ec2-user/SakuraiBot-Ultimate/nohup.out 2>&1 &
disown

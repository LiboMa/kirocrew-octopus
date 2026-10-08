#!/bin/zsh
set -eu
cd -- "$(dirname -- "$0")"
python3 pipeline_launch.py
printf '\n按 Enter 关闭此窗口。\n'
read -r

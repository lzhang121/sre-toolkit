#!/bin/bash

# 期望输出示例：
# ./grade.sh 85
# 成绩: 85, 等级: B

score=$1

if [ -z "$score" ]; then
    echo "请输入成绩"
    exit 1
fi 

if [ $score -ge 90 ]; then
    echo "成绩: $score, 等级: A"
elif [ $score -ge 80 ]; then
    echo "成绩: $score, 等级: B"
elif [ $score -ge 70 ]; then
    echo "成绩: $score, 等级: C"
else
    echo "成绩: $score, 等级: D"
fi
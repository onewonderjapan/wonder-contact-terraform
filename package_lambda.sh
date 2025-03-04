#!/bin/bash

# 创建临时目录
mkdir -p temp_lambda

# 复制Lambda函数代码到临时目录
cp lambda_function.py temp_lambda/

# 在临时目录中创建ZIP包
cd temp_lambda
zip -r ../lambda_function.zip .
cd ..

# 清理临时目录
rm -rf temp_lambda

echo "Lambda package created: lambda_function.zip"
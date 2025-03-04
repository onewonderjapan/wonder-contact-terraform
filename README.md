# OneWonder Contact Form Infrastructure

这个Terraform项目用于管理OneWonder联系表单的AWS基础设施，包括API Gateway、Lambda和SES配置。

## 项目结构

```
onewonder-contact-terraform/
├── main.tf               # 主Terraform配置文件
├── variables.tf          # 变量定义
├── outputs.tf            # 输出配置
├── email_config.json     # 邮箱配置JSON文件
├── lambda_function.py    # Lambda函数代码
├── package_lambda.sh     # Lambda打包脚本
└── README.md             # 项目说明文件
```

## 功能特点

- 使用JSON文件管理邮箱配置
- 完整的API Gateway设置，包括CORS支持
- Lambda函数自动将JSON配置转换为环境变量
- SES邮箱验证自动化
- 完整的IAM权限配置

## 使用方法

### 前提条件

1. 安装Terraform (v1.0.0+)
2. 配置AWS认证凭证
3. 准备好域名的DNS访问权限（用于邮件安全配置）

### 部署步骤

1. 克隆仓库
   ```
   git clone [仓库URL]
   cd onewonder-contact-terraform
   ```

2. 更新邮箱配置
   ```
   # 编辑email_config.json文件，设置正确的发件人和收件人邮箱
   ```

3. 创建Lambda部署包
   ```
   chmod +x package_lambda.sh
   ./package_lambda.sh
   ```

4. 初始化Terraform
   ```
   terraform init
   ```

5. 生成执行计划
   ```
   terraform plan
   ```

6. 应用配置
   ```
   terraform apply
   ```

7. 确认部署
   ```
   # 查看输出中的API Gateway URL和其他资源信息
   terraform output
   ```

## API Gateway URL

部署完成后，您将获得一个API Gateway端点URL，格式类似于：
```
https://xxxxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/prod/contact
```

将此URL更新到前端代码中的fetch请求中：

```javascript
const response = await fetch('YOUR_API_GATEWAY_URL', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(formDataObj),
});
```

## 邮件安全配置

要解决邮件被标记为不安全的问题，请在您的DNS配置中添加以下记录：

1. **SPF记录**
   ```
   类型: TXT
   名称: @
   值: v=spf1 include:amazonses.com ~all
   ```

2. **DKIM记录**
   请在AWS SES控制台中获取DKIM记录配置，通常是3个CNAME记录。

3. **DMARC记录**
   ```
   类型: TXT
   名称: _dmarc
   值: v=DMARC1; p=none; sp=none; rua=mailto:admin@onewonder.co.jp
   ```

## 维护和更新

1. 修改邮箱配置
   ```
   # 编辑email_config.json后运行
   terraform apply
   ```

2. 更新Lambda代码
   ```
   # 修改lambda_function.py后运行
   ./package_lambda.sh
   terraform apply
   ```
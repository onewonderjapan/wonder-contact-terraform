# 读取邮箱配置JSON文件
data "local_file" "email_config" {
  filename = "email_config.json"
}

locals {
  email_config = jsondecode(data.local_file.email_config.content)
}
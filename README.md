# OneWonder Contact Form Infrastructure

この Terraform プロジェクトは、OneWonder のお問い合わせフォームの AWS インフラストラクチャを管理するためのもので、API Gateway、Lambda、SES 設定を含みます。

## 项目结构

```
onewonder-contact-terraform/
├── main.tf               # メインTerraform設定ファイル
├── variables.tf          # 変数定義
├── outputs.tf            # 出力設定
├── email_config.json     # メール設定JSONファイル
├── lambda_function.py    # Lambda関数コード
├── package_lambda.sh     # Lambdaパッケージングスクリプト
└── README.md             # プロジェクト説明ファイル
```

## 功能特点

- JSON ファイルによるメール設定の管理
- CORS サポートを含む完全な API Gateway 設定
- Lambda 関数が JSON 設定を環境変数に自動変換
- 完全な IAM 権限設定

## 使用方法

### 前提条件

1. Terraform のインストール (v1.6.6)
2. AWS 認証情報の設定
3. ドメイン名の DNS アクセス権限（メールセキュリティ設定用）

### 部署步骤

1. リポジトリをクローン

   ```
   git clone [リポジトリURL]
   cd onewonder-contact-terraform
   ```

2. メール設定の更新

   ```
   # email_config.jsonファイルを編集し、正しい送信者と受信者のメールアドレスを設定
   ```

3. Lambda デプロイパッケージの作成

   ```
   ワークフローでpyファイルをzipにする
   ```

4. Terraform の初期化

   ```
   terraform init
   ```

5. 実行計画の生成

   ```
   terraform plan
   ```

6. 設定の適用

   ```
   terraform apply
   ```

7. デプロイの確認
   ```
   　# 出力から API Gateway URL とその他のリソース情報を確認
    terraform output
   ```

## API Gateway URL

デプロイ完了後、以下のような形式の API Gateway エンドポイント URL が提供されます：

```

https://xxxxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/prod/contact

```

この URL をフロントエンドコードの fetch リクエストに更新してください：

```javascript
const response = await fetch("YOUR_API_GATEWAY_URL", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify(formDataObj),
});
```
